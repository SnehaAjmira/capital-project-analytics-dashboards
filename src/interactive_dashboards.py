"""Builds interactive HTML dashboards (Plotly) into docs/ for GitHub Pages."""
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

import style

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
B, O, A, Y, N = style.SERIES[0], style.SERIES[1], style.SERIES[2], style.SERIES[3], style.NEUTRAL
FONT = "-apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif"

PAGES = [
    ("project-controls", "1. Project Controls", "Earned value, S-curve, CPI/SPI, EAC"),
    ("engineering", "2. Engineering and Document Control", "Deliverable progress, first-time approval, overdue"),
    ("rfi", "3. RFI Management", "Flow, Pareto, response performance, aging"),
    ("procurement", "4. Procurement and Supplier RFMT", "Spend Pareto, ABC, RFMT segments, on-time delivery"),
    ("quality", "5. Quality and Completion", "Punch Pareto, burndown forecast, Category A, NCRs"),
]

CSS = f"""
body{{margin:0;background:{style.SURFACE};color:{style.TEXT};font-family:{FONT}}}
header{{padding:20px 28px 8px;display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:8px}}
h1{{font-size:22px;margin:0}} .note{{color:{style.TEXT_2};font-size:12px}}
nav{{padding:0 28px 12px;display:flex;gap:16px;flex-wrap:wrap;font-size:13px}}
nav a{{color:{B};text-decoration:none}} nav a.active{{font-weight:700;color:{style.TEXT}}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;padding:0 28px}}
.kpi{{background:#fff;border:1px solid {style.GRID};border-radius:6px;padding:12px 14px}}
.kpi .l{{font-size:12px;color:{style.TEXT_2}}} .kpi .v{{font-size:24px;font-weight:700;margin:4px 0}}
.kpi .s{{font-size:11px;color:{style.TEXT_2}}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(520px,1fr));gap:16px;padding:16px 28px 28px}}
.card{{background:#fff;border:1px solid {style.GRID};border-radius:6px;padding:8px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px;padding:8px 28px 28px}}
.cards a{{display:block;background:#fff;border:1px solid {style.GRID};border-radius:6px;padding:12px;color:{style.TEXT};text-decoration:none}}
.cards img{{width:100%;border-radius:4px;border:1px solid {style.GRID}}} .cards h3{{margin:8px 0 4px;font-size:15px}}
.cards p{{margin:0;font-size:12px;color:{style.TEXT_2}}}
"""


def layout(fig, title, ytitle=None, yfmt=None, h=360):
    fig.update_layout(
        title=dict(text=title, x=0.01, font=dict(size=14)), height=h, template="simple_white",
        font=dict(family=FONT, size=12, color=style.TEXT), paper_bgcolor="#fff", plot_bgcolor="#fff",
        margin=dict(l=60, r=20, t=70, b=50), legend=dict(orientation="h", y=1.12, x=0),
        hoverlabel=dict(bgcolor="#fff"), hovermode="x unified" if fig.data and fig.data[0].type == "scatter" else "closest",
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor=style.GRID, showgrid=True, title=ytitle, tickformat=yfmt)
    return fig


def pareto(labels, share, cum, title, bar_name):
    f = go.Figure()
    f.add_bar(x=labels, y=share, name=bar_name, marker_color=B, hovertemplate="%{y:.1f}%<extra></extra>")
    f.add_scatter(x=labels, y=cum, name="Cumulative share", line=dict(color=O, width=2), mode="lines+markers",
                  hovertemplate="%{y:.1f}%<extra></extra>")
    f.add_hline(y=80, line_dash="dash", line_color=style.TEXT_2, line_width=1)
    return layout(f, title, yfmt=".0f", h=380).update_yaxes(range=[0, 105], ticksuffix="%")


def hbar(y, x, title, colors, text=None, suffix="", vline=None):
    f = go.Figure(go.Bar(y=y, x=x, orientation="h", marker_color=colors, text=text, textposition="outside",
                         hovertemplate=f"%{{y}}: %{{x:.1f}}{suffix}<extra></extra>"))
    if vline is not None:
        f.add_vline(x=vline, line_dash="dash", line_color=style.TEXT_2, line_width=1)
    f = layout(f, title, h=380)
    f.update_xaxes(showgrid=True, gridcolor=style.GRID, ticksuffix=suffix, range=[0, float(max(x)) * 1.45])
    f.update_yaxes(showgrid=False)
    return f


def page(slug, title, kpis, figs):
    nav = " ".join(f'<a href="{s}.html" class="{"active" if s == slug else ""}">{t}</a>' for s, t, _ in PAGES)
    cards = "".join(f'<div class="kpi"><div class="l">{l}</div><div class="v">{v}</div><div class="s">{s}</div></div>'
                    for l, v, s in kpis)
    charts = "".join(f'<div class="card">{pio.to_html(f, include_plotlyjs=False, full_html=False, config={"displaylogo": False})}</div>'
                     for f in figs)
    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} | EPC Project Analytics</title><script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script><style>{CSS}</style></head>
<body><header><h1>{title}</h1><span class="note">Synthetic data for demonstration. Data date: 30 Jun 2026. <a href="index.html">All dashboards</a> | <a href="analysis-report.html">Analysis report</a></span></header>
<nav>{nav}</nav><section class="kpis">{cards}</section><section class="grid">{charts}</section></body></html>"""
    (DOCS / f"{slug}.html").write_text(html, encoding="utf-8")


def index():
    cards = "".join(f'<a href="{s}.html"><img src="img/{i + 1:02d}.png" alt="{t}"><h3>{t}</h3><p>{d}</p></a>'
                    for i, (s, t, d) in enumerate(PAGES))
    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>EPC Project Analytics Dashboards</title><style>{CSS}</style></head><body>
<header><h1>EPC Project Analytics Dashboards</h1><span class="note">Semiconductor fab EPC project. Synthetic data. Data date: 30 Jun 2026.</span></header>
<nav><a href="analysis-report.html">Advanced analysis report (8 levels, descriptive to predictive)</a> <a href="https://github.com/SnehaAjmira/epc-project-analytics-dashboards">Source code and SQL</a></nav>
<section class="cards">{cards}</section></body></html>"""
    (DOCS / "index.html").write_text(html, encoding="utf-8")


def build_all(k):
    DOCS.mkdir(exist_ok=True)
    (DOCS / "img").mkdir(exist_ok=True)
    static = ROOT / "dashboards" / "static"
    for i, src in enumerate(sorted(static.glob("*.png")), start=1):
        (DOCS / "img" / f"{i:02d}.png").write_bytes(src.read_bytes())
    (DOCS / ".nojekyll").write_text("")

    # 1. Project controls
    m, a = k["pc_monthly"], k["pc_by_area"]
    cur = m.dropna(subset=["ev"]).iloc[-1]
    bac = k["control_accounts"].bac.sum()
    eac = bac / cur.cpi
    f1 = go.Figure()
    for col, name, color, dash in [("pv", "Planned value", N, "dash"), ("ev", "Earned value", B, None), ("ac", "Actual cost", O, None)]:
        f1.add_scatter(x=m.month, y=m[col] / 1e9, name=name, line=dict(color=color, width=2, dash=dash),
                       hovertemplate="$%{y:.2f}B")
    f1 = layout(f1, "Cumulative S-curve ($B)", yfmt="$.1f")
    t = m.dropna(subset=["ev"]).query("month >= '2024-07-01'")
    f2 = go.Figure([go.Scatter(x=t.month, y=t.cpi, name="CPI", line=dict(color=B, width=2), hovertemplate="%{y:.3f}"),
                    go.Scatter(x=t.month, y=t.spi, name="SPI", line=dict(color=O, width=2), hovertemplate="%{y:.3f}")])
    f2.add_hline(y=1, line_dash="dash", line_color=style.TEXT_2, line_width=1)
    f2 = layout(f2, "Performance indices (1.00 = on plan)", yfmt=".2f").update_yaxes(range=[0.85, 1.05])
    f3 = go.Figure([go.Bar(y=a.area, x=a.cv / 1e6, name="Cost variance", orientation="h", marker_color=B, hovertemplate="$%{x:,.0f}M"),
                    go.Bar(y=a.area, x=a.sv / 1e6, name="Schedule variance", orientation="h", marker_color=O, hovertemplate="$%{x:,.0f}M")])
    f3 = layout(f3, "Variance by area ($M, negative = over cost or behind)").update_yaxes(autorange="reversed", showgrid=False)
    f4 = go.Figure([go.Bar(y=a.area, x=a.bac / 1e6, name="BAC", orientation="h", marker_color=N, hovertemplate="$%{x:,.0f}M"),
                    go.Bar(y=a.area, x=a.eac / 1e6, name="EAC", orientation="h", marker_color=B, hovertemplate="$%{x:,.0f}M")])
    f4 = layout(f4, "Budget vs estimate at completion by area ($M)").update_yaxes(autorange="reversed", showgrid=False)
    page("project-controls", "1. Project Controls: Earned Value", [
        ("Budget at completion", f"${bac / 1e9:.2f}B", "BAC"), ("Earned to date", f"{cur.ev / bac:.1%}", f"Planned {cur.pv / bac:.1%}"),
        ("CPI", f"{cur.cpi:.2f}", "Earned / actual cost"), ("SPI", f"{cur.spi:.2f}", "Earned / planned"),
        ("Estimate at completion", f"${eac / 1e9:.2f}B", "EAC = BAC / CPI"), ("Variance at completion", f"-${(eac - bac) / 1e6:,.0f}M", "BAC - EAC"),
    ], [f1, f2, f3, f4])

    # 2. Engineering
    p, d, o, docs = k["eng_progress"], k["eng_by_discipline"], k["eng_overdue"], k["engineering_documents"]
    sub = docs.first_submittal_date.notna()
    g1 = go.Figure([go.Scatter(x=p.month, y=p.planned_cum, name="Planned", line=dict(color=N, dash="dash", width=2)),
                    go.Scatter(x=p.month, y=p.actual_cum, name="Submitted", line=dict(color=B, width=2)),
                    go.Scatter(x=p.month, y=p.approved_cum, name="Approved", line=dict(color=A, width=2))])
    g1 = layout(g1, "Cumulative deliverables")
    dd = d.sort_values("first_time_approval_pct")
    g2 = hbar(dd.discipline, dd.first_time_approval_pct, "First-time approval by discipline (target 70%)",
              [O if v < 60 else B for v in dd.first_time_approval_pct], [f"{v:.0f}%" for v in dd.first_time_approval_pct], "%", 70)
    dd = d.sort_values("avg_days_late")
    g3 = hbar(dd.discipline, dd.avg_days_late, "Average days late to first submittal",
              [O if v > 25 else B for v in dd.avg_days_late], [f"{v:.0f}" for v in dd.avg_days_late], " d")
    order = ["1-30 days", "31-60 days", "61-90 days", "90+ days"]
    ov = o.pivot_table(index="overdue_bucket", columns="discipline", values="documents", aggfunc="sum").reindex(order).fillna(0)
    g4 = go.Figure([go.Bar(x=ov.index, y=ov[c], name=c, hovertemplate=f"{c}: %{{y}}<extra></extra>") for c in ov.columns])
    g4 = layout(g4, "Overdue deliverables by age (hover for discipline)").update_layout(barmode="stack", showlegend=False)
    g4.update_traces(marker_color=B, marker_line_color="#fff", marker_line_width=1)
    page("engineering", "2. Engineering Deliverables and Document Control", [
        ("Deliverables", f"{len(docs):,}", "Drawings, specs, datasheets, calcs"), ("Submitted", f"{sub.mean():.1%}", f"{sub.sum():,} first submittals"),
        ("Approved", f"{docs.approved_date.notna().mean():.1%}", "Code 1 or 2, incl. resubmittals"),
        ("First-time approval", f"{(docs.first_return_code == 'Code 1').sum() / sub.sum():.1%}", "Code 1 on first review"),
        ("Overdue, not submitted", f"{int(o.documents.sum())}", "Past planned issue date"),
        ("Median review time", f"{docs.first_review_days.median():.0f} days", "Client first review"),
    ], [g1, g2, g3, g4])

    # 3. RFIs
    rm, rd, ag, r = k["rfi_monthly"], k["rfi_by_discipline"], k["rfi_aging"], k["rfis"]
    ans = r.answered_date.notna()
    r1 = go.Figure([go.Scatter(x=rm.month, y=rm.raised, name="Raised", line=dict(color=B, width=2)),
                    go.Scatter(x=rm.month, y=rm.answered, name="Answered", line=dict(color=A, width=2)),
                    go.Scatter(x=rm.month, y=rm.open_end_of_month, name="Open at month end", line=dict(color=O, width=2))])
    r1 = layout(r1, "Monthly RFI flow")
    r2 = pareto(rd.discipline, rd.share_pct, rd.share_pct.cumsum(), "Pareto: RFIs by discipline", "Share of RFIs")
    dd = rd.sort_values("on_time_pct")
    r3 = hbar(dd.discipline, dd.on_time_pct, "Answered by required date",
              [O if v < 50 else B for v in dd.on_time_pct], [f"{v:.0f}% (median {m_:.0f} d)" for v, m_ in zip(dd.on_time_pct, dd.median_response_days)], "%")
    order = ["0-7 days", "8-14 days", "15-30 days", "30+ days"]
    pv = ag.pivot_table(index="age_bucket", columns="priority", values="open_rfis", aggfunc="sum").reindex(order).fillna(0)
    r4 = go.Figure([go.Bar(x=pv.index, y=pv[c], name=c, marker_color=col, marker_line_color="#fff", marker_line_width=2)
                    for c, col in [("High", O), ("Medium", Y), ("Low", B)] if c in pv])
    r4 = layout(r4, "Open RFI aging by priority").update_layout(barmode="stack")
    resp = (pd.to_datetime(r.answered_date) - pd.to_datetime(r.raised_date)).dt.days
    page("rfi", "3. RFI Management", [
        ("RFIs raised", f"{len(r):,}", "Since Jun 2024"), ("Open", f"{(~ans).sum()}", "Awaiting response"),
        ("Answered on time", f"{(pd.to_datetime(r.answered_date) <= pd.to_datetime(r.required_date))[ans].mean():.1%}", "By required-by date"),
        ("Median response", f"{resp.median():.0f} days", "Raised to answered"),
        ("Cost impact", f"{(r.cost_impact == 'Y').mean():.1%}", f"{(r.cost_impact == 'Y').sum()} RFIs flagged"),
    ], [r1, r2, r3, r4])

    # 4. Procurement
    s, seg, par, cat, po = k["supplier_rfmt"], k["supplier_segments"], k["supplier_pareto"], k["procurement_by_category"], k["purchase_orders"]
    dl = po.delivered_date.notna()
    p1 = go.Figure()
    for cls, col in [("A", B), ("B", Y), ("C", N)]:
        sel = par[par.abc_class == cls]
        p1.add_scatter(x=100 * sel["rank"] / len(par), y=sel.cum_spend_pct, name=f"Class {cls}", mode="lines",
                       line=dict(color=col, width=3), customdata=sel[["supplier_id", "category"]],
                       hovertemplate="%{customdata[0]} (%{customdata[1]})<br>Cumulative spend %{y:.1f}%<extra></extra>")
    p1.add_hline(y=80, line_dash="dash", line_color=style.TEXT_2, line_width=1)
    p1 = layout(p1, "Spend Pareto and ABC classes").update_xaxes(title="Suppliers ranked by spend (%)", ticksuffix="%").update_yaxes(ticksuffix="%")
    p1.update_layout(hovermode="closest")
    g = s.pivot_table(index="r", columns="m", values="supplier_id", aggfunc="count").reindex(index=[5, 4, 3, 2, 1], columns=[1, 2, 3, 4, 5]).fillna(0)
    p2 = go.Figure(go.Heatmap(z=g.values, x=[f"M{c}" for c in g.columns], y=[f"R{i}" for i in g.index], colorscale="Blues",
                              text=g.values.astype(int), texttemplate="%{text}", hovertemplate="%{y} %{x}: %{z} suppliers<extra></extra>"))
    p2 = layout(p2, "RFMT grid: suppliers by recency (R) and monetary (M) score").update_xaxes(title="Monetary score (5 = highest spend)").update_yaxes(title="Recency score (5 = most recent)", showgrid=False, autorange="reversed")
    p3 = go.Figure(go.Scatter(x=s.frequency, y=s.monetary / 1e6, mode="markers", marker=dict(size=9, color=B, opacity=0.7, line=dict(color="#fff", width=1)),
                              customdata=s[["supplier_id", "segment", "rfmt_code", "otd_pct"]],
                              hovertemplate="%{customdata[0]}<br>Segment: %{customdata[1]}<br>RFMT: %{customdata[2]}<br>POs: %{x}<br>Spend: $%{y:,.1f}M<br>OTD: %{customdata[3]}%<extra></extra>"))
    p3 = layout(p3, "Suppliers: frequency vs spend (hover for RFMT segment)").update_xaxes(title="Purchase orders", showgrid=True, gridcolor=style.GRID).update_yaxes(title="Spend ($M)", type="log")
    p3.update_layout(hovermode="closest")
    cc = cat.sort_values("otd_pct")
    p4 = hbar(cc.category, cc.otd_pct, "On-time delivery by category (target 90%)", [O if v < 80 else B for v in cc.otd_pct],
              [f"{v:.0f}% (lead {l:.0f} d)" for v, l in zip(cc.otd_pct, cc.median_lead_days)], "%", 90)
    page("procurement", "4. Procurement and Supplier Performance (RFMT)", [
        ("Committed spend", f"${po.po_value.sum() / 1e9:.2f}B", f"{len(po):,} purchase orders"), ("Active suppliers", f"{len(s)}", "With at least one PO"),
        ("Class A suppliers", f"{(par.abc_class == 'A').sum()}", "80% of spend"),
        ("On-time delivery", f"{(pd.to_datetime(po.delivered_date) <= pd.to_datetime(po.promised_date))[dl].mean():.1%}", "Delivered by promised date"),
        ("Strategic segment", f"{seg.set_index('segment').loc['Strategic', 'spend_share_pct']:.0f}%", "Share of spend (RFMT)"),
    ], [p1, p2, p3, p4])

    # 5. Quality
    pp, w, sysd, ncr, fc, pi, nc = (k["punch_pareto"], k["punch_weekly"], k["punch_open_by_system"], k["ncr_pareto"],
                                    k["punch_forecast"].iloc[0], k["punch_items"], k["ncrs"])
    q1 = pareto(pp.cause, pp.pct, pp.cum_pct, "Pareto: punch items by cause", "Share of items")
    q2 = go.Figure([go.Scatter(x=w.week_end, y=w.open_items, name="Open items", line=dict(color=B, width=2)),
                    go.Scatter(x=w.week_end, y=w.open_cat_a, name="Open Category A", line=dict(color=O, width=2)),
                    go.Scatter(x=[w.week_end.iloc[-1], fc.forecast_zero_date], y=[fc.open_items, 0], name="Forecast",
                               line=dict(color=B, width=2, dash="dot"))])
    q2 = layout(q2, "Weekly punch burndown with forecast")
    sd = sysd.sort_values("open_cat_a")
    q3 = hbar(sd.system, sd.open_cat_a, "Open Category A items by system", O, [f"{a_} A | {b_} B" for a_, b_ in zip(sd.open_cat_a, sd.open_cat_b)])
    share = 100 * ncr.rework_cost_kusd / ncr.rework_cost_kusd.sum()
    q4 = pareto(ncr.cause, share, ncr.cum_cost_pct, "Pareto: NCR rework cost by cause", "Share of rework cost")
    page("quality", "5. Construction Quality and Mechanical Completion", [
        ("Punch items raised", f"{len(pi):,}", "Since Jul 2025"), ("Open punch items", f"{fc.open_items:,}", f"Cat A open: {int(w.iloc[-1].open_cat_a)}"),
        ("Net closure rate", f"{fc.net_closed_per_week:.0f} / week", "Last 8 weeks, trend"),
        ("Forecast zero open", pd.Timestamp(fc.forecast_zero_date).strftime("%b %Y"), "At current net rate"),
        ("NCRs", f"{len(nc)}", f"{nc.closed_date.isna().sum()} open"), ("NCR rework cost", f"${nc.rework_cost.sum() / 1e6:.1f}M", "All causes"),
    ], [q1, q2, q3, q4])
    index()
