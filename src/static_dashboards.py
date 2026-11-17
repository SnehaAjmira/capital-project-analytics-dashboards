"""Renders each dashboard as one static PNG (KPI strip + 2x2 panels) for the README."""
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd

import style

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dashboards" / "static"
NOTE = "Synthetic data for demonstration. Data date: 30 Jun 2026."
BLUE, ORANGE, AQUA, YELLOW = style.SERIES[0], style.SERIES[1], style.SERIES[2], style.SERIES[3]
PCT = mtick.PercentFormatter(decimals=0)


def frame(title, kpis):
    """Figure with a title, a row of KPI tiles, and a 2x2 grid of axes."""
    fig = plt.figure(figsize=(16, 10.5))
    fig.text(0.02, 0.975, title, fontsize=18, fontweight="bold", va="top", color=style.TEXT)
    fig.text(0.98, 0.975, NOTE, fontsize=9, va="top", ha="right", color=style.TEXT_2)
    n = len(kpis)
    w = 0.96 / n
    for i, (label, value, sub) in enumerate(kpis):
        x = 0.02 + i * w
        ax = fig.add_axes([x, 0.84, w - 0.01, 0.095])
        ax.set_xticks([]), ax.set_yticks([])
        for s in ax.spines.values():
            s.set_visible(True), s.set_color(style.GRID)
        ax.set_facecolor("#ffffff")
        ax.text(0.06, 0.78, label, fontsize=9, color=style.TEXT_2, transform=ax.transAxes, va="center")
        ax.text(0.06, 0.42, value, fontsize=19, fontweight="bold", color=style.TEXT, transform=ax.transAxes, va="center")
        if sub:
            ax.text(0.06, 0.12, sub, fontsize=8, color=style.TEXT_2, transform=ax.transAxes, va="center")
    gs = fig.add_gridspec(2, 2, left=0.06, right=0.98, top=0.78, bottom=0.06, hspace=0.42, wspace=0.22)
    return fig, [fig.add_subplot(gs[i, j]) for i in range(2) for j in range(2)]


def save(fig, name):
    for ax in fig.axes:
        if isinstance(ax.xaxis.get_major_formatter(), mdates.AutoDateFormatter):
            loc = mdates.MonthLocator(bymonth=[1, 4, 7, 10])
            ax.xaxis.set_major_locator(loc)
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
            ax.tick_params(axis="x", labelsize=8)
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.png", dpi=110)
    plt.close(fig)


def money(v, unit="B"):
    return f"${v / (1e9 if unit == 'B' else 1e6):,.2f}{unit}" if unit == "B" else f"${v / 1e6:,.0f}M"


def legend_top(ax, ncol=3):
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=ncol, fontsize=8, borderaxespad=0.1)


# ---------------------------------------------------------------- 1. Project controls
def project_controls(k):
    m, a = k["pc_monthly"], k["pc_by_area"]
    cur = m.dropna(subset=["ev"]).iloc[-1]
    bac = k["control_accounts"].bac.sum()
    eac = bac / cur.cpi
    fig, ax = frame("1. Project Controls: Earned Value", [
        ("Budget at completion", money(bac), "BAC"),
        ("Earned to date", f"{cur.ev / bac:.1%}", f"Planned {cur.pv / bac:.1%}"),
        ("CPI", f"{cur.cpi:.2f}", "Earned / actual cost"),
        ("SPI", f"{cur.spi:.2f}", "Earned / planned"),
        ("Estimate at completion", money(eac), "EAC = BAC / CPI"),
        ("Variance at completion", f"-${(eac - bac) / 1e6:,.0f}M", "BAC - EAC"),
    ])
    d = pd.to_datetime(m.month)
    ax[0].plot(d, m.pv / 1e9, color=style.NEUTRAL, linestyle="--", label="Planned value")
    ax[0].plot(d, m.ev / 1e9, color=BLUE, label="Earned value")
    ax[0].plot(d, m.ac / 1e9, color=ORANGE, label="Actual cost")
    ax[0].axvline(pd.Timestamp("2026-06-30"), color=style.TEXT_2, linewidth=0.8)
    ax[0].yaxis.set_major_formatter(mtick.StrMethodFormatter("${x:.1f}B"))
    ax[0].set_title("Cumulative S-curve", pad=22), legend_top(ax[0])

    t = m.dropna(subset=["ev"]).query("month >= '2024-07-01'")
    ax[1].plot(pd.to_datetime(t.month), t.cpi, color=BLUE, label="CPI")
    ax[1].plot(pd.to_datetime(t.month), t.spi, color=ORANGE, label="SPI")
    ax[1].axhline(1, color=style.TEXT_2, linewidth=0.8, linestyle="--")
    ax[1].set_ylim(0.85, 1.05)
    ax[1].set_title("Performance indices (1.00 = on plan)", pad=22), legend_top(ax[1])

    y = np.arange(len(a))
    ax[2].barh(y + 0.2, a.cv / 1e6, 0.38, color=BLUE, label="Cost variance")
    ax[2].barh(y - 0.2, a.sv / 1e6, 0.38, color=ORANGE, label="Schedule variance")
    ax[2].set_yticks(y, a.area), ax[2].invert_yaxis()
    ax[2].xaxis.set_major_formatter(mtick.StrMethodFormatter("${x:,.0f}M"))
    ax[2].grid(axis="y", visible=False)
    ax[2].set_title("Variance by area (negative = over cost / behind)", pad=22), legend_top(ax[2])

    ax[3].barh(y + 0.2, a.bac / 1e6, 0.38, color=style.NEUTRAL, label="BAC")
    ax[3].barh(y - 0.2, a.eac / 1e6, 0.38, color=BLUE, label="EAC")
    for i, r in a.reset_index(drop=True).iterrows():
        ax[3].text(r.eac / 1e6 + 20, i - 0.2, f"-${-r.vac / 1e6:,.0f}M", va="center", fontsize=8, color=style.TEXT)
    ax[3].set_yticks(y, a.area), ax[3].invert_yaxis()
    ax[3].xaxis.set_major_formatter(mtick.StrMethodFormatter("${x:,.0f}M"))
    ax[3].grid(axis="y", visible=False)
    ax[3].set_title("Forecast at completion by area (label = overrun)", pad=22), legend_top(ax[3])
    save(fig, "01_project_controls")


# ---------------------------------------------------------------- 2. Engineering
def engineering(k):
    p, d, o, docs = k["eng_progress"], k["eng_by_discipline"], k["eng_overdue"], k["engineering_documents"]
    sub = docs.first_submittal_date.notna()
    fta = (docs.first_return_code == "Code 1").sum() / sub.sum()
    fig, ax = frame("2. Engineering Deliverables and Document Control", [
        ("Deliverables", f"{len(docs):,}", "Drawings, specs, datasheets, calcs"),
        ("Submitted", f"{sub.mean():.1%}", f"{sub.sum():,} first submittals"),
        ("Approved", f"{docs.approved_date.notna().mean():.1%}", "Code 1 or 2, incl. resubmittals"),
        ("First-time approval", f"{fta:.1%}", "Returned Code 1 on first review"),
        ("Overdue, not submitted", f"{int(o.documents.sum())}", "Past planned issue date"),
        ("Median review time", f"{docs.first_review_days.median():.0f} days", "Client first review"),
    ])
    t = pd.to_datetime(p.month)
    ax[0].plot(t, p.planned_cum, color=style.NEUTRAL, linestyle="--", label="Planned")
    ax[0].plot(t, p.actual_cum, color=BLUE, label="Submitted")
    ax[0].plot(t, p.approved_cum, color=AQUA, label="Approved")
    ax[0].yaxis.set_major_formatter(mtick.StrMethodFormatter("{x:,.0f}"))
    ax[0].set_title("Cumulative deliverables", pad=22), legend_top(ax[0])

    dd = d.sort_values("first_time_approval_pct")
    colors = [ORANGE if v < 60 else BLUE for v in dd.first_time_approval_pct]
    ax[1].barh(dd.discipline, dd.first_time_approval_pct, color=colors, height=0.6)
    ax[1].axvline(70, color=style.TEXT_2, linestyle="--", linewidth=0.8)
    ax[1].text(70.5, -0.6, "Target 70%", fontsize=8, color=style.TEXT_2)
    for i, v in enumerate(dd.first_time_approval_pct):
        ax[1].text(v + 0.8, i, f"{v:.0f}%", va="center", fontsize=8)
    ax[1].xaxis.set_major_formatter(PCT), ax[1].set_xlim(0, 85), ax[1].grid(axis="y", visible=False)
    ax[1].set_title("First-time approval by discipline (orange: below 60%)")

    dd = d.sort_values("avg_days_late")
    ax[2].barh(dd.discipline, dd.avg_days_late, color=[ORANGE if v > 25 else BLUE for v in dd.avg_days_late], height=0.6)
    for i, v in enumerate(dd.avg_days_late):
        ax[2].text(v + 0.5, i, f"{v:.0f}", va="center", fontsize=8)
    ax[2].grid(axis="y", visible=False), ax[2].set_xlabel("Days")
    ax[2].set_title("Average days late to first submittal")

    order = ["1-30 days", "31-60 days", "61-90 days", "90+ days"]
    b = o.groupby("overdue_bucket").documents.sum().reindex(order).fillna(0)
    ax[3].bar(b.index, b.values, color=[BLUE, YELLOW, ORANGE, ORANGE], width=0.55)
    for i, v in enumerate(b.values):
        ax[3].text(i, v + 0.2, f"{int(v)}", ha="center", fontsize=9)
    ax[3].grid(axis="x", visible=False)
    ax[3].set_title("Overdue deliverables by days past planned issue")
    save(fig, "02_engineering")


# ---------------------------------------------------------------- 3. RFIs
def rfis(k):
    m, d, ag, r = k["rfi_monthly"], k["rfi_by_discipline"], k["rfi_aging"], k["rfis"]
    ans = r.answered_date.notna()
    on_time = (pd.to_datetime(r.answered_date) <= pd.to_datetime(r.required_date))[ans].mean()
    resp = (pd.to_datetime(r.answered_date) - pd.to_datetime(r.raised_date)).dt.days
    fig, ax = frame("3. RFI Management", [
        ("RFIs raised", f"{len(r):,}", "Since Jun 2024"),
        ("Open", f"{(~ans).sum()}", "Awaiting response"),
        ("Answered on time", f"{on_time:.1%}", "By required-by date"),
        ("Median response", f"{resp.median():.0f} days", "Raised to answered"),
        ("Cost impact", f"{(r.cost_impact == 'Y').mean():.1%}", f"{(r.cost_impact == 'Y').sum()} RFIs flagged"),
    ])
    t = pd.to_datetime(m.month)
    ax[0].plot(t, m.raised, color=BLUE, label="Raised")
    ax[0].plot(t, m.answered, color=AQUA, label="Answered")
    ax[0].plot(t, m.open_end_of_month, color=ORANGE, label="Open at month end")
    ax[0].set_title("Monthly RFI flow", pad=22), legend_top(ax[0])

    x = np.arange(len(d))
    ax[1].bar(x, d.share_pct, color=BLUE, width=0.6, label="Share of RFIs")
    ax[1].plot(x, d.share_pct.cumsum(), color=ORANGE, marker="o", markersize=4, label="Cumulative share")
    ax[1].axhline(80, color=style.TEXT_2, linestyle="--", linewidth=0.8)
    ax[1].set_xticks(x, d.discipline, rotation=30, ha="right", fontsize=8)
    ax[1].yaxis.set_major_formatter(PCT), ax[1].set_ylim(0, 105), ax[1].grid(axis="x", visible=False)
    ax[1].set_title("Pareto: RFIs by discipline", pad=22), legend_top(ax[1], 2)

    dd = d.sort_values("on_time_pct")
    ax[2].barh(dd.discipline, dd.on_time_pct, color=[ORANGE if v < 50 else BLUE for v in dd.on_time_pct], height=0.6)
    for i, (v, md) in enumerate(zip(dd.on_time_pct, dd.median_response_days)):
        ax[2].text(v + 0.8, i, f"{v:.0f}%  (median {md:.0f} d)", va="center", fontsize=8)
    ax[2].xaxis.set_major_formatter(PCT), ax[2].set_xlim(0, 100), ax[2].grid(axis="y", visible=False)
    ax[2].set_title("Answered by required date (orange: below 50%)")

    order = ["0-7 days", "8-14 days", "15-30 days", "30+ days"]
    pv = ag.pivot_table(index="age_bucket", columns="priority", values="open_rfis", aggfunc="sum").reindex(order).fillna(0)
    bottom = np.zeros(len(pv))
    for i, pr in enumerate(["High", "Medium", "Low"]):
        if pr in pv:
            ax[3].bar(pv.index, pv[pr], bottom=bottom, color=[ORANGE, YELLOW, BLUE][i], width=0.55,
                      edgecolor=style.SURFACE, linewidth=2, label=pr)
            bottom += pv[pr].values
    ax[3].grid(axis="x", visible=False)
    ax[3].set_title("Open RFI aging by priority", pad=22), legend_top(ax[3])
    save(fig, "03_rfi")


# ---------------------------------------------------------------- 4. Procurement
def procurement(k):
    s, seg, par, cat, po = (k["supplier_rfmt"], k["supplier_segments"], k["supplier_pareto"],
                            k["procurement_by_category"], k["purchase_orders"])
    dl = po.delivered_date.notna()
    otd = (pd.to_datetime(po.delivered_date) <= pd.to_datetime(po.promised_date))[dl].mean()
    a = par[par.abc_class == "A"]
    fig, ax = frame("4. Procurement and Supplier Performance (RFMT)", [
        ("Committed spend", money(po.po_value.sum()), f"{len(po):,} purchase orders"),
        ("Active suppliers", f"{len(s)}", "With at least one PO"),
        ("Class A suppliers", f"{len(a)}", f"{len(a) / len(s):.0%} of suppliers, 80% of spend"),
        ("On-time delivery", f"{otd:.1%}", "Delivered by promised date"),
        ("Strategic segment", f"{seg.set_index('segment').loc['Strategic', 'spend_share_pct']:.0f}%",
         "Share of spend (RFMT)"),
    ])
    x = 100 * par["rank"] / len(par)
    ax[0].plot(x, par.cum_spend_pct, color=BLUE)
    for cls, c in [("A", BLUE), ("B", YELLOW), ("C", style.NEUTRAL)]:
        sel = par[par.abc_class == cls]
        ax[0].fill_between(100 * sel["rank"] / len(par), 0, sel.cum_spend_pct, color=c, alpha=0.18, label=f"Class {cls}")
    ax[0].axhline(80, color=style.TEXT_2, linestyle="--", linewidth=0.8)
    ax[0].xaxis.set_major_formatter(PCT), ax[0].yaxis.set_major_formatter(PCT)
    ax[0].set_xlabel("Suppliers ranked by spend"), ax[0].set_ylim(0, 102), ax[0].set_xlim(0, 100)
    ax[0].set_title("Spend Pareto and ABC classes", pad=22), legend_top(ax[0])

    g = s.pivot_table(index="r", columns="m", values="supplier_id", aggfunc="count").reindex(index=[5, 4, 3, 2, 1], columns=[1, 2, 3, 4, 5]).fillna(0)
    im = ax[1].imshow(g.values, cmap="Blues", aspect="auto")
    for i in range(5):
        for j in range(5):
            v = int(g.values[i, j])
            ax[1].text(j, i, v, ha="center", va="center", fontsize=9,
                       color="#ffffff" if v > g.values.max() * 0.6 else style.TEXT)
    ax[1].set_xticks(range(5), [1, 2, 3, 4, 5]), ax[1].set_yticks(range(5), [5, 4, 3, 2, 1])
    ax[1].set_xlabel("Monetary score (5 = highest spend)"), ax[1].set_ylabel("Recency score (5 = most recent)")
    ax[1].grid(False)
    ax[1].set_title("RFMT grid: suppliers by recency and spend score")

    sg = seg.sort_values("spend_share_pct")
    ax[2].barh(sg.segment, sg.spend_share_pct, color=BLUE, height=0.6)
    for i, r in enumerate(sg.itertuples()):
        ax[2].text(r.spend_share_pct + 1, i, f"{r.spend_share_pct:.1f}%  |  {r.suppliers} suppliers  |  OTD {r.avg_otd_pct:.0f}%",
                   va="center", fontsize=8)
    ax[2].xaxis.set_major_formatter(PCT), ax[2].set_xlim(0, 140), ax[2].set_xticks(range(0, 101, 20)), ax[2].grid(axis="y", visible=False)
    ax[2].set_title("RFMT segments: share of spend")

    cc = cat.sort_values("otd_pct")
    ax[3].barh(cc.category, cc.otd_pct, color=[ORANGE if v < 80 else BLUE for v in cc.otd_pct], height=0.6)
    ax[3].axvline(90, color=style.TEXT_2, linestyle="--", linewidth=0.8)
    for i, (v, ld) in enumerate(zip(cc.otd_pct, cc.median_lead_days)):
        ax[3].text(v + 0.8, i, f"{v:.0f}%  (lead {ld:.0f} d)", va="center", fontsize=8)
    ax[3].xaxis.set_major_formatter(PCT), ax[3].set_xlim(0, 115), ax[3].set_xticks(range(0, 101, 20)), ax[3].grid(axis="y", visible=False)
    ax[3].tick_params(axis="y", labelsize=8)
    ax[3].set_title("On-time delivery by category (target 90%; orange below 80%)")
    save(fig, "04_procurement_rfmt")


# ---------------------------------------------------------------- 5. Quality and completion
def quality(k):
    pp, w, sysd, ncr, f, pi, nc = (k["punch_pareto"], k["punch_weekly"], k["punch_open_by_system"], k["ncr_pareto"],
                                   k["punch_forecast"].iloc[0], k["punch_items"], k["ncrs"])
    fig, ax = frame("5. Construction Quality and Mechanical Completion", [
        ("Punch items raised", f"{len(pi):,}", "Since Jul 2025"),
        ("Open punch items", f"{f.open_items:,}", f"Cat A open: {int(w.iloc[-1].open_cat_a)}"),
        ("Net closure rate", f"{f.net_closed_per_week:.0f} / week", "Last 8 weeks, trend"),
        ("Forecast zero open", pd.Timestamp(f.forecast_zero_date).strftime("%b %Y"), "At current net rate"),
        ("NCRs", f"{len(nc)}", f"{nc.closed_date.isna().sum()} open"),
        ("NCR rework cost", f"${nc.rework_cost.sum() / 1e6:.1f}M", "All causes"),
    ])
    x = np.arange(len(pp))
    ax[0].bar(x, pp.pct, color=BLUE, width=0.6, label="Share of items")
    ax[0].plot(x, pp.cum_pct, color=ORANGE, marker="o", markersize=4, label="Cumulative share")
    ax[0].axhline(80, color=style.TEXT_2, linestyle="--", linewidth=0.8)
    ax[0].set_xticks(x, pp.cause, rotation=25, ha="right", fontsize=8)
    ax[0].yaxis.set_major_formatter(PCT), ax[0].set_ylim(0, 105), ax[0].grid(axis="x", visible=False)
    ax[0].set_title("Pareto: punch items by cause", pad=22), legend_top(ax[0], 2)

    t = pd.to_datetime(w.week_end)
    ax[1].plot(t, w.open_items, color=BLUE, label="Open items")
    ax[1].plot(t, w.open_cat_a, color=ORANGE, label="Open Category A")
    end = t.iloc[-1]
    ax[1].plot([end, pd.Timestamp(f.forecast_zero_date)], [f.open_items, 0], color=BLUE, linestyle=":", label="Forecast")
    ax[1].set_title("Weekly punch burndown with forecast", pad=22), legend_top(ax[1])

    sd = sysd.sort_values("open_cat_a")
    ax[2].barh(sd.system, sd.open_cat_a, color=ORANGE, height=0.6)
    for i, (a, b) in enumerate(zip(sd.open_cat_a, sd.open_cat_b)):
        ax[2].text(a + 0.3, i, f"{a} A  |  {b} B open", va="center", fontsize=8)
    ax[2].set_xlim(0, sd.open_cat_a.max() * 1.8), ax[2].grid(axis="y", visible=False), ax[2].tick_params(axis="y", labelsize=8)
    ax[2].set_title("Open Category A items by system (blocks turnover)")

    x = np.arange(len(ncr))
    share = 100 * ncr.rework_cost_kusd / ncr.rework_cost_kusd.sum()
    ax[3].bar(x, share, color=BLUE, width=0.6, label="Share of rework cost")
    ax[3].plot(x, ncr.cum_cost_pct, color=ORANGE, marker="o", markersize=4, label="Cumulative share")
    ax[3].axhline(80, color=style.TEXT_2, linestyle="--", linewidth=0.8)
    ax[3].set_xticks(x, ncr.cause, rotation=25, ha="right", fontsize=8)
    ax[3].yaxis.set_major_formatter(PCT), ax[3].set_ylim(0, 105), ax[3].grid(axis="x", visible=False)
    ax[3].set_title("Pareto: NCR rework cost by cause", pad=22), legend_top(ax[3], 2)
    save(fig, "05_quality_completion")


def build_all(k):
    style.apply()
    for f in (project_controls, engineering, rfis, procurement, quality):
        f(k)
