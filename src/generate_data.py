"""
generate_data.py

Builds a SYNTHETIC dataset for a semiconductor fab construction project (engineering,
procurement and construction). All values are randomly generated from a
fixed seed. No real project, client, or company data is used.

Output: data/*.csv
Usage:  python src/generate_data.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data"
DATA_DATE = pd.Timestamp("2026-06-30")
PROJECT_START = pd.Timestamp("2024-01-01")
PROJECT_FINISH = pd.Timestamp("2027-06-30")

AREAS = {"FAB": 0.52, "CUB": 0.24, "OSB": 0.09, "YARD": 0.15}  # fab, central utility bldg, office/support, utility yard
DISCIPLINES = ["Civil", "Structural", "Architectural", "Mechanical", "Piping", "Electrical", "I&C", "Fire Protection"]
DISC_WEIGHT = np.array([0.10, 0.14, 0.06, 0.18, 0.22, 0.16, 0.09, 0.05])
SYSTEMS = ["Ultrapure Water", "Process Exhaust", "Process Cooling Water", "Cleanroom HVAC", "Electrical Distribution",
           "Bulk Gases", "Specialty Gases", "Chemical Distribution", "Fire Protection", "Wastewater Treatment"]

rng = np.random.default_rng(SEED)


def s_curve(t):
    """Cumulative fraction complete for t in [0, 1] (smooth S-shape)."""
    t = np.clip(t, 0, 1)
    return 3 * t**2 - 2 * t**3


def months(start, end):
    return pd.date_range(start, end, freq="ME")


def control_accounts():
    rows, total_bac = [], 4_800_000_000  # $4.8B construct-and-install scope
    disc_offset = dict(zip(DISCIPLINES, [0, 3, 10, 8, 8, 9, 12, 14]))   # months after start
    disc_dur = dict(zip(DISCIPLINES, [22, 30, 32, 34, 34, 34, 30, 28]))
    for area, aw in AREAS.items():
        for d, dw in zip(DISCIPLINES, DISC_WEIGHT):
            start = PROJECT_START + pd.DateOffset(months=disc_offset[d] + int(rng.integers(0, 3)))
            finish = min(start + pd.DateOffset(months=disc_dur[d]), PROJECT_FINISH)
            rows.append({
                "control_account": f"{area}-{d[:4].upper().replace('&', '')}",
                "area": area, "discipline": d,
                "bac": round(total_bac * aw * dw * rng.uniform(0.85, 1.15), -3),
                "planned_start": start.date(), "planned_finish": finish.date(),
                "spi_factor": rng.normal(0.95, 0.04), "cpi_factor": rng.normal(0.96, 0.04),
            })
    return pd.DataFrame(rows)


def ev_monthly(ca):
    rows = []
    for _, c in ca.iterrows():
        s, f = pd.Timestamp(c.planned_start), pd.Timestamp(c.planned_finish)
        dur = (f - s).days
        for m in months(PROJECT_START, PROJECT_FINISH):
            pv = c.bac * s_curve((m - s).days / dur)
            ev = ac = None
            if m <= DATA_DATE:
                drift = 1 + 0.02 * np.sin((m - PROJECT_START).days / 90)  # gentle performance drift
                ev = c.bac * s_curve((m - s).days * c.spi_factor * drift / dur)
                ac = ev / (c.cpi_factor * rng.normal(1, 0.01)) if ev > 0 else 0.0
            rows.append({"month": m.date(), "control_account": c.control_account,
                         "pv": round(pv), "ev": None if ev is None else round(ev), "ac": None if ac is None else round(ac)})
    return pd.DataFrame(rows)


def documents(n=2400):
    disc = rng.choice(DISCIPLINES, n, p=DISC_WEIGHT / DISC_WEIGHT.sum())
    area = rng.choice(list(AREAS), n, p=list(AREAS.values()))
    dtype = rng.choice(["Drawing", "Specification", "Datasheet", "Calculation", "3D Model Review"], n,
                       p=[0.58, 0.10, 0.14, 0.12, 0.06])
    planned = PROJECT_START + pd.to_timedelta(rng.beta(2.2, 2.2, n) * 960, unit="D")
    delay_scale = pd.Series(disc).map({"Piping": 26, "I&C": 30, "Electrical": 20}).fillna(14).values
    delay = rng.gamma(1.6, delay_scale) - 8
    first_sub = planned + pd.to_timedelta(delay, unit="D")
    issued = first_sub <= DATA_DATE
    review1 = np.clip(rng.gamma(4, 3.6, n), 3, 60).round()
    p_code1 = pd.Series(disc).map({"Piping": 0.48, "I&C": 0.44, "Mechanical": 0.55}).fillna(0.64).values
    u = rng.random(n)
    code = np.where(u < p_code1, "Code 1", np.where(u < p_code1 + 0.22, "Code 2", "Code 3"))
    resub = np.where(code == "Code 3", rng.integers(1, 4, n), 0)
    approved = first_sub + pd.to_timedelta(review1 + resub * rng.uniform(18, 30, n), unit="D")
    df = pd.DataFrame({
        "doc_no": [f"DOC-{i:05d}" for i in range(1, n + 1)], "discipline": disc, "area": area, "doc_type": dtype,
        "planned_issue_date": planned.date,
        "first_submittal_date": pd.Series(first_sub.date).where(issued),
        "first_review_days": pd.Series(review1).where(issued),
        "first_return_code": pd.Series(code).where(issued),
        "resubmittals": pd.Series(resub).where(issued),
        "approved_date": pd.Series(approved.date).where(issued & (approved <= DATA_DATE)),
    })
    return df


def rfis(n=1850):
    disc = rng.choice(DISCIPLINES, n, p=DISC_WEIGHT / DISC_WEIGHT.sum())
    area = rng.choice(list(AREAS), n, p=list(AREAS.values()))
    raised = PROJECT_START + pd.DateOffset(months=5) + pd.to_timedelta(rng.beta(2.2, 1.3, n) * 760, unit="D")
    priority = rng.choice(["High", "Medium", "Low"], n, p=[0.22, 0.53, 0.25])
    base = pd.Series(priority).map({"High": 5, "Medium": 9, "Low": 13}).values
    disc_mult = pd.Series(disc).map({"Piping": 1.5, "I&C": 1.4, "Electrical": 1.2}).fillna(1.0).values
    resp = np.round(rng.gamma(2.0, base * disc_mult / 2.0)) + 1
    answered = raised + pd.to_timedelta(resp, unit="D")
    keep = raised <= DATA_DATE
    df = pd.DataFrame({
        "rfi_no": [f"RFI-{i:05d}" for i in range(1, n + 1)], "discipline": disc, "area": area, "priority": priority,
        "raised_date": raised.date,
        "required_date": (raised + pd.to_timedelta(pd.Series(priority).map({"High": 5, "Medium": 10, "Low": 14}).values, unit="D")).date,
        "answered_date": pd.Series(answered.date).where(answered <= DATA_DATE),
        "cost_impact": rng.choice(["Y", "N"], n, p=[0.17, 0.83]),
        "schedule_impact": rng.choice(["Y", "N"], n, p=[0.12, 0.88]),
    })
    return df[keep].reset_index(drop=True)


def purchase_orders(n_sup=140, n_po=1600):
    cats = {"Process Piping & Valves": 1.3, "Electrical Equipment": 1.6, "HVAC & Air Handling": 1.5,
            "Exhaust & Abatement": 1.4, "UPW Systems": 1.8, "Structural Steel": 1.2, "Concrete & Rebar": 0.6,
            "Instrumentation": 0.7, "Cleanroom Systems": 1.5, "Construction Services": 0.9}
    sup = pd.DataFrame({
        "supplier_id": [f"SUP-{i:03d}" for i in range(1, n_sup + 1)],
        "category": rng.choice(list(cats), n_sup),
        "size": rng.pareto(1.3, n_sup) + 1,
        "reliability": np.clip(rng.normal(0.82, 0.1, n_sup), 0.45, 0.99),
        "first_engaged": PROJECT_START + pd.to_timedelta(rng.beta(1.2, 2.5, n_sup) * 800, unit="D"),
    })
    w = sup["size"] / sup["size"].sum()
    idx = rng.choice(n_sup, n_po, p=w)
    s = sup.iloc[idx].reset_index(drop=True)
    po_date = s.first_engaged + pd.to_timedelta(rng.uniform(0, 1, n_po) * (DATA_DATE - s.first_engaged).dt.days, unit="D")
    value = np.round(rng.lognormal(12.4, 1.25, n_po) * s.category.map(cats).values * np.sqrt(s["size"]), -2)
    lead = np.round(rng.gamma(4, s.category.map(cats).values * 20))
    promised = po_date + pd.to_timedelta(lead, unit="D")
    late = rng.random(n_po) > s.reliability
    slip = np.where(late, np.round(rng.gamma(2, 9, n_po)) + 1, -np.round(rng.uniform(0, 5, n_po)))
    delivered = promised + pd.to_timedelta(slip, unit="D")
    return pd.DataFrame({
        "po_no": [f"PO-{i:05d}" for i in range(1, n_po + 1)], "supplier_id": s.supplier_id, "category": s.category,
        "po_date": po_date.dt.date, "po_value": value, "promised_date": promised.dt.date,
        "delivered_date": pd.Series(delivered.dt.date).where(delivered <= DATA_DATE),
    }).sort_values("po_date").reset_index(drop=True)


def punch_items(n=6200):
    system = rng.choice(SYSTEMS, n)
    disc = rng.choice(["Mechanical", "Piping", "Electrical", "I&C", "Architectural", "Fire Protection"], n,
                      p=[0.18, 0.30, 0.22, 0.16, 0.08, 0.06])
    cause = rng.choice(["Incomplete work", "Installation defect", "Missing tag or label", "Damage",
                        "Documentation gap", "Wrong material", "Cleanliness"], n,
                       p=[0.34, 0.22, 0.14, 0.11, 0.09, 0.06, 0.04])
    cat = rng.choice(["A", "B"], n, p=[0.3, 0.7])
    raised = pd.Timestamp("2025-07-01") + pd.to_timedelta(rng.beta(1.8, 1.3, n) * 364, unit="D")
    close_days = np.round(rng.gamma(1.7, np.where(cat == "A", 14, 26)))
    closed = raised + pd.to_timedelta(close_days, unit="D")
    return pd.DataFrame({
        "punch_no": [f"PL-{i:05d}" for i in range(1, n + 1)], "system": system, "discipline": disc,
        "category": cat, "cause": cause, "raised_date": raised.date,
        "closed_date": pd.Series(closed.date).where(closed <= DATA_DATE),
    })


def ncrs(n=380):
    disc = rng.choice(DISCIPLINES, n, p=DISC_WEIGHT / DISC_WEIGHT.sum())
    cause = rng.choice(["Workmanship", "Supplier material defect", "Wrong revision used", "Inspection hold missed",
                        "Weld defect", "Torque or bolting", "Damage in handling"], n,
                       p=[0.31, 0.21, 0.15, 0.11, 0.10, 0.07, 0.05])
    raised = PROJECT_START + pd.DateOffset(months=8) + pd.to_timedelta(rng.uniform(0, 1, n) * 665, unit="D")
    closed = raised + pd.to_timedelta(np.round(rng.gamma(2, 12, n)), unit="D")
    return pd.DataFrame({
        "ncr_no": [f"NCR-{i:04d}" for i in range(1, n + 1)], "discipline": disc, "cause": cause,
        "raised_date": raised.date, "closed_date": pd.Series(closed.date).where(closed <= DATA_DATE),
        "rework_cost": np.round(rng.lognormal(9.6, 1.0, n), -2),
    })


def main():
    OUT.mkdir(exist_ok=True)
    ca = control_accounts()
    tables = {
        "control_accounts": ca.drop(columns=["spi_factor", "cpi_factor"]),
        "ev_monthly": ev_monthly(ca),
        "engineering_documents": documents(),
        "rfis": rfis(),
        "purchase_orders": purchase_orders(),
        "punch_items": punch_items(),
        "ncrs": ncrs(),
    }
    for name, df in tables.items():
        df.to_csv(OUT / f"{name}.csv", index=False)
        print(f"{name:<24}{len(df):>7,} rows")


if __name__ == "__main__":
    main()
