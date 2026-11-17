"""
advanced_analysis.py

End-to-end analysis of the EPC project data, from simple to complex:
  L1  Data profiling and quality checks
  L2  Diagnostic statistics (chi-square, Kruskal-Wallis, Spearman)
  L3  Earned schedule and EAC methods
  L4  Monte Carlo simulation (cost at completion, punch list completion)
  L5  Survival analysis (RFI time to answer, open RFIs censored)
  L6  Predictive model (late PO delivery, leakage-safe features, time-based split)
  L7  Unsupervised learning (supplier clustering, PO anomaly detection)
  L8  Prescriptive what-if scenarios
Writes figures to analysis/figures, tables to analysis/tables, and results.json.

Usage: python src/advanced_analysis.py
"""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.ensemble import HistGradientBoostingClassifier, IsolationForest
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, roc_curve, silhouette_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import kpis
import style

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "analysis" / "figures"
TAB = ROOT / "analysis" / "tables"
DATA_DATE = pd.Timestamp("2026-06-30")
SRC = "Synthetic EPC project data. Data date 30 Jun 2026."
B, O, A, Y, N = style.SERIES[0], style.SERIES[1], style.SERIES[2], style.SERIES[3], style.NEUTRAL
rng = np.random.default_rng(7)
R = {}  # results for the report


def save(fig, name):
    style.finish(fig, FIG / f"{name}.png", SRC)


def table(df, name):
    df.to_csv(TAB / f"{name}.csv", index=False)
    return df


# ------------------------------------------------------------------ L1 profiling
def profile(k):
    specs = {
        "engineering_documents": ("doc_no", ["planned_issue_date", "first_submittal_date", "approved_date"]),
        "rfis": ("rfi_no", ["raised_date", "answered_date"]),
        "purchase_orders": ("po_no", ["po_date", "promised_date", "delivered_date"]),
        "punch_items": ("punch_no", ["raised_date", "closed_date"]),
        "ncrs": ("ncr_no", ["raised_date", "closed_date"]),
        "ev_monthly": (None, ["month"]),
    }
    rows = []
    for t, (key, dates) in specs.items():
        df = k[t]
        d0 = pd.to_datetime(df[dates[0]])
        rows.append({
            "table": t, "rows": len(df), "columns": df.shape[1],
            "null_cells_pct": round(100 * df.isna().sum().sum() / df.size, 1),
            "duplicate_keys": int(df[key].duplicated().sum()) if key else 0,
            "date_from": d0.min().date(), "date_to": d0.max().date(),
        })
    prof = table(pd.DataFrame(rows), "L1_profile")

    d, r, p, pi = k["engineering_documents"], k["rfis"], k["purchase_orders"], k["punch_items"]
    checks = [
        ("Approved before first submittal", (pd.to_datetime(d.approved_date) < pd.to_datetime(d.first_submittal_date)).sum()),
        ("RFI answered before raised", (pd.to_datetime(r.answered_date) < pd.to_datetime(r.raised_date)).sum()),
        ("PO promised before PO date", (pd.to_datetime(p.promised_date) < pd.to_datetime(p.po_date)).sum()),
        ("Non-positive PO value", (p.po_value <= 0).sum()),
        ("Punch closed before raised", (pd.to_datetime(pi.closed_date) < pd.to_datetime(pi.raised_date)).sum()),
        ("Events after data date", sum((pd.to_datetime(k[t][c]) > DATA_DATE).sum() for t, c in
                                       [("rfis", "answered_date"), ("punch_items", "closed_date"), ("purchase_orders", "delivered_date")])),
        ("Earned value above budget", (k["pc_monthly"].ev > k["control_accounts"].bac.sum()).sum()),
    ]
    chk = table(pd.DataFrame(checks, columns=["rule", "violations"]), "L1_logic_checks")
    R["L1"] = {"profile": prof.to_dict("records"), "checks": chk.to_dict("records"),
               "total_rows": int(prof.rows.sum() + len(k["control_accounts"]))}


# ------------------------------------------------------------------ L2 diagnostics
def diagnostics(k):
    d = k["engineering_documents"].dropna(subset=["first_return_code"])
    ct = pd.crosstab(d.discipline, d.first_return_code)
    chi2, p, dof, exp = stats.chi2_contingency(ct)
    cramer = np.sqrt(chi2 / (ct.values.sum() * (min(ct.shape) - 1)))
    resid = (ct - exp) / np.sqrt(exp)

    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    vmax = np.abs(resid.values).max()
    im = ax.imshow(resid.values, cmap="RdBu_r", vmin=-vmax, vmax=vmax, aspect="auto")
    for i in range(resid.shape[0]):
        for j in range(resid.shape[1]):
            ax.text(j, i, f"{resid.values[i, j]:+.1f}", ha="center", va="center", fontsize=9,
                    color="#fff" if abs(resid.values[i, j]) > vmax * 0.6 else style.TEXT)
    ax.set_xticks(range(resid.shape[1]), resid.columns), ax.set_yticks(range(resid.shape[0]), resid.index)
    ax.grid(False)
    fig.colorbar(im, ax=ax, shrink=0.8, label="Standardized residual")
    ax.set_title("Return code by discipline: observed vs expected (chi-square residuals)")
    save(fig, "L2_chi_square_residuals")

    r = k["rfis"].dropna(subset=["answered_date"]).copy()
    r["days"] = (pd.to_datetime(r.answered_date) - pd.to_datetime(r.raised_date)).dt.days
    groups = [g.days.values for _, g in r.groupby("discipline")]
    kw = stats.kruskal(*groups)
    hi, lo = r[r.priority == "High"].days, r[r.priority == "Low"].days
    mw = stats.mannwhitneyu(hi, lo, alternative="less")

    eng = k["eng_by_discipline"].set_index("discipline")
    rfi_n = k["rfis"].groupby("discipline").size()
    docs_n = k["engineering_documents"].groupby("discipline").size()
    rate = (rfi_n / docs_n).rename("rfis_per_document")
    j = eng.join(rate)
    rho, rho_p = stats.spearmanr(j.first_time_approval_pct, j.rfis_per_document)
    table(j.reset_index()[["discipline", "first_time_approval_pct", "rfis_per_document"]].round(3), "L2_quality_vs_rfis")

    R["L2"] = {
        "chi2": round(chi2, 1), "chi2_dof": int(dof), "chi2_p": float(p), "cramers_v": round(cramer, 3),
        "worst_code3": resid["Code 3"].sort_values(ascending=False).head(2).round(1).to_dict(),
        "kw_h": round(kw.statistic, 1), "kw_p": float(kw.pvalue),
        "median_high": float(hi.median()), "median_low": float(lo.median()), "mw_p": float(mw.pvalue),
        "spearman_rho": round(rho, 2), "spearman_p": round(rho_p, 3),
        "rfis_per_doc": rate.round(2).sort_values(ascending=False).to_dict(),
    }


# ------------------------------------------------------------------ L3 earned schedule
def earned_schedule(k):
    m = k["pc_monthly"].copy()
    m["month"] = pd.to_datetime(m.month)
    bac = k["control_accounts"].bac.sum()
    cur = m.dropna(subset=["ev"]).iloc[-1]
    pv = m[["month", "pv"]].reset_index(drop=True)
    # ES: interpolate the time at which planned value equalled current earned value
    idx = int((pv.pv <= cur.ev).sum()) - 1
    t0, t1 = idx + 1, idx + 2  # months elapsed at end of month idx and idx+1
    frac = (cur.ev - pv.pv[idx]) / (pv.pv[idx + 1] - pv.pv[idx])
    es = t0 + frac
    at = len(m.dropna(subset=["ev"]))
    pd_months = len(m)
    spi_t = es / at
    ieac_t = pd_months / spi_t
    finish_planned = m.month.iloc[-1]
    finish_forecast = m.month.iloc[0] + pd.DateOffset(months=int(round(ieac_t)) - 1)
    eac = {
        "CPI method (BAC / CPI)": bac / cur.cpi,
        "Composite (AC + (BAC - EV) / (CPI x SPI))": cur.ac + (bac - cur.ev) / (cur.cpi * cur.spi),
        "Remaining at plan rate (AC + BAC - EV)": cur.ac + (bac - cur.ev),
    }
    table(pd.DataFrame([{"method": k_, "eac_busd": round(v / 1e9, 3), "vac_musd": round((bac - v) / 1e6)} for k_, v in eac.items()]), "L3_eac_methods")

    fig, ax = plt.subplots(figsize=(8, 4.4))
    ax.plot(m.month, m.pv / 1e9, color=N, linestyle="--", label="Planned value")
    ax.plot(m.month, m.ev / 1e9, color=B, label="Earned value")
    es_date = m.month.iloc[0] + pd.DateOffset(days=int((es - 1) * 30.44))
    ax.hlines(cur.ev / 1e9, es_date, cur.month, color=O, linewidth=2)
    ax.plot([es_date], [cur.ev / 1e9], "o", color=O, markersize=8, markeredgecolor=style.SURFACE)
    ax.annotate(f"Schedule gap: {at - es:.1f} months\nSPI(t) = {spi_t:.3f}", xy=(es_date, cur.ev / 1e9),
                xytext=(m.month.iloc[3], cur.ev / 1e9 + 0.6), fontsize=9,
                arrowprops=dict(arrowstyle="-", color=style.TEXT_2, lw=0.8))
    ax.yaxis.set_major_formatter(mtick.StrMethodFormatter("${x:.1f}B"))
    ax.legend(loc="lower right")
    ax.set_title("Earned schedule: when was today's earned value planned?")
    save(fig, "L3_earned_schedule")
    R["L3"] = {
        "es_months": round(es, 2), "at_months": at, "spi_t": round(spi_t, 3), "spi_cost": round(cur.spi, 3),
        "planned_duration": pd_months, "ieac_t_months": round(ieac_t, 1),
        "finish_planned": finish_planned.strftime("%b %Y"), "finish_forecast": finish_forecast.strftime("%b %Y"),
        "slip_months": round(ieac_t - pd_months, 1),
        "eac": {k_: round(v / 1e9, 3) for k_, v in eac.items()}, "bac": round(bac / 1e9, 3),
    }


# ------------------------------------------------------------------ L4 Monte Carlo
def monte_carlo(k, n=10_000):
    ev = k["ev_monthly"].dropna(subset=["ev"]).copy()
    ev["month"] = pd.to_datetime(ev.month)
    ev = ev.sort_values(["control_account", "month"])
    g = ev.groupby("control_account")
    ev["d_ev"], ev["d_ac"] = g.ev.diff(), g.ac.diff()
    recent = ev[(ev.month > DATA_DATE - pd.DateOffset(months=12)) & (ev.d_ac > 0)].copy()
    recent["cpi_m"] = recent.d_ev / recent.d_ac
    cur = ev[ev.month == DATA_DATE].set_index("control_account")
    bac = k["control_accounts"].set_index("control_account").bac
    remaining = (bac - cur.ev).clip(lower=0)
    # Bootstrap each control account's future CPI from its own last 12 monthly CPIs, plus a shared
    # project-level shock so accounts are correlated (common causes: labor market, productivity).
    shock = rng.normal(1.0, 0.02, n)
    total = np.full(n, cur.ac.sum())
    for ca, rem in remaining.items():
        hist = recent.loc[recent.control_account == ca, "cpi_m"].clip(0.6, 1.4).values
        if len(hist) == 0 or rem == 0:
            continue
        draws = rng.choice(hist, size=(n, 6)).mean(axis=1) * shock
        total += rem / draws
    p10, p50, p80, p90 = np.percentile(total, [10, 50, 80, 90])
    b = bac.sum()
    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.hist(total / 1e9, bins=60, color=B, alpha=0.85, edgecolor=style.SURFACE, linewidth=0.5)
    for v, lab, c in [(b, "BAC", style.TEXT), (p50, "P50", O), (p90, "P90", O)]:
        ax.axvline(v / 1e9, color=c, linestyle="--" if lab != "BAC" else "-", linewidth=1.2)
        ax.text(v / 1e9, ax.get_ylim()[1] * 0.95, f" {lab} ${v / 1e9:.2f}B", fontsize=8, color=style.TEXT, va="top")
    ax.set_xlabel("Estimate at completion ($B)"), ax.set_yticks([])
    ax.set_title(f"Cost at completion: {n:,} Monte Carlo runs")
    save(fig, "L4_eac_monte_carlo")
    R["L4_cost"] = {"runs": n, "p10": round(p10 / 1e9, 3), "p50": round(p50 / 1e9, 3), "p80": round(p80 / 1e9, 3),
                    "p90": round(p90 / 1e9, 3), "bac": round(b / 1e9, 3), "prob_within_bac": round(float((total <= b).mean()), 3),
                    "contingency_p80_musd": round((p80 - b) / 1e6)}

    punch_sim(k, n=5000)


def simulate_punch(weekly, n, close_mult=1.0, max_weeks=156, taper=(0.0, 0.04)):
    w = weekly.tail(12).copy()
    raised = np.diff(w.raised_cum.values)
    closed = np.diff(w.closed_cum.values)
    open0 = int(w.open_items.iloc[-1])
    # New punch items taper as construction completes. The weekly taper rate is uncertain,
    # so each simulated future draws its own rate from the given range.
    paths = np.zeros((n, max_weeks + 1))
    paths[:, 0] = open0
    done = np.full(n, max_weeks)
    for s in range(n):
        o = open0
        decay = 1 - rng.uniform(*taper)
        for t in range(1, max_weeks + 1):
            new = rng.choice(raised) * (decay ** t)
            cl = rng.choice(closed) * close_mult
            o = max(o + new - cl, 0)
            paths[s, t] = o
            if o < 1:
                done[s] = t
                paths[s, t:] = 0
                break
    return paths, done


def punch_sim(k, n):
    w = k["punch_weekly"]
    start = pd.Timestamp(w.week_end.iloc[-1])
    paths, done = simulate_punch(w, n)
    q = {p: start + pd.Timedelta(weeks=int(np.percentile(done, p))) for p in (10, 50, 80, 90)}
    paths2, done2 = simulate_punch(w, n, close_mult=1.2)
    q2 = {p: start + pd.Timedelta(weeks=int(np.percentile(done2, p))) for p in (50, 80)}
    _, done0 = simulate_punch(w, n, taper=(0.0, 0.0))
    q0 = {p: start + pd.Timedelta(weeks=int(np.percentile(done0, p))) for p in (50, 80)}
    weeks = pd.date_range(start, periods=paths.shape[1], freq="W-SUN")
    lo, med, hi = np.percentile(paths, [10, 50, 90], axis=0)
    cut = int(np.percentile(done, 97)) + 4
    fig, ax = plt.subplots(figsize=(8, 4.2))
    hist = pd.to_datetime(w.week_end)
    ax.plot(hist, w.open_items, color=B, label="Actual open items")
    ax.fill_between(weeks[:cut], lo[:cut], hi[:cut], color=B, alpha=0.18, label="P10 to P90 range")
    ax.plot(weeks[:cut], med[:cut], color=B, linestyle="--", label="Median path")
    lin = pd.Timestamp(k["punch_forecast"].forecast_zero_date.iloc[0])
    ax.axvline(lin, color=N, linestyle=":", linewidth=1.2)
    ax.text(lin, ax.get_ylim()[1] * 0.9, " Linear\n forecast", fontsize=8, color=style.TEXT_2)
    ax.axvline(q[80], color=O, linestyle="--", linewidth=1.2)
    ax.text(q[80], ax.get_ylim()[1] * 0.7, f" P80\n {q[80]:%b %Y}", fontsize=8, color=style.TEXT)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=3, fontsize=8, borderaxespad=0.2)
    import matplotlib.dates as mdates
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 4, 7, 10]))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.set_title(f"Punch list completion: {n:,} simulated futures", pad=28)
    save(fig, "L4_punch_simulation")
    R["L4_punch"] = {"runs": n, **{f"p{p}": d.strftime("%d %b %Y") for p, d in q.items()},
                     "linear": lin.strftime("%d %b %Y"),
                     "faster_p50": q2[50].strftime("%d %b %Y"), "faster_p80": q2[80].strftime("%d %b %Y"),
                     "weeks_saved_p80": int((q[80] - q2[80]).days / 7),
                     "no_taper_p50": q0[50].strftime("%d %b %Y"), "no_taper_p80": q0[80].strftime("%d %b %Y"),
                     "recent_raised_per_week": round(float(np.diff(w.tail(12).raised_cum.values).mean()), 1),
                     "recent_closed_per_week": round(float(np.diff(w.tail(12).closed_cum.values).mean()), 1)}


# ------------------------------------------------------------------ L5 survival
def kaplan_meier(durations, observed):
    df = pd.DataFrame({"t": durations, "e": observed}).sort_values("t")
    times = np.sort(df.t[df.e == 1].unique())
    s, out, n_at = 1.0, [(0, 1.0)], len(df)
    for t in times:
        d = ((df.t == t) & (df.e == 1)).sum()
        at_risk = (df.t >= t).sum()
        s *= 1 - d / at_risk
        out.append((t, s))
    return pd.DataFrame(out, columns=["t", "s"])


def survival(k):
    r = k["rfis"].copy()
    raised = pd.to_datetime(r.raised_date)
    ans = pd.to_datetime(r.answered_date)
    r["observed"] = ans.notna().astype(int)
    r["t"] = np.where(r.observed == 1, (ans - raised).dt.days, (DATA_DATE - raised).dt.days)
    fig, ax = plt.subplots(figsize=(8, 4.2))
    res = {}
    for pr, c in [("High", O), ("Medium", Y), ("Low", B)]:
        sub = r[r.priority == pr]
        km = kaplan_meier(sub.t.values, sub.observed.values)
        ax.step(km.t, 1 - km.s, where="post", color=c, label=f"{pr} (n={len(sub)})")
        target = {"High": 5, "Medium": 10, "Low": 14}[pr]
        p_by_target = 1 - km[km.t <= target].s.iloc[-1]
        med = km[km.s <= 0.5].t.iloc[0] if (km.s <= 0.5).any() else None
        res[pr] = {"n": len(sub), "censored": int((sub.observed == 0).sum()), "answered_by_target_pct": round(100 * p_by_target, 1),
                   "target_days": target, "median_days": int(med) if med is not None else None,
                   "p90_days": int(km[km.s <= 0.1].t.iloc[0]) if (km.s <= 0.1).any() else None}
        ax.axvline(target, color=c, linestyle=":", linewidth=0.9)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0, decimals=0))
    ax.set_xlim(0, 45), ax.set_xlabel("Days since raised"), ax.set_ylabel("Share answered")
    ax.legend(loc="lower right")
    ax.set_title("RFI time to answer (Kaplan-Meier, open RFIs censored); dotted = target")
    save(fig, "L5_rfi_survival")
    # Log-rank style comparison via Mann-Whitney is not censoring-aware; report naive bias instead
    naive = r[r.observed == 1].groupby("priority").t.median().to_dict()
    table(pd.DataFrame(res).T.reset_index(names="priority"), "L5_survival_by_priority")
    R["L5"] = {"by_priority": res, "open_censored": int((r.observed == 0).sum()), "naive_median": {k_: float(v) for k_, v in naive.items()}}


# ------------------------------------------------------------------ L6 predictive model
def late_delivery_model(k):
    po = k["purchase_orders"].copy()
    for c in ["po_date", "promised_date", "delivered_date"]:
        po[c] = pd.to_datetime(po[c])
    po = po.sort_values("po_date").reset_index(drop=True)
    po["late"] = (po.delivered_date > po.promised_date).astype(float).where(po.delivered_date.notna())
    # Leakage-safe supplier history: only POs from the same supplier that were already delivered
    # before this PO was placed.
    hist_n, hist_rate = [], []
    for i, row in po.iterrows():
        prior = po[(po.supplier_id == row.supplier_id) & (po.delivered_date < row.po_date)]
        hist_n.append(len(prior))
        hist_rate.append((prior.late.sum() + 1) / (len(prior) + 5))  # smoothed toward ~20%
    po["supplier_prior_pos"] = hist_n
    po["supplier_prior_late_rate"] = hist_rate
    po["log_value"] = np.log10(po.po_value)
    po["lead_days"] = (po.promised_date - po.po_date).dt.days
    po["month_index"] = (po.po_date - pd.Timestamp("2024-01-01")).dt.days / 30.44
    # Leaky feature for comparison: supplier late rate over ALL POs, including future ones
    po["supplier_late_rate_LEAKY"] = po.groupby("supplier_id").late.transform("mean")
    cats = pd.get_dummies(po.category, prefix="cat", dtype=float)
    feats = ["log_value", "lead_days", "supplier_prior_pos", "supplier_prior_late_rate", "month_index"]
    X = pd.concat([po[feats], cats], axis=1)
    lab = po.late.notna()
    cutoff = pd.Timestamp("2025-10-01")
    tr = lab & (po.po_date < cutoff)
    te = lab & (po.po_date >= cutoff)
    y = po.late
    logit = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=0.5)).fit(X[tr], y[tr])
    gbm = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=300, random_state=0).fit(X[tr], y[tr])
    Xl = X.assign(leaky=po.supplier_late_rate_LEAKY)
    leaky = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=300, random_state=0).fit(Xl[tr], y[tr])
    p_log, p_gbm, p_leak = logit.predict_proba(X[te])[:, 1], gbm.predict_proba(X[te])[:, 1], leaky.predict_proba(Xl[te])[:, 1]
    auc = {"Logistic regression": roc_auc_score(y[te], p_log), "Gradient boosting": roc_auc_score(y[te], p_gbm),
           "Gradient boosting with LEAKY feature": roc_auc_score(y[te], p_leak)}
    best = max(["Logistic regression", "Gradient boosting"], key=auc.get)
    p_best = p_log if best == "Logistic regression" else p_gbm
    yt = y[te].values
    order = np.argsort(-p_best)
    top = order[: int(len(order) * 0.2)]
    base_rate, top_rate = yt.mean(), yt[top].mean()
    capture = yt[top].sum() / yt.sum()

    fig, ax = plt.subplots(figsize=(6.5, 5))
    for (name, p), c in zip([("Logistic regression", p_log), ("Gradient boosting", p_gbm),
                             ("Gradient boosting with LEAKY feature", p_leak)], [B, A, O]):
        fpr, tpr, _ = roc_curve(yt, p)
        ax.plot(fpr, tpr, color=c, linestyle=":" if "LEAKY" in name else "-", label=f"{name} (AUC {auc[name]:.2f})")
    ax.plot([0, 1], [0, 1], color=N, linestyle="--", linewidth=1)
    ax.set_xlabel("False positive rate"), ax.set_ylabel("True positive rate")
    ax.legend(loc="lower right", fontsize=8)
    ax.set_title("Late delivery model: holdout ROC (POs from Oct 2025)")
    save(fig, "L6_roc")

    model = logit if best == "Logistic regression" else gbm
    pi = permutation_importance(model, X[te], y[te], scoring="roc_auc", n_repeats=20, random_state=0)
    imp = pd.Series(pi.importances_mean, index=X.columns)
    grouped = pd.Series({f: imp[f] for f in feats})
    grouped["category (all dummies)"] = imp[[c for c in X.columns if c.startswith("cat_")]].sum()
    grouped = grouped.sort_values()
    fig, ax = plt.subplots(figsize=(7, 3.8))
    ax.barh(grouped.index, grouped.values, color=[B if v > 0.005 else N for v in grouped.values], height=0.6)
    ax.set_xlabel("Drop in holdout AUC when feature is shuffled"), ax.grid(axis="y", visible=False)
    ax.set_title(f"What drives late delivery ({best}, permutation importance)")
    save(fig, "L6_feature_importance")

    po_te = po[te].assign(late_risk=p_best)
    table(po_te.sort_values("late_risk", ascending=False).head(25)[
        ["po_no", "supplier_id", "category", "po_date", "po_value", "lead_days", "supplier_prior_late_rate", "late_risk", "late"]].round({"supplier_prior_late_rate": 3, "late_risk": 3}),
        "L6_highest_risk_pos")
    R["L6"] = {"train_n": int(tr.sum()), "test_n": int(te.sum()), "cutoff": cutoff.strftime("%d %b %Y"),
               "auc": {k_: round(v, 3) for k_, v in auc.items()}, "best": best, "base_rate": round(base_rate, 3),
               "top20_rate": round(top_rate, 3), "lift": round(top_rate / base_rate, 2), "capture_top20": round(capture, 3),
               "importance": grouped.sort_values(ascending=False).round(3).to_dict()}


# ------------------------------------------------------------------ L7 unsupervised
def unsupervised(k):
    s = k["supplier_rfmt"].copy()
    s["log_monetary"] = np.log10(s.monetary)
    s["otd"] = s.otd_pct.fillna(s.otd_pct.median())
    f = ["recency_days", "frequency", "log_monetary", "tenure_days", "otd"]
    Z = StandardScaler().fit_transform(s[f])
    sil = {kk: silhouette_score(Z, KMeans(kk, n_init=20, random_state=0).fit_predict(Z)) for kk in range(2, 7)}
    kbest = max([3, 4], key=sil.get)
    km = KMeans(kbest, n_init=20, random_state=0).fit(Z)
    s["cluster"] = km.labels_
    prof = s.groupby("cluster").agg(suppliers=("supplier_id", "count"), median_spend_musd=("monetary", lambda v: v.median() / 1e6),
                                    median_pos=("frequency", "median"), median_recency_days=("recency_days", "median"),
                                    median_tenure_days=("tenure_days", "median"), mean_otd_pct=("otd", "mean")).round(1)
    # Name clusters from their profile
    names = {}
    for c, row in prof.iterrows():
        if row.median_spend_musd == prof.median_spend_musd.max():
            names[c] = "Core high-volume"
        elif row.mean_otd_pct == prof.mean_otd_pct.min():
            names[c] = "Delivery risk"
        elif row.median_recency_days == prof.median_recency_days.max():
            names[c] = "Inactive"
        else:
            names[c] = "Steady mid-tier"
    s["cluster_name"] = s.cluster.map(names)
    prof.insert(0, "cluster_name", prof.index.map(names))
    table(prof.reset_index(), "L7_cluster_profiles")
    xt = pd.crosstab(s.cluster_name, s.segment)
    table(xt.reset_index(), "L7_cluster_vs_rfmt")

    pc = PCA(2).fit_transform(Z)
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    for i, (c, nm) in enumerate(sorted(names.items())):
        sel = s.cluster == c
        ax.scatter(pc[sel, 0], pc[sel, 1], s=30, color=style.SERIES[i], marker="os^D"[i], edgecolors=style.SURFACE, linewidths=0.8,
                   label=f"{nm} ({sel.sum()})")
    ax.set_xlabel("Principal component 1"), ax.set_ylabel("Principal component 2")
    ax.legend(loc="best", fontsize=8)
    ax.set_title(f"Supplier clusters (k-means, k={kbest}, silhouette {sil[kbest]:.2f})")
    save(fig, "L7_supplier_clusters")

    po = k["purchase_orders"].copy()
    po["lead_days"] = (pd.to_datetime(po.promised_date) - pd.to_datetime(po.po_date)).dt.days
    po["log_value"] = np.log10(po.po_value)
    po["value_vs_cat"] = po.log_value - po.groupby("category").log_value.transform("median")
    po["lead_vs_cat"] = po.lead_days / po.groupby("category").lead_days.transform("median")
    feats = ["log_value", "lead_days", "value_vs_cat", "lead_vs_cat"]
    iso = IsolationForest(n_estimators=300, contamination=0.01, random_state=0).fit(po[feats])
    po["anomaly_score"] = -iso.score_samples(po[feats])
    po["anomaly"] = iso.predict(po[feats]) == -1
    out = po[po.anomaly].sort_values("anomaly_score", ascending=False)
    table(out[["po_no", "supplier_id", "category", "po_value", "lead_days", "value_vs_cat", "lead_vs_cat", "anomaly_score"]].round(3), "L7_po_anomalies")
    fig, ax = plt.subplots(figsize=(7.5, 4.4))
    ax.scatter(po.lead_days[~po.anomaly], po.po_value[~po.anomaly] / 1e6, s=10, color=N, alpha=0.6, label="Normal")
    ax.scatter(out.lead_days, out.po_value / 1e6, s=40, color=O, edgecolors=style.SURFACE, linewidths=1, label=f"Flagged ({len(out)})")
    ax.set_yscale("log"), ax.set_xlabel("Promised lead time (days)"), ax.set_ylabel("PO value ($M, log scale)")
    ax.legend(loc="lower right")
    ax.set_title("Purchase order anomalies (isolation forest, top 1%)")
    save(fig, "L7_po_anomalies")
    R["L7"] = {"silhouette": {int(a): round(b, 3) for a, b in sil.items()}, "k": kbest,
               "clusters": prof.reset_index().to_dict("records"), "anomalies": len(out),
               "anomaly_examples": out.head(3)[["po_no", "category", "po_value", "lead_days"]].to_dict("records")}


# ------------------------------------------------------------------ L8 prescriptive
def prescriptive(k):
    d = k["engineering_documents"].dropna(subset=["first_return_code"])
    others = d[~d.discipline.isin(["Piping", "I&C"])]
    base_c3 = (others.first_return_code == "Code 3").mean()
    pi_ = d[d.discipline.isin(["Piping", "I&C"])]
    excess = (pi_.first_return_code == "Code 3").sum() - base_c3 * len(pi_)
    avg_resub = d[d.first_return_code == "Code 3"].resubmittals.mean()

    ev = k["ev_monthly"]
    cur = ev[ev.month.astype(str) == "2026-06-30"].merge(k["control_accounts"], on="control_account")
    fab = cur[cur.area == "FAB"]
    cpi_fab = fab.ev.sum() / fab.ac.sum()
    rem_fab = (fab.bac - fab.ev).sum()
    saving = rem_fab / cpi_fab - rem_fab / min(cpi_fab + 0.02, 1.0)
    R["L8"] = {
        "excess_code3": int(round(excess)), "resubmittal_cycles_avoided": int(round(excess * avg_resub)),
        "base_code3_pct": round(100 * base_c3, 1), "pi_code3_pct": round(100 * (pi_.first_return_code == "Code 3").mean(), 1),
        "fab_cpi": round(cpi_fab, 3), "fab_remaining_busd": round(rem_fab / 1e9, 2), "fab_saving_musd": round(saving / 1e6),
    }


def main():
    style.apply()
    FIG.mkdir(parents=True, exist_ok=True)
    TAB.mkdir(parents=True, exist_ok=True)
    k = kpis.load()
    for step in (profile, diagnostics, earned_schedule, monte_carlo, survival, late_delivery_model, unsupervised, prescriptive):
        step(k)
        print("done", step.__name__)
    (ROOT / "analysis" / "results.json").write_text(json.dumps(R, indent=2, default=str))


if __name__ == "__main__":
    main()
