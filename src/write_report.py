"""Writes REPORT.md and docs/analysis-report.html from analysis/results.json and analysis/tables."""
import json
import shutil
from pathlib import Path

import markdown
import pandas as pd

import style

ROOT = Path(__file__).resolve().parents[1]
R = json.loads((ROOT / "analysis" / "results.json").read_text())
T = ROOT / "analysis" / "tables"


def md_table(df):
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(str(v) for v in r.values) + " |")
    return "\n".join(lines)


def p(v):
    return "< 0.001" if v < 0.001 else f"{v:.3f}"


def build(fig_prefix):
    L1, L2, L3, C, P, L5, L6, L7, L8 = (R[k] for k in ["L1", "L2", "L3", "L4_cost", "L4_punch", "L5", "L6", "L7", "L8"])
    f = lambda name: f"{fig_prefix}{name}.png"
    prof = pd.DataFrame(L1["profile"])[["table", "rows", "columns", "null_cells_pct", "duplicate_keys", "date_from", "date_to"]]
    prof.columns = ["Table", "Rows", "Columns", "Null cells %", "Duplicate keys", "First date", "Last date"]
    chk = pd.DataFrame(L1["checks"]).rename(columns={"rule": "Logic rule", "violations": "Violations"})
    eac = pd.DataFrame([{"Method": k, "EAC": f"${v:.2f}B", "Variance at completion": f"-${(v - L3['bac']) * 1000:,.0f}M"}
                        for k, v in L3["eac"].items()])
    surv = pd.DataFrame([{"Priority": k, "RFIs": v["n"], "Still open (censored)": v["censored"], "Target": f"{v['target_days']} days",
                          "Answered by target": f"{v['answered_by_target_pct']}%", "Median": f"{v['median_days']} days",
                          "90% answered by": f"{v['p90_days']} days"} for k, v in L5["by_priority"].items()])
    auc = pd.DataFrame([{"Model": k, "Holdout AUC": f"{v:.3f}", "Valid?": "No: uses future information" if "LEAKY" in k else "Yes"}
                        for k, v in L6["auc"].items()])
    imp = pd.DataFrame([{"Feature": k.replace("_", " "), "AUC drop when shuffled": f"{v:.3f}"} for k, v in L6["importance"].items()])
    cl = pd.DataFrame(L7["clusters"])[["cluster_name", "suppliers", "median_spend_musd", "median_pos", "median_recency_days", "mean_otd_pct"]]
    cl.columns = ["Cluster", "Suppliers", "Median spend ($M)", "Median POs", "Days since last PO", "Mean OTD %"]
    xt = pd.read_csv(T / "L7_cluster_vs_rfmt.csv")
    anom = pd.read_csv(T / "L7_po_anomalies.csv").head(5)
    anom = pd.DataFrame({"PO": anom.po_no, "Category": anom.category, "Value": anom.po_value.map(lambda v: f"${v:,.0f}"),
                         "Lead days": anom.lead_days, "Value vs category median": anom.value_vs_cat.map(lambda v: f"{10 ** v:.1f}x")})
    rpd = L2["rfis_per_doc"]
    dr = xt.set_index("cluster_name").loc["Delivery risk"]
    dr_segments, dr_strategic = int((dr > 0).sum()), int(dr.get("Strategic", 0))
    worst = L2["worst_code3"]

    return f"""# Capital Project Analysis Report: From Descriptive to Predictive

End-to-end analysis of a semiconductor fab construction project, building from data profiling to simulation, survival analysis, and machine learning. Each level answers a harder question than the one before it.

| | |
|---|---|
| **Scope** | {L1['total_rows']:,} records across 7 tables: earned value, engineering documents, RFIs, purchase orders, punch items, NCRs |
| **Data date** | 30 Jun 2026 (month 30 of a 42-month plan) |
| **Tools** | SQL (DuckDB), Python, pandas, SciPy, scikit-learn, matplotlib |
| **Data** | Synthetic. Generated from a fixed seed; no real project, client, or company data. |
| **Reproduce** | `python src/advanced_analysis.py && python src/write_report.py` |

---

## Executive Summary

| # | Finding | Level |
|---|---|---|
| 1 | The project is about {L3['at_months'] - L3['es_months']:.1f} months behind schedule. Earned schedule forecasts completion in **{L3['finish_forecast']}** vs a planned {L3['finish_planned']}. | 3 |
| 2 | Simulated cost at completion is **${C['p50']:.2f}B (P50)** to ${C['p90']:.2f}B (P90) against a ${C['bac']:.2f}B budget. The chance of finishing within budget is under 1%. A P80 contingency of **${C['contingency_p80_musd']}M** is needed. | 4 |
| 3 | The punch list is likely to clear by **{P['p50']} (P50)**, {P['p80']} at P80, about {(pd.Timestamp(P['linear']) - pd.Timestamp(P['p50'])).days // 30} months earlier than the straight-line forecast, because new items are already tapering. If new items do not taper, the P50 slips to {P['no_taper_p50']}. | 4 |
| 4 | Only {L5['by_priority']['High']['answered_by_target_pct']}% of high-priority RFIs are answered within the 5-day target, the worst of the three priorities. | 5 |
| 5 | A supplier's own delivery history is the strongest predictor of a late PO, but the signal is modest (AUC {L6['auc'][L6['best']]:.2f}). The riskiest 20% of POs are late {L6['lift']}x as often as average. | 6 |
| 6 | Clustering finds a **"Delivery risk"** group of {next(c['suppliers'] for c in L7['clusters'] if c['cluster_name'] == 'Delivery risk')} suppliers with {next(c['mean_otd_pct'] for c in L7['clusters'] if c['cluster_name'] == 'Delivery risk'):.0f}% on-time delivery that the rule-based RFMT segments spread across {dr_segments} groups, including {dr_strategic} Strategic suppliers. | 7 |

## Analysis Roadmap

| Level | Question | Method |
|---|---|---|
| 1. Data profiling | Can the data be trusted? | Completeness, uniqueness, and logic checks |
| 2. Diagnostic statistics | Are the differences we see real or noise? | Chi-square with Cramer's V, Kruskal-Wallis, Mann-Whitney, Spearman |
| 3. Advanced earned value | When will the project finish, and what will it cost? | Earned schedule (SPI(t)), three EAC methods |
| 4. Simulation | How uncertain are those forecasts? | Monte Carlo: bootstrapped CPI by control account; punch list burndown with uncertain taper |
| 5. Survival analysis | How long do RFIs really take, counting ones still open? | Kaplan-Meier with right-censoring |
| 6. Predictive modeling | Which new POs will be delivered late? | Logistic regression vs gradient boosting, leakage-safe features, time-based split, permutation importance |
| 7. Unsupervised learning | Are there supplier groups or POs the rules miss? | K-means with silhouette selection, PCA, isolation forest |
| 8. Prescriptive | Where should management act first? | What-if scenarios quantified from Levels 2 to 7 |

---

## Level 1. Data Profiling and Quality

**Question:** Is the data complete, unique, and logically consistent enough to analyze?

{md_table(prof)}

{md_table(chk)}

**Result:** No duplicate keys and no logic violations. Null cells are expected: unanswered RFIs, undelivered POs, open punch items, and future months with no earned value yet. These nulls carry meaning and are handled explicitly in later levels (for example, as censored records in Level 5).

## Level 2. Diagnostic Statistics

**Question:** Are the discipline differences on the dashboards statistically real?

| Test | Hypothesis | Statistic | p-value | Conclusion |
|---|---|---|---|---|
| Chi-square | First-review return code is independent of discipline | chi2 = {L2['chi2']}, df = {L2['chi2_dof']}, Cramer's V = {L2['cramers_v']} | {p(L2['chi2_p'])} | Real but modest association |
| Kruskal-Wallis | RFI response time is the same across disciplines | H = {L2['kw_h']} | {p(L2['kw_p'])} | Response times differ by discipline |
| Mann-Whitney (one-sided) | High-priority RFIs are answered faster than Low | Medians {L2['median_high']:.0f} vs {L2['median_low']:.0f} days | {p(L2['mw_p'])} | Priority is respected |
| Spearman | Disciplines with lower first-time approval raise more RFIs per document | rho = {L2['spearman_rho']} | {p(L2['spearman_p'])} | Not significant (n = 8 disciplines) |

![Chi-square residuals]({f('L2_chi_square_residuals')})

**Result:** Piping (+{worst['Piping']}) and I&C (+{worst['I&C']}) receive far more "revise and resubmit" (Code 3) returns than expected. With only 8 disciplines, the link between design quality and field RFIs cannot be confirmed; it should be retested at the drawing level, where the sample is much larger.

## Level 3. Advanced Earned Value: Earned Schedule

**Question:** Cost-based SPI drifts toward 1.00 late in every project and stops measuring schedule. When will this project actually finish?

Earned schedule (ES) finds the date on which today's earned value was planned to be reached.

| Measure | Value |
|---|---|
| Actual time (AT) | {L3['at_months']} months |
| Earned schedule (ES) | {L3['es_months']} months |
| SPI(t) = ES / AT | {L3['spi_t']} (cost-based SPI: {L3['spi_cost']}) |
| Forecast duration = planned / SPI(t) | {L3['ieac_t_months']} months vs {L3['planned_duration']} planned |
| Forecast completion | **{L3['finish_forecast']}** (planned {L3['finish_planned']}, slip {L3['slip_months']} months) |

![Earned schedule]({f('L3_earned_schedule')})

{md_table(eac)}

**Result:** The three EAC methods span ${min(L3['eac'].values()):.2f}B to ${max(L3['eac'].values()):.2f}B. The composite method is the most conservative because it assumes the schedule delay also costs money. Level 4 replaces this single-point range with a probability distribution.

## Level 4. Monte Carlo Simulation

### 4.1 Cost at completion

**Method:** For each of the 32 control accounts, future cost performance is resampled from that account's own last 12 monthly CPIs, plus a shared project-wide shock so accounts move together. {C['runs']:,} runs.

| Percentile | Estimate at completion |
|---|---|
| P10 | ${C['p10']:.2f}B |
| P50 | ${C['p50']:.2f}B |
| P80 | ${C['p80']:.2f}B |
| P90 | ${C['p90']:.2f}B |
| Budget (BAC) | ${C['bac']:.2f}B |
| Probability of finishing within budget | {100 * C['prob_within_bac']:.1f}% |

![EAC Monte Carlo]({f('L4_eac_monte_carlo')})

### 4.2 Punch list completion

**Method:** Each simulated week draws raised and closed counts from the last 12 weeks (average {P['recent_raised_per_week']} raised and {P['recent_closed_per_week']} closed per week). New items taper as construction finishes, and the taper rate itself is uncertain (0% to 4% per week, drawn per run). {P['runs']:,} runs.

| Scenario | P50 | P80 | P90 |
|---|---|---|---|
| Base (uncertain taper) | {P['p50']} | {P['p80']} | {P['p90']} |
| No taper (new items continue at current rate) | {P['no_taper_p50']} | {P['no_taper_p80']} | |
| Closure rate +20% | {P['faster_p50']} | {P['faster_p80']} | |
| Straight-line trend (dashboard forecast) | {P['linear']} | | |

![Punch simulation]({f('L4_punch_simulation')})

**Result:** The straight-line forecast on the dashboard is close to the no-taper scenario, so it is a pessimistic view. The simulation gives a range instead of one date and shows which assumption matters most: whether new punch items keep tapering.

## Level 5. Survival Analysis: RFI Time to Answer

**Question:** How long do RFIs take, when {L5['open_censored']} RFIs are still open?

Averaging only answered RFIs ignores the open ones, which are often the slowest. Kaplan-Meier treats open RFIs as censored: they count as "not yet answered" for as long as they have been open.

{md_table(surv)}

![RFI survival]({f('L5_rfi_survival')})

**Result:** High-priority RFIs are answered fastest in absolute days, but only {L5['by_priority']['High']['answered_by_target_pct']}% meet their 5-day target, the lowest attainment of any priority. The 5-day target and actual practice are misaligned: either the target needs resourcing or it needs resetting.

## Level 6. Predictive Model: Late Purchase Order Delivery

**Question:** When a PO is placed, can we predict whether it will be delivered late?

| Design choice | Detail |
|---|---|
| Label | Delivered after promised date (POs with a delivery date only) |
| Features | PO value (log), promised lead time, category, month, supplier's prior PO count, supplier's prior late rate |
| Leakage control | Supplier history uses only POs already **delivered before** the new PO was placed |
| Validation | Time-based split: train on POs before {L6['cutoff']} ({L6['train_n']}), test on later POs ({L6['test_n']}) |

{md_table(auc)}

![ROC curves]({f('L6_roc')})

{md_table(imp)}

![Feature importance]({f('L6_feature_importance')})

**Result:** The best valid model is {L6['best'].lower()} (AUC {L6['auc'][L6['best']]:.3f}). The simpler model wins because the dataset is small. Flagging the top 20% riskiest POs catches {100 * L6['capture_top20']:.0f}% of late deliveries at a {100 * L6['top20_rate']:.1f}% late rate vs {100 * L6['base_rate']:.1f}% overall ({L6['lift']}x lift). That is enough to target expediting, not enough to automate decisions.

**Leakage lesson:** Using each supplier's late rate over all POs, including future ones, raises AUC to {L6['auc']['Gradient boosting with LEAKY feature']:.2f}. That model looks better but would fail in production, because the future is not known when a PO is placed.

## Level 7. Unsupervised Learning

### 7.1 Supplier clustering

**Method:** K-means on standardized recency, frequency, log spend, tenure, and on-time delivery. k was chosen from 3 or 4 by silhouette score (k = {L7['k']}, silhouette {L7['silhouette'][str(L7['k'])]:.2f}). Scores for k = 2 to 6 ranged from {min(L7['silhouette'].values()):.2f} to {max(L7['silhouette'].values()):.2f}, so the clusters overlap and should be read as tendencies.

{md_table(cl)}

![Supplier clusters]({f('L7_supplier_clusters')})

**Cluster vs RFMT segment (supplier counts):**

{md_table(xt)}

**Result:** RFMT rules segment on buying behavior only. Adding delivery performance surfaces a "Delivery risk" cluster that spans {dr_segments} of the 5 RFMT segments, including {dr_strategic} Strategic suppliers. A supplier can be Strategic by spend and still be a delivery risk.

### 7.2 Purchase order anomaly detection

**Method:** Isolation forest on PO value, lead time, and both measured relative to the category median. Top 1% flagged ({L7['anomalies']} POs).

{md_table(anom)}

![PO anomalies]({f('L7_po_anomalies')})

**Result:** Flagged POs combine unusual value with unusual lead time for their category. These are candidates for a commercial review (price check, scope check, or data entry error), not proof of a problem.

## Level 8. Prescriptive: Where to Act First

| # | Action | Evidence | Quantified effect |
|---|---|---|---|
| 1 | Add a design-review checkpoint for Piping and I&C before client submittal | Level 2: Code 3 rate {L8['pi_code3_pct']}% vs {L8['base_code3_pct']}% elsewhere | About {L8['excess_code3']} fewer Code 3 returns and {L8['resubmittal_cycles_avoided']} fewer resubmittal cycles at the other disciplines' rate |
| 2 | Hold P80 cost contingency of ${C['contingency_p80_musd']}M | Level 4: P80 EAC ${C['p80']:.2f}B | Funds the overrun in 80% of simulated outcomes |
| 3 | Target FAB productivity first | Level 3: FAB CPI {L8['fab_cpi']}, ${L8['fab_remaining_busd']}B of work remaining | Each +0.02 CPI on remaining FAB work saves about ${L8['fab_saving_musd']}M |
| 4 | Add punch closure capacity (+20%) | Level 4: closure-rate scenario | P80 completion moves from {P['p80']} to {P['faster_p80']} ({P['weeks_saved_p80']} weeks earlier) |
| 5 | Re-baseline or resource the 5-day high-priority RFI target | Level 5: {L5['by_priority']['High']['answered_by_target_pct']}% attainment | Align target with practice so it drives real escalation |
| 6 | Expedite the top 20% of POs by predicted late risk, prioritizing the "Delivery risk" cluster | Levels 6 and 7 | Covers {100 * L6['capture_top20']:.0f}% of late deliveries with 20% of expediting effort |

## Method Notes

- All figures and tables are generated by `src/advanced_analysis.py`; this report is generated from its output by `src/write_report.py`, so numbers cannot drift from the code.
- Random seeds are fixed, so the simulations and models reproduce exactly.
- Because the data is synthetic, some patterns (for example Piping and I&C performance) were built into the generator. The value of this report is the method: each technique would be applied the same way to real project data.
"""


def main():
    (ROOT / "REPORT.md").write_text(build("analysis/figures/"), encoding="utf-8")
    docs = ROOT / "docs"
    (docs / "analysis").mkdir(parents=True, exist_ok=True)
    for png in (ROOT / "analysis" / "figures").glob("*.png"):
        shutil.copy(png, docs / "analysis" / png.name)
    body = markdown.markdown(build("analysis/"), extensions=["tables"])
    css = f"""body{{margin:0;background:{style.SURFACE};color:{style.TEXT};font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;line-height:1.55}}
main{{max-width:980px;margin:0 auto;padding:24px 28px 60px}} h1{{font-size:28px;margin-top:8px}} h2{{margin-top:40px;border-bottom:1px solid {style.GRID};padding-bottom:6px}}
table{{border-collapse:collapse;width:100%;margin:12px 0;font-size:14px;background:#fff}} th,td{{border:1px solid {style.GRID};padding:6px 10px;text-align:left;vertical-align:top}}
th{{background:#f3f3f1}} img{{max-width:100%;border:1px solid {style.GRID};border-radius:6px;background:#fff;margin:8px 0}}
code{{background:#f0efec;padding:1px 5px;border-radius:4px}} nav{{font-size:13px;margin-bottom:8px}} nav a{{color:{style.SERIES[0]}}}"""
    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Capital Project Analysis Report</title><style>{css}</style></head><body><main>
<nav><a href="index.html">Dashboards</a> | <a href="https://github.com/SnehaAjmira/capital-project-analytics-dashboards">Source code</a></nav>{body}</main></body></html>"""
    (docs / "analysis-report.html").write_text(html, encoding="utf-8")
    print("Wrote REPORT.md and docs/analysis-report.html")


if __name__ == "__main__":
    main()
