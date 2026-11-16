"""Statewide program screen on constructed programs, and on the published program table."""
import pandas as pd
import pytest

from src.models import program_screen as S

CFG = {"first_fy": 2017, "last_actual_fy": 2025, "min_years": 5, "min_spend": 10_000_000, "fast_growth_multiple": 2.0, "large_swing": 0.30, "top_n": 20}


def _programs():
    def rows(agency, code, name, values, stage="Actual", start=2017):
        return [{"fiscal_year": start + i, "stage": stage, "agency_code": agency, "unit_name": "Unit", "program_code": code, "program_name": name,
                 "budget": v} for i, v in enumerate(values)]
    flat = rows("A00", "01", "Flat", [50e6] * 9)
    grew = rows("A00", "02", "Grew steadily", [20e6 * 1.12 ** i for i in range(9)])           # 2.5x, never more than 12% a year
    swung = rows("B00", "01", "Swung", [50e6, 50e6, 80e6, 50e6, 50e6, 50e6, 50e6, 50e6, 50e6])  # +60% then back
    both = rows("B00", "02", "Old name", [10e6, 12e6, 40e6, 30e6, 45e6, 60e6, 70e6, 75e6], start=2017) + rows("B00", "02", "New name", [80e6], start=2025)
    small = rows("C00", "01", "Too small", [1e6 * (i + 1) for i in range(9)])
    short = rows("C00", "02", "Too short", [50e6, 150e6, 400e6], start=2023)
    plan = rows("A00", "01", "Flat", [900e6], stage="Working budget", start=2026)
    return pd.DataFrame(flat + grew + swung + both + small + short + plan)


OLA = pd.DataFrame({"agency_code": ["B00", "B00"], "report_date": ["2022-01-01", "2025-06-01"], "findings": [3, 7], "repeat_findings": [1, 2]})
REP = pd.DataFrame({"finding_id": ["X1", "X2"], "agency_code": ["B00", "B00"], "program_code": ["02", "02"], "amount": ["500", "200"],
                    "recoupment_status": ["", "Waived/Forgiven"]})


@pytest.fixture(scope="module")
def d():
    return S.screen(_programs(), OLA, REP, {"A00": "Agency A", "B00": "Agency B"}, CFG).set_index("program_name")


def test_signals_follow_the_thresholds_and_small_or_short_programs_are_left_out(d):
    assert set(d.index) == {"Flat", "Grew steadily", "Swung", "New name"}  # the latest name is kept; too small and too short are not screened
    assert d.loc["Flat", "signals"] == 0 and d.loc["Grew steadily", "signals"] == 1 and bool(d.loc["Grew steadily", "fast_growth"])
    assert d.loc["Swung", "signals"] == 1 and bool(d.loc["Swung", "large_swing"]) and not d.loc["Swung", "fast_growth"]
    assert d.loc["New name", "signals"] == 2


def test_measures_are_computed_from_actual_years_only(d):
    assert d.loc["Flat", "spend_last"] == 50e6 and d.loc["Flat", "last_fy"] == 2025        # the $900M working budget is not an outcome
    assert d.loc["Grew steadily", "growth_multiple"] == pytest.approx(1.12 ** 8, abs=1e-3)
    assert d.loc["Swung", "largest_swing"] == pytest.approx(0.6) and d.loc["Swung", "swing_fy"] == 2019
    assert d.loc["New name", "largest_swing"] == pytest.approx(40 / 12 - 1, abs=1e-3)


def test_most_signals_first_then_largest():
    d = S.screen(_programs(), OLA, REP, None, CFG)
    assert list(d.signals) == sorted(d.signals, reverse=True) and d.program_name.iloc[0] == "New name"
    assert list(d.columns) == S.COLUMNS


def test_audit_context_is_the_latest_report_by_agency_and_reported_findings_by_program(d):
    assert d.loc["Swung", "ola_findings"] == 7 and d.loc["Swung", "ola_report_date"] == "2025-06-01"
    assert pd.isna(d.loc["Flat", "ola_findings"])
    assert d.loc["New name", "reported_findings"] == 2 and d.loc["New name", "reported_amount"] == 500  # the largest, not the sum
    assert d.loc["New name", "recoupment_status"] == "Waived/Forgiven" and d.loc["Swung", "reported_findings"] == 0


def test_thresholds_come_from_the_assumptions_file():
    cfg = S.assumptions()
    assert set(CFG) == set(cfg)
    loose = S.screen(_programs(), cfg={**CFG, "fast_growth_multiple": 1.0, "large_swing": 0.0})
    assert (loose.signals == 2).all()


def test_the_published_programs_are_screened_statewide_and_child_care_is_among_the_flagged():
    from src.pipeline import overview_figures as V
    d = V.program_screen_table()
    assert d.agency_code.nunique() > 30 and len(d) > 200
    cc = d[d.program_name == "Child Care Assistance Grants"].iloc[0]
    assert cc.signals == 2 and cc.reported_findings == 2 and cc.growth_multiple > 7
