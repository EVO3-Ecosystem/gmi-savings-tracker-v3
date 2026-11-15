"""How past flags turned out (src/models/backtest.outcomes) on the constructed world of tests/test_backtest.py."""
import numpy as np
import pandas as pd
import pytest
from test_backtest import _cfg, _world

from src.models import backtest as B
from src.models import opportunities as O

BT = {"as_of": [2022, 2023], "payment_as_of_extra": [2024], "horizons": [1, 2, 3], "last_actual_fy": 2025, "last_payments_fy": 2025,
      "outcomes": {"flagged_again": {}, "fell": {"min_drop": 0.05}, "grew_slower_than_peers": {}}, "min_units_for_rate": 1, "wilson_z": 1.96}


@pytest.fixture(scope="module")
def res():
    return B.outcomes(*_world(), _cfg(), BT)


def test_columns_cohorts_and_horizons_stop_at_the_last_year(res):
    out, lift = res
    assert list(out.columns) == B.OUT_COLS and list(lift.columns) == B.LIFT_COLS
    assert set(out.cohort) == {"Flagged", "Not flagged", "All eligible"} and set(out.outcome) == set(B.OUTCOMES)
    assert (out.follow_fy == out.as_of_fy + out.horizon).all() and out.follow_fy.max() == 2025
    pg = out[out.detector == "Peer gap"]
    assert set(pg.as_of_fy) == {2022, 2023} and set(pg[pg.as_of_fy == 2023].horizon) == {1, 2}  # 2023 + 3 is past the last actual
    assert 2024 in set(out[out.detector == "Leverage"].as_of_fy) and 2024 not in set(pg.as_of_fy)  # the extra year is payments only


def test_peer_gap_flag_recurs_then_spending_falls(res):
    out, _ = res
    r = out[(out.detector == "Peer gap") & (out.as_of_fy == 2022) & (out.cohort == "Flagged")].set_index(["horizon", "outcome"])
    assert r.loc[(1, "flagged_again"), "units"] == 1 and r.loc[(1, "flagged_again"), "hits"] == 1  # D10 still 10x its peers in FY2023
    assert r.loc[(1, "fell"), "hits"] == 0                                                         # flat from FY2022 to FY2023
    assert r.loc[(2, "fell"), "hits"] == 1  # $10M -> $2M in FY2024
    assert r.loc[(2, "fell"), "pooled_change"] == pytest.approx(-0.8)


def test_all_eligible_is_flagged_plus_not_flagged(res):
    out, _ = res
    g = out.pivot_table(index=["detector", "as_of_fy", "horizon", "outcome"], columns="cohort", values=["units", "hits"])
    assert (g["units"]["All eligible"] == g["units"]["Flagged"] + g["units"]["Not flagged"]).all()
    assert (g["hits"]["All eligible"] == g["hits"]["Flagged"] + g["hits"]["Not flagged"]).all()
    assert (out.hits <= out.units).all()


def test_no_year_after_the_follow_up_year_is_read():
    budget, ay, pay = _world()
    a, _ = B.outcomes(budget, ay, pay, _cfg(), {**BT, "horizons": [1], "last_actual_fy": 2024, "last_payments_fy": 2024, "payment_as_of_extra": []})
    budget2, pay2 = budget.copy(), pay.copy()
    budget2.loc[budget2.fiscal_year == 2025, "budget"] *= 50
    pay2.loc[pay2.fiscal_year == 2025, "amount"] *= 50
    b, _ = B.outcomes(budget2, ay, pay2, _cfg(), {**BT, "horizons": [1], "last_actual_fy": 2024, "last_payments_fy": 2024, "payment_as_of_extra": []})
    pd.testing.assert_frame_equal(a, b)


def test_small_cohorts_publish_counts_but_no_rate():
    out, lift = B.outcomes(*_world(), _cfg(), {**BT, "min_units_for_rate": 1000})
    assert out.rate.isna().all() and out.rate_lo.isna().all() and (out.units > 0).any() and out.hits.notna().all()
    assert lift.lift.isna().all() and lift.flagged_rate.isna().all() and lift.flagged_units.notna().all()


def test_bid_list_detector_flags_exactly_the_bid_list():
    budget, ay, pay = _world()
    cfg = B._cfg(_cfg(), 2023)
    cfg["bid_list"] = {**cfg["bid_list"], "min_spend": 1_000_000, "excluded_agency_codes": []}
    u = B._bid_units(ay[ay.fiscal_year <= 2023], pay[pay.fiscal_year <= 2023], cfg)
    listed = set(O.bid_list(pay[pay.fiscal_year <= 2023], ay[ay.fiscal_year <= 2023], cfg).vendor.str.upper())
    assert set(u[u.flag].vendor.str.upper()) == listed == {"V"}


def test_katz_interval_matches_a_hand_computed_case():
    rr, lo, hi = B.katz(20, 100, 10, 100)
    se = np.sqrt(1 / 20 - 1 / 100 + 1 / 10 - 1 / 100)
    assert rr == pytest.approx(2.0) and lo == pytest.approx(2 * np.exp(-1.96 * se)) and hi == pytest.approx(2 * np.exp(1.96 * se))
    assert B.katz(0, 50, 5, 50) == (None, None, None)


def test_lift_pools_as_of_years_and_compares_flagged_with_not_flagged(res):
    out, lift = res
    r = lift[(lift.detector == "Peer gap") & (lift.horizon == 1) & (lift.outcome == "flagged_again")].iloc[0]
    f = out[(out.detector == "Peer gap") & (out.horizon == 1) & (out.outcome == "flagged_again") & (out.cohort == "Flagged")]
    assert r.flagged_units == f.units.sum() and r.flagged_hits == f.hits.sum() and r.as_of_years == 2


def test_settings_come_from_the_assumptions_file():
    bt = B._full()["detector_backtest"]
    assert bt["as_of"] == [2020, 2021, 2022, 2023, 2024] and bt["horizons"] == [1, 2, 3] and bt["outcomes"]["fell"]["min_drop"] == 0.05
    assert bt["base"] == "not_flagged" and bt["min_units_for_rate"] == 20
