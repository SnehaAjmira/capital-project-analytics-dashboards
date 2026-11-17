"""Runs the SQL layer and returns every KPI table as a pandas DataFrame."""
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DATE = pd.Timestamp("2026-06-30")


def load():
    con = duckdb.connect()
    for path in sorted((ROOT / "sql").glob("*.sql")):
        con.execute(path.read_text())
    tables = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
    k = {t: con.execute(f"SELECT * FROM {t}").df() for t in tables}
    k["punch_forecast"] = punch_forecast(k["punch_weekly"])
    out = ROOT / "outputs" / "tables"
    out.mkdir(parents=True, exist_ok=True)
    for name in ["pc_by_area", "eng_by_discipline", "rfi_by_discipline", "supplier_segments", "supplier_rfmt",
                 "procurement_by_category", "punch_pareto", "punch_open_by_system", "ncr_pareto", "punch_forecast"]:
        k[name].to_csv(out / f"{name}.csv", index=False)
    return k


def punch_forecast(weekly, lookback=8):
    """Linear trend of open items over the last N weeks, projected to zero."""
    w = weekly.tail(lookback)
    x = np.arange(len(w))
    slope, intercept = np.polyfit(x, w.open_items, 1)
    last = weekly.iloc[-1]
    weeks_to_zero = int(np.ceil(last.open_items / -slope)) if slope < 0 else None
    zero_date = pd.Timestamp(last.week_end) + pd.Timedelta(weeks=weeks_to_zero) if weeks_to_zero else None
    return pd.DataFrame([{
        "as_of": pd.Timestamp(last.week_end).date(), "open_items": int(last.open_items),
        "net_closed_per_week": round(-slope, 1), "weeks_to_zero": weeks_to_zero,
        "forecast_zero_date": zero_date.date() if zero_date is not None else None,
    }])
