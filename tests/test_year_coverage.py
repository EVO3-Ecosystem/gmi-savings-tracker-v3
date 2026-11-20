"""Every published table covers every fiscal year its source has (src/pipeline/coverage.py, reference/year_coverage.csv)."""
from pathlib import Path

import pandas as pd
import pytest

from src.pipeline import coverage as C

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "site_data"


def test_the_published_snapshot_covers_every_source_year():
    if not SNAP.exists():
        pytest.skip("no site_data/ snapshot")
    have = C.from_csv(SNAP)
    assert C.problems(set(have), lambda t: have.get(t)) == []


def test_payments_marts_start_at_the_configured_first_year_and_reach_the_open_year():
    if not SNAP.exists():
        pytest.skip("no site_data/ snapshot")
    have = C.from_csv(SNAP)
    first, open_year = C.history_first(), have["totals_by_fy"][1]
    for t in ("f_vendor", "f_vendor_pay", "d_multi", "f_agency", "f_budget_vs_pay"):
        assert have[t][0] <= first and have[t][1] == open_year, (t, have[t])


def test_a_lost_year_is_reported():
    have = {"totals_by_fy": (2008, 2027), "f_function": (2017, 2027), "f_grants": (2009, 2025),
            "f_vendor": (2022, 2026)}
    bad = C.problems(set(have), lambda t: have.get(t), first=2010)
    assert any(b.startswith("f_vendor starts FY2022") for b in bad)
    assert any(b.startswith("f_vendor ends FY2026") for b in bad)


def test_an_unlisted_table_is_reported():
    have = {"totals_by_fy": (2008, 2027), "f_function": (2017, 2027), "f_grants": (2009, 2025), "f_new_table": (2010, 2027)}
    assert any("f_new_table has a fiscal_year column" in b for b in C.problems(set(have), lambda t: have.get(t), first=2010))


def test_every_narrow_table_says_why():
    ref = pd.read_csv(C.REF)
    assert set(ref.family) <= {"payments", "grants", "budget", "mixed", "narrow"}
    assert ref[ref.family == "narrow"].reason.str.strip().str.len().gt(0).all()
