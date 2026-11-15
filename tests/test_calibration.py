"""Range calibration on constructed cases (no data/ needed): the conformal factor, the widening, the out-of-sample
designs, the adoption rule, and how forecast, challenger and revenue use them."""
import duckdb
import numpy as np
import pandas as pd
import pytest

from src.models import calibration as C
from src.models import challenger as CH
from src.models import forecast as F
from src.models import revenue as R
from test_challenger import CFG as CH_CFG
from test_challenger import NAMES, _panel
from test_forecast import _inputs

CAL = {"nominal": 0.8, "min_factor": 1.0, "min_scores_per_horizon": 20, "min_scored_for_adoption": 9, "wilson_z": 1.96}


def test_wilson_interval_matches_a_hand_computed_case():
    lo, hi = C.wilson(8, 10)  # textbook value for 8 of 10 at z = 1.96
    assert lo == pytest.approx(0.4902, abs=1e-4) and hi == pytest.approx(0.9433, abs=1e-4)
    assert all(np.isnan(v) for v in C.wilson(0, 0))


def test_conformal_quantile_uses_the_finite_sample_rank():
    s = np.arange(1, 10) / 10  # nine scores: rank ceil(10 x 0.8) = 8, the eighth smallest
    assert C.conformal_quantile(s, 0.2) == pytest.approx(0.8)
    assert C.conformal_quantile([0.3, 2.0], 0.2) == 2.0  # too few scores for the level: the largest
    assert np.isnan(C.conformal_quantile([], 0.2))


def test_factor_never_narrows_and_is_one_without_scores():
    assert C.factor([0.1, 0.2, 0.3, 0.4, 0.5], 0.2, 1.0) == 1.0
    assert C.factor([], 0.2, 1.0) == 1.0
    assert C.factor([0.5, 1.5, 2.5, 3.0], 0.2, 1.0) == 3.0


def test_widen_keeps_the_median_contains_the_raw_range_and_is_exact_on_the_log_scale():
    lo, hi = C.widen([80.0], [100.0], [150.0], 2.0)
    assert lo[0] == pytest.approx(100 * (80 / 100) ** 2) and hi[0] == pytest.approx(100 * (150 / 100) ** 2)
    assert lo[0] <= 80 and hi[0] >= 150
    same = C.widen([80.0], [100.0], [150.0], 1.0)
    assert same[0][0] == pytest.approx(80) and same[1][0] == pytest.approx(150)


def test_miss_is_below_one_inside_the_range_and_above_one_outside():
    m = C.miss([80, 80, 80], [100, 100, 100], [150, 150, 150], [100, 149, 200])
    assert m[0] == pytest.approx(0) and m[1] < 1 < m[2]


def test_one_factor_per_horizon_only_when_every_horizon_has_enough_scores():
    few = pd.DataFrame({"horizon": [1] * 25 + [2] * 5, "miss": np.linspace(0.1, 3, 30)})
    assert set(C.factors(few, CAL)) == {0}
    many = pd.DataFrame({"horizon": [1] * 25 + [2] * 25, "miss": np.r_[np.full(25, 0.5), np.full(25, 2.0)]})
    fs = C.factors(many, CAL)
    assert fs == {1: 1.0, 2: 2.0}
    assert C.factor_for(fs, 5) == 2.0 and C.factor_for({0: 1.4}, 3) == 1.4  # beyond the backtest: the longest horizon


def _bt(years=(2021, 2022, 2023, 2024, 2025), inside=(True, True, False, True, True)):
    """One area, one method, horizon 1: the range 80-150 around 100; the outcome is inside or far above it."""
    rows = [{"area": "A", "method": F.NAIVE, "origin_fy": y - 1, "horizon": 1, "forecast_fy": y, "target": "actual",
             "outcome": 110.0 if ok else 400.0, "p10": 80.0, "p50": 100.0, "p90": 150.0, "covered": ok,
             "interval_score": float(C.interval_score(80, 150, 110.0 if ok else 400.0)), "mase": 1.0} for y, ok in zip(years, inside)]
    return pd.DataFrame(rows)


def test_leave_one_year_out_never_fits_on_the_held_out_year():
    bt = _bt()
    model = pd.DataFrame({"area": ["A"], "method": [F.NAIVE]})
    seen = []

    def rechoose(rows):
        seen.append(set(rows.forecast_fy))
        return model
    fs, cov = C.evaluate(bt, model, rechoose, CAL)
    loyo = seen[:5]  # the five leave-one-year-out fits come first
    assert len(loyo) == 5 and all(len(s) == 4 for s in loyo)
    assert {y for y in bt.forecast_fy} == {next(iter(set(bt.forecast_fy) - s)) for s in loyo}
    # the one large miss sets the published factor; held out, that year cannot be covered by a factor fitted without it
    out = cov[(cov.scope == "out_of_sample") & (cov.calibrated == 1) & (cov.area == C.ALL) & (cov.horizon == 0)].iloc[0]
    assert out.n == 5 and out.hits == 4
    ins = cov[(cov.scope == "in_sample") & (cov.calibrated == 1) & (cov.area == C.ALL) & (cov.horizon == 0)].iloc[0]
    assert ins.hits == 5 and fs[0] > 1


def test_expanding_origin_uses_only_outcomes_known_at_the_origin():
    bt = _bt()
    model = pd.DataFrame({"area": ["A"], "method": [F.NAIVE]})
    seen = []

    def rechoose(rows):
        seen.append((int(rows.forecast_fy.max()), len(rows)))
        return model
    _, cov = C.evaluate(bt, model, rechoose, CAL)
    expanding = seen[5:]  # after the five leave-one-year-out calls
    assert expanding == [(2021, 1), (2022, 2), (2023, 3), (2024, 4)]  # origin O sees forecast years <= O only
    row = cov[(cov.scope == "expanding_origin") & (cov.calibrated == 1) & (cov.horizon == 0)].iloc[0]
    assert row.n == 4  # the first origin has nothing to fit on and is not scored


def test_adoption_needs_closer_coverage_and_no_worse_interval_score_and_enough_scores():
    inc = {"n": 21, "coverage": 0.95, "relative_interval_score": 0.50}
    assert C.adopt({"n": 16, "coverage": 0.81, "relative_interval_score": 0.40}, inc, CAL)
    assert not C.adopt({"n": 16, "coverage": 0.81, "relative_interval_score": 0.60}, inc, CAL)   # wider relative to outcome
    assert not C.adopt({"n": 16, "coverage": 0.65, "relative_interval_score": 0.40}, inc, CAL)   # coverage tie in distance: keep
    assert not C.adopt({"n": 8, "coverage": 0.81, "relative_interval_score": 0.40}, inc, CAL)    # too few scored forecasts
    assert not C.adopt({"n": 16, "coverage": 0.81, "relative_interval_score": 0.40}, None, CAL)  # nothing to compare with


def test_cqr_margin_is_never_negative_and_widens_both_ends():
    s = C.cqr_scores([90, 90], [110, 110], [100, 130])
    assert s[0] < 0 < s[1]
    assert C.cqr_margin([-0.2, -0.1, -0.05], 0.2) == 0.0
    lo, hi = C.cqr_widen([90.0], [110.0], 0.1)
    assert lo[0] < 90 and hi[0] > 110


@pytest.fixture(scope="module")
def built():
    f, m, bt = F.build(*_inputs())
    return f, m, bt


def test_calibrated_forecast_ranges_contain_the_raw_range_and_leave_it_untouched(built):
    f, m, bt = built
    g, cov = F.calibrate(f, m, bt)
    pd.testing.assert_frame_equal(g[f.columns], f)  # value, p10, p50, p90, plan are exactly as built
    fc = g[g.kind == "Forecast"]
    assert (fc.p10_cal <= fc.p10).all() and (fc.p90_cal >= fc.p90).all() and (fc.p10_cal <= fc.p50).all()
    assert set(fc.range_source) == {"bootstrap"} and g[g.kind == "Actual"].p10_cal.isna().all()
    assert list(cov.columns) == C.COLS
    assert {"in_sample", "out_of_sample", "expanding_origin"} <= set(cov.scope)
    assert ((cov.hits <= cov.n) & (cov.cov_lo <= cov.coverage) & (cov.coverage <= cov.cov_hi)).all()


def test_calibration_is_deterministic(built):
    f, m, bt = built
    a, b = F.calibrate(f, m, bt), F.calibrate(f, m, bt)
    pd.testing.assert_frame_equal(a[0], b[0])
    pd.testing.assert_frame_equal(a[1], b[1])


def test_calibrated_in_sample_coverage_is_at_least_the_raw_coverage(built):
    f, m, bt = built
    _, cov = F.calibrate(f, m, bt)
    row = cov[(cov.source == "bootstrap") & (cov.area == C.ALL) & (cov.horizon == 0) & (cov.scope == "in_sample")].set_index("calibrated")
    assert row.loc[1, "hits"] >= row.loc[0, "hits"] and row.loc[1, "n"] == row.loc[0, "n"]


@pytest.fixture(scope="module")
def chal():
    return CH.build_all(_panel("walk"), NAMES, CH_CFG, CAL)


def test_challenger_calibrated_bands_contain_the_raw_bands(chal):
    f, agg, detail, medians = chal
    assert (f.p10_cal <= f.p10).all() and (f.p90_cal >= f.p90).all()
    assert len(detail) and {"origin_fy", "outcome", "lgbm_p10", "lgbm_p90", "naive_p10", "naive_p90"} <= set(detail.columns)
    assert len(medians) == len(f)


def test_series_calibration_scores_later_origins_with_margins_from_earlier_ones(chal):
    _, _, detail, _ = chal
    margins, rows = CH.series_calibration(detail, CAL)
    assert margins[CH.LGBM] >= 0 and margins[CH.NAIVE] >= 0
    held = [r for r in rows if r["scope"] == "expanding_origin" and r["source"] == "lightgbm"][0]
    assert held["n"] == len(detail[detail.origin_fy > detail.origin_fy.min()])  # the first origin is never scored
    one = detail[detail.origin_fy == detail.origin_fy.min()]
    assert not [r for r in CH.series_calibration(one, CAL)[1] if r["scope"] == "expanding_origin"]


def test_area_backtest_applies_the_challenger_growth_to_the_area_total(chal):
    _, _, detail, _ = chal
    actual = {("A", int(y)): 1000.0 * 1.05 ** (y - 2017) for y in range(2017, 2026)}
    bt, margin, cov = CH.area_backtest(detail, lambda a, c: "A", actual, CAL)
    g = detail[detail.origin_fy == 2022]
    assert bt[bt.origin_fy == 2022].pred.iloc[0] == pytest.approx(actual[("A", 2022)] * g.lgbm_p50.sum() / g["last"].sum())
    assert margin >= 0 and cov[0]["n"] == 2  # origins 2023 and 2024, one area


def test_statewide_corridor_is_not_clamped_and_widens_with_a_common_shock(chal):
    f = chal[0]
    a, b = CH._statewide(f, CH_CFG, 0.0).iloc[0], CH._statewide(f, CH_CFG, 0.1).iloc[0]
    assert a.p10 < a.p50 < a.p90 and (b.p90 - b.p10) > (a.p90 - a.p10)
    assert b.common_shock_sigma == 0.1 and "clamp" not in a.note


def test_adoption_rewrites_only_the_forecast_year_and_only_ranges_that_contain_the_median(built):
    f, m, bt = built
    g, cov = F.calibrate(f, m, bt)
    con = duckdb.connect()
    con.execute("CREATE SCHEMA mart")
    con.register("_f", g)
    con.execute("CREATE TABLE mart.f_forecast AS SELECT * FROM _f")
    inc = C.table([C.coverage_row("bootstrap", C.ALL, 1, "expanding_origin", 1, [True] * 12, np.full(12, 90.0), 5.0, outcome=np.full(12, 100.0))])
    con.register("_c", inc)
    con.execute("CREATE TABLE mart.d_range_coverage AS SELECT * FROM _c")
    areas = sorted(g.area.unique())
    last = g[(g.kind == "Actual") & (g.fiscal_year == 2025)].set_index("area").value
    p50 = g[(g.kind == "Forecast") & (g.fiscal_year == 2026)].set_index("area").p50
    # area 0: a challenger growth that puts the median inside the range; area 1: far away, so its range is not used
    medians = pd.DataFrame({"area": areas[:2], "last": [1.0, 1.0], "lgbm_p50": [p50[areas[0]] / last[areas[0]], 10.0]})
    cand = [C.coverage_row("lightgbm area", C.ALL, 1, "expanding_origin", 1, [True] * 8 + [False] * 2, np.full(10, 30.0), 0.1, outcome=np.full(10, 100.0))]
    adopted, rows = CH.adopt_area_ranges(con, medians, None, 0.1, cand, {"last_actual_fy": 2025}, CAL)
    out = con.execute("SELECT * FROM mart.f_forecast").df()
    assert adopted and rows[0]["adopted"] == 1
    src = out[(out.kind == "Forecast")].set_index(["area", "fiscal_year"]).range_source
    assert src[(areas[0], 2026)] == "lightgbm" and src[(areas[1], 2026)] == "bootstrap" and src[(areas[0], 2027)] == "bootstrap"
    pd.testing.assert_frame_equal(out[f.columns].reset_index(drop=True), f.reset_index(drop=True), check_dtype=False)
    # a candidate that is not closer to nominal changes nothing
    worse = [{**cand[0], "coverage": 0.3}]
    assert not CH.adopt_area_ranges(con, medians, None, 0.1, worse, {"last_actual_fy": 2025}, CAL)[0]


def test_revenue_calibrated_range_contains_the_raw_range():
    hist = pd.DataFrame({"fiscal_year": range(2017, 2027), "value": [17e9 * 1.04 ** i * (1 + 0.03 * (-1) ** i) for i in range(10)]})
    cpi = pd.DataFrame({"fiscal_year": range(2017, 2027), "cpi_avg": [240 * 1.03 ** i for i in range(10)], "months": 12})
    f, bt, meta = R.build(hist, cpi)
    g, cov = R.calibrate(f, bt, meta, CAL)
    fc = g[g.kind == "Forecast"]
    assert (fc.p10_cal <= fc.p10).all() and (fc.p90_cal >= fc.p90).all()
    pd.testing.assert_frame_equal(g[f.columns], f)
    assert set(cov.source) == {"revenue"} and cov[cov.calibrated == 1].coverage.iloc[0] >= cov[cov.calibrated == 0].coverage.iloc[0]


def test_published_forecast_is_reproduced_from_the_published_tables():
    from src.models import forecast_published as P
    tables = P.rebuild()
    assert P.differences(tables) == []
    cov = tables["d_range_coverage"]
    raw = cov[(cov.area == C.ALL) & (cov.horizon == 0) & (cov.scope == "in_sample") & (cov.calibrated == 0)].iloc[0]
    assert raw.n == len(tables["d_forecast_backtest"].merge(tables["d_forecast_model"][["area", "method"]]).query("target == 'actual'"))
