import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import pandas as pd  # noqa: E402

import kpis  # noqa: E402

K = kpis.load()


class TestReconciliation(unittest.TestCase):
    def test_ev_never_exceeds_bac(self):
        bac = K["control_accounts"].bac.sum()
        self.assertTrue((K["pc_monthly"].ev.dropna() <= bac + 1).all())

    def test_area_rollup_matches_project(self):
        cur = K["pc_monthly"].dropna(subset=["ev"]).iloc[-1]
        self.assertAlmostEqual(K["pc_by_area"].ev.sum(), cur.ev, delta=1)

    def test_pareto_ends_at_100(self):
        self.assertAlmostEqual(K["punch_pareto"].cum_pct.iloc[-1], 100, delta=0.1)
        self.assertAlmostEqual(K["supplier_pareto"].cum_spend_pct.iloc[-1], 100, delta=0.01)

    def test_punch_open_matches_raw(self):
        raw_open = K["punch_items"].closed_date.isna().sum()
        # weekly snapshot is taken at the last week end on or before the data date
        last_week = pd.Timestamp(K["punch_weekly"].week_end.iloc[-1])
        p = K["punch_items"]
        expected = ((pd.to_datetime(p.raised_date) <= last_week) &
                    (p.closed_date.isna() | (pd.to_datetime(p.closed_date) > last_week))).sum()
        self.assertEqual(int(K["punch_weekly"].open_items.iloc[-1]), int(expected))
        self.assertGreaterEqual(raw_open, 0)

    def test_rfmt_scores_in_range(self):
        s = K["supplier_rfmt"]
        for col in "rfmt":
            self.assertTrue(s[col].between(1, 5).all())
        self.assertEqual(s.supplier_id.nunique(), len(s))

    def test_every_supplier_has_one_segment(self):
        self.assertEqual(K["supplier_segments"].suppliers.sum(), len(K["supplier_rfmt"]))


if __name__ == "__main__":
    unittest.main()
