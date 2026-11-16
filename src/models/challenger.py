"""LightGBM quantile challenger for agency x spending-code spending (review idea #26; #27 declined revenue forecasting
because the tracker holds no revenue data — the same model is applied to spending instead; #25's P10-P90 corridors).

A global gradient-boosted quantile model over every agency x spending-code yearly series (controllable purchases,
actual years), trained with lagged features only, so no future value enters a prediction. Rolling-origin validation:
train through each origin year, predict the next, and score against the naive last-value forecast with MASE whose
scale comes from each origin's own training window. The challenger is kept only for the series where it beats the
naive baseline; the rest stay naive. Published rows forecast the year after the last actual with a p10-p50-p90 band
(fiscal risk corridors): quantile objectives for the challenger, the series' own historical one-step log-change
quantiles for the naive rows.

Assumptions (origins, lags, hyperparameters, seed) live in config/assumptions.yaml under `challenger`.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from lightgbm import LGBMRegressor

from . import calibration as C

ROOT = Path(__file__).resolve().parents[2]
LGBM = "LightGBM quantile (global)"
NAIVE = "Naive (last actual)"
FEATURES = ["l1", "l2", "l3", "g1", "m3", "agency_log", "code_log", "t"]


def assumptions():
    return yaml.safe_load((ROOT / "config" / "assumptions.yaml").read_text())["challenger"]


def panel(scope):
    """scope: one row per agency x code x year of controllable actual spending (fiscal_year, agency_code, code,
    spending_code, budget). Returns the modelling panel: positive years only, one row per series and year."""
    p = scope[scope.budget > 0].copy()
    p = p.groupby(["agency_code", "code", "spending_code", "fiscal_year"], as_index=False).budget.sum()
    return p.sort_values(["agency_code", "code", "fiscal_year"]).reset_index(drop=True)


def features(p, cfg):
    """Lagged features; a row exists only when the series has `lags` prior positive years. No current-year value is
    used as an input, so a forecast never sees its own target or any later year."""
    k = cfg["lags"]
    p = p.copy()
    p["log"] = np.log1p(p.budget)
    g = p.groupby(["agency_code", "code"], sort=False)
    for i in range(1, k + 1):
        p[f"l{i}"] = g["log"].shift(i)
        p[f"y{i}"] = g.fiscal_year.shift(i)
    p["g1"] = p.l1 - p.l2
    p["m3"] = (p.l1 + p.l2 + p.l3) / 3
    ok = (p.fiscal_year - p[f"y{k}"] == k)  # exactly k consecutive prior years
    for keys, col in ((["agency_code"], "agency_log"), (["code"], "code_log")):
        tot = p.groupby(keys + ["fiscal_year"]).budget.sum().rename("total").reset_index()
        tot[col] = np.log1p(tot.total)
        tot["fiscal_year"] += 1  # the prior year's total, so the current year never leaks in
        p = p.merge(tot[keys + ["fiscal_year", col]], on=keys + ["fiscal_year"], how="left")
    p["t"] = p.fiscal_year - cfg["first_actual_fy"]
    return p[ok].dropna(subset=FEATURES + ["log"]).reset_index(drop=True)


def _fit_quantile(train, alpha, cfg):
    m = LGBMRegressor(objective="quantile", alpha=alpha, n_estimators=cfg["n_estimators"],
                      learning_rate=cfg["learning_rate"], num_leaves=cfg["num_leaves"],
                      min_child_samples=cfg["min_child_samples"], random_state=cfg["seed"], deterministic=True, verbose=-1)
    return m.fit(train[FEATURES], train["log"])


def _naive_band(train_series, years):
    """The naive forecast's band for a single series: last value, widened by the series' own one-step log changes."""
    last = float(train_series.budget.iloc[-1])
    d = np.diff(np.log(train_series.budget.values))
    if len(d) < 2:
        return {y: (last, last, last) for y in years}
    q10, q50, q90 = np.percentile(d, [10, 50, 90])
    return {y: (last * np.exp(q10), last * np.exp(q50), last * np.exp(q90)) for y in years}


def backtest(f, cfg):
    """Rolling-origin scoring: per origin, train through the origin and predict the next year; per series, mean MASE
    for the challenger and the naive baseline, and each model's 80% band coverage. One row per origin and model."""
    rows, per_series, detail = [], {}, []
    for origin in cfg["origins"]:
        train, test = f[f.fiscal_year <= origin], f[f.fiscal_year == origin + 1]
        if test.empty:
            continue
        test_idx = test.set_index(["agency_code", "code"])
        models = {a: _fit_quantile(train, a, cfg) for a in (0.1, 0.5, 0.9)}
        for (a, c), ts in f[f.fiscal_year <= origin].groupby(["agency_code", "code"]):
            hist = ts[ts.fiscal_year <= origin].budget.values
            scale = np.mean(np.abs(np.diff(hist))) if len(hist) > 1 else 0
            if not scale or (a, c) not in test_idx.index:
                continue
            row = test_idx.loc[[(a, c)]]
            out = float(np.expm1(row["log"].iloc[0]))
            last = float(ts[ts.fiscal_year == origin].budget.iloc[0])
            band = _naive_band(ts[ts.fiscal_year <= origin], [origin + 1])[origin + 1]
            pred = {q: float(np.expm1(models[q].predict(row[FEATURES])[0])) for q in (0.1, 0.5, 0.9)}
            detail.append({"origin_fy": origin, "agency_code": a, "code": c, "last": last, "outcome": out, "naive_p10": band[0],
                           "naive_p90": band[2], "lgbm_p10": min(pred.values()), "lgbm_p50": pred[0.5], "lgbm_p90": max(pred.values())})
            s = per_series.setdefault((a, c), {NAIVE: [], LGBM: []})
            s[NAIVE].append(abs(last - out) / scale)
            s[LGBM].append(abs(pred[0.5] - out) / scale)
            for model, mid, lo, hi in ((NAIVE, band[1], band[0], band[2]), (LGBM, pred[0.5], pred[0.1], pred[0.9])):
                rows.append({"origin_fy": origin, "model": model, "abs_error": abs(mid - out), "scale": scale,
                             "covered": bool(lo <= out <= hi), "width_log": abs(np.log1p(hi) - np.log1p(lo))})
    bt = pd.DataFrame(rows)
    bt["mase"] = bt.abs_error / bt.scale
    agg = (bt.groupby(["origin_fy", "model"])
           .agg(series_scored=("mase", "size"), mean_mase=("mase", "mean"), coverage_80=("covered", "mean"),
                mean_width_log=("width_log", "mean")).reset_index())
    for c in ("mean_mase", "coverage_80", "mean_width_log"):
        agg[c] = pd.to_numeric(agg[c]).round(4)
    scores = pd.DataFrame([{"agency_code": a, "code": c, "scored_origins": len(v[NAIVE]),
                            "naive_mase": float(np.mean(v[NAIVE])), "challenger_mase": float(np.mean(v[LGBM]))}
                           for (a, c), v in per_series.items()])
    return agg, scores, pd.DataFrame(detail)


def series_calibration(detail, cal):
    """Conformalized quantile regression on the per-series backtest. Returns (margins, coverage rows).

    margins: model -> the log1p margin added to both ends of that model's band, fitted on every origin (used for the
    published forecast year). Coverage rows report the raw band in sample and the widened band at each origin after
    the first, where the margin comes only from earlier origins (out of sample)."""
    alpha, z, rows, margins = 1 - cal["nominal"], cal["wilson_z"], [], {}
    origins = sorted(detail.origin_fy.unique()) if len(detail) else []
    for model, lo, hi, source in ((LGBM, "lgbm_p10", "lgbm_p90", "lightgbm"), (NAIVE, "naive_p10", "naive_p90", "naive band")):
        if not len(detail):
            margins[model] = 0.0
            continue
        d = detail.assign(score=C.cqr_scores(detail[lo], detail[hi], detail.outcome))
        margins[model] = C.cqr_margin(d.score.values, alpha)
        raw_cov = (d[lo] <= d.outcome) & (d.outcome <= d[hi])
        rows.append(C.coverage_row(source, "All series", 1, "in_sample", 0, raw_cov, C.interval_score(d[lo], d[hi], d.outcome), 0.0, z, outcome=d.outcome))
        held = []
        for o in origins[1:]:
            m = C.cqr_margin(d[d.origin_fy < o].score.values, alpha)
            t = d[d.origin_fy == o]
            a, b = C.cqr_widen(t[lo], t[hi], m)
            held.append(pd.DataFrame({"covered": (a <= t.outcome) & (t.outcome <= b), "iscore": C.interval_score(a, b, t.outcome),
                                      "outcome": t.outcome, "margin": m}))
        if held:
            h = pd.concat(held, ignore_index=True)
            rows.append(C.coverage_row(source, "All series", 1, "expanding_origin", 1, h.covered, h.iscore, float(h.margin.mean()), z, outcome=h.outcome))
    return margins, rows


def area_backtest(detail, area_of, area_actual, cal):
    """LightGBM-based ranges for focus-area totals, scored at each origin. Returns (rows, margin, coverage rows).

    Per-series quantiles are not additive, so the area range is not built from them. The challenger's growth for an
    area is the sum of its series medians over the sum of their last actuals; that growth is applied to the area's
    actual total, and the range around it is that point times exp(+/- margin), where the margin is the conformal
    quantile of the absolute log errors of the same construction at earlier origins, pooled over areas.
    area_of: (agency_code, code) -> area. area_actual: (area, fiscal_year) -> actual spending."""
    alpha, z = 1 - cal["nominal"], cal["wilson_z"]
    rows = []
    if len(detail):
        d = detail.assign(area=[area_of(a, c) for a, c in zip(detail.agency_code, detail.code)])
        for (o, area), g in d.groupby(["origin_fy", "area"]):
            base, out = area_actual.get((area, int(o))), area_actual.get((area, int(o) + 1))
            if not base or not out or g["last"].sum() <= 0:
                continue
            pred = base * g.lgbm_p50.sum() / g["last"].sum()
            rows.append({"origin_fy": int(o), "area": area, "pred": pred, "outcome": out, "score": abs(np.log(out) - np.log(pred))})
    bt = pd.DataFrame(rows, columns=["origin_fy", "area", "pred", "outcome", "score"])
    margin = C.conformal_quantile(bt.score.values, alpha) if len(bt) else float("nan")
    cov, held = [], []
    for o in sorted(bt.origin_fy.unique())[1:]:
        m = C.conformal_quantile(bt[bt.origin_fy < o].score.values, alpha)
        t = bt[bt.origin_fy == o]
        lo, hi = t.pred * np.exp(-m), t.pred * np.exp(m)
        held.append(pd.DataFrame({"covered": (lo <= t.outcome) & (t.outcome <= hi), "iscore": C.interval_score(lo, hi, t.outcome),
                                  "outcome": t.outcome, "margin": m}))
    if held:
        h = pd.concat(held, ignore_index=True)
        cov.append(C.coverage_row("lightgbm area", C.ALL, 1, "expanding_origin", 1, h.covered, h.iscore, float(h.margin.mean()), z, outcome=h.outcome))
    return bt, margin, cov


def statewide_tau(detail):
    """Size of the shock all series share in a year: root mean square, over the backtest origins, of the log ratio of
    the actual statewide total to the sum of the series medians. 0 when there is no backtest."""
    if not len(detail):
        return 0.0
    g = detail.groupby("origin_fy")[["outcome", "lgbm_p50"]].sum()
    return float(np.sqrt(np.mean(np.log(g.outcome / g.lgbm_p50) ** 2)))


def build(scope, agency_names, cfg=None):
    """The challenger tables from the spending panel. agency_names: agency_code -> latest name. Returns
    (f_challenger, d_challenger_backtest): per-series forecasts for the year after the last actual, and the
    rolling-origin validation that justifies each series' model."""
    return build_all(scope, agency_names, cfg)[:2]


def build_all(scope, agency_names, cfg=None, cal=None):
    """build() plus what the range calibration needs: (f_challenger, d_challenger_backtest, per-series backtest rows,
    per-series LightGBM medians for the forecast year). f_challenger carries p10_cal / p90_cal: each row's band widened
    by its model's conformal margin."""
    cfg = cfg or assumptions()
    cal = cal or C.settings()
    p = panel(scope)
    f = features(p, cfg)
    agg, scores, detail = backtest(f, cfg)
    margins, _ = series_calibration(detail, cal)
    keep = scores[(scores.scored_origins >= cfg["min_scored_origins"]) & (scores.challenger_mase < scores.naive_mase - 1e-9)]
    adopted = set(zip(keep.agency_code, keep.code))
    fy = cfg["last_actual_fy"] + 1
    train = f[f.fiscal_year <= cfg["last_actual_fy"]]
    models = {a: _fit_quantile(train, a, cfg) for a in (0.1, 0.5, 0.9)}
    agency_tot = p[p.fiscal_year == cfg["last_actual_fy"]].groupby("agency_code").budget.sum()
    code_tot = p[p.fiscal_year == cfg["last_actual_fy"]].groupby("code").budget.sum()
    lags_needed = [fy - i for i in range(1, cfg["lags"] + 1)]
    sc = scores.set_index(["agency_code", "code"])
    rows, medians = [], []
    for (a, c, name), ts in p.groupby(["agency_code", "code", "spending_code"]):
        hist = ts[ts.fiscal_year <= cfg["last_actual_fy"]]
        vals = hist.set_index("fiscal_year").budget
        if any(y not in vals.index for y in lags_needed):
            continue  # not enough consecutive history to feature a one-year-ahead forecast
        lg = np.log1p(vals.loc[lags_needed].values)  # l1 = last actual, l2, l3
        x = pd.DataFrame([{"l1": lg[0], "l2": lg[1], "l3": lg[2], "g1": lg[0] - lg[1], "m3": lg.mean(),
                           "agency_log": np.log1p(agency_tot.get(a)), "code_log": np.log1p(code_tot.get(c)),
                           "t": fy - cfg["first_actual_fy"]}])
        key = (a, c)
        use_lgbm = key in adopted
        q = {a_: float(np.expm1(models[a_].predict(x)[0])) for a_ in (0.1, 0.5, 0.9)}
        medians.append({"agency_code": a, "code": c, "last": float(vals.loc[lags_needed[0]]), "lgbm_p50": q[0.5]})
        if use_lgbm:
            p10, p50, p90 = q[0.1], q[0.5], q[0.9]
        else:
            p10, p50, p90 = _naive_band(hist, [fy])[fy]
        lo, mid, hi = min(p10, p50, p90), np.median([p10, p50, p90]), max(p10, p50, p90)
        nm, cm = (float(sc.loc[key, col]) if key in sc.index else None for col in ("naive_mase", "challenger_mase"))
        rows.append({"agency_code": a, "agency": agency_names.get(a, a), "code": c, "spending_code": name,
                     "fiscal_year": fy, "p10": lo, "p50": mid, "p90": hi,
                     "model": LGBM if use_lgbm else NAIVE, "adopted": use_lgbm, "naive_mase": nm, "challenger_mase": cm})
    out = pd.DataFrame(rows)
    m = out.model.map(margins).fillna(0.0).to_numpy(dtype=float) if len(out) else []
    out["p10_cal"], out["p90_cal"] = C.cqr_widen(out.p10, out.p90, m) if len(out) else ([], [])
    for c in ("p10", "p50", "p90", "p10_cal", "p90_cal"):
        out[c] = pd.to_numeric(out[c]).round(0)
    for c in ("naive_mase", "challenger_mase"):
        out[c] = pd.to_numeric(out[c]).round(4)
    return out.sort_values("p50", ascending=False).reset_index(drop=True), agg, detail, pd.DataFrame(medians)


def _statewide(out, cfg, tau=0.0, origins=0):
    """A band for the statewide FY-after-last-actual total, measured on the total itself.

    p50 = the sum of the series medians; p10 / p90 = p50 x exp(-/+ 1.2816 x tau), where tau is the root-mean-square log
    miss of the actual statewide total against the sum of the series medians over the backtest origins
    (statewide_tau). Summing per-series draws was tried and rejected on the Nov 16, 2026 run: 154 series have a
    calibrated p90 more than 20 times their median (pandemic-era swings), so any sum of draws, clamped or not, moved the
    statewide median 25-130% above the sum of medians, a total no series median supports. The per-series calibrated
    bands stay published in f_challenger; only the statewide corridor is taken from the statewide miss."""
    z = 1.2816
    p50 = float(out["p50"].sum())
    lo, hi = p50 * np.exp(-z * tau), p50 * np.exp(z * tau)
    return pd.DataFrame([{"fiscal_year": int(out.fiscal_year.iloc[0]), "p10": round(lo), "p50": round(p50),
                          "p90": round(hi), "n_series": len(out), "n_adopted": int(out.adopted.sum()),
                          "bootstrap_paths": 0, "common_shock_sigma": round(float(tau), 4),
                          "note": f"Statewide corridor: the sum of the series medians, with a band from the statewide total's "
                                  f"own miss in the backtest (log sigma {tau:.3f} over {origins} origins; few points, so read "
                                  f"it as indicative). Per-series bands are not summed: a few very volatile series would "
                                  f"dominate the total."}])


AREA_SQL = "SELECT DISTINCT agency_code, code, area FROM mart.f_code"
OTHER = "Other controllable purchases"


def adopt_area_ranges(con, medians, bt_area, margin, cov, cfg, cal):
    """Apply the pre-registered adoption rule to the one-year-ahead area ranges and record the outcome.

    Compares the LightGBM-based area range with the calibrated bootstrap range at horizon 1, both out of sample
    (expanding origin). When the rule adopts, the forecast-year rows of mart.f_forecast get the LightGBM-based
    p10_cal / p90_cal and range_source = 'lightgbm', except for an area whose LightGBM-based range would not contain
    the published median. Returns (adopted, coverage rows to append to mart.d_range_coverage)."""
    tables = {r[0] for r in con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'mart'").fetchall()}
    if "d_range_coverage" not in tables or "f_forecast" not in tables or not cov:
        return False, cov
    inc = con.execute("""SELECT n, coverage, relative_interval_score FROM mart.d_range_coverage
                         WHERE source = 'bootstrap' AND area = ? AND horizon = 1 AND scope = 'expanding_origin' AND calibrated = 1""", [C.ALL]).df()
    incumbent = inc.iloc[0].to_dict() if len(inc) else None
    adopted = C.adopt({k: cov[0][k] for k in ("n", "coverage", "relative_interval_score")}, incumbent, cal)
    cov = [{**r, "adopted": int(adopted)} for r in cov]
    if adopted and len(medians) and not np.isnan(margin):
        fy = cfg["last_actual_fy"] + 1
        f = con.execute("SELECT * FROM mart.f_forecast").df()
        last = f[(f.kind == "Actual") & (f.fiscal_year == cfg["last_actual_fy"])].set_index("area").value
        g = medians.groupby("area")[["last", "lgbm_p50"]].sum()
        for area, r in g.iterrows():
            row = (f.area == area) & (f.kind == "Forecast") & (f.fiscal_year == fy)
            if area not in last.index or not row.any() or r["last"] <= 0:
                continue
            pred = last[area] * r.lgbm_p50 / r["last"]
            lo, hi = round(pred * np.exp(-margin)), round(pred * np.exp(margin))
            if lo <= float(f.loc[row, "p50"].iloc[0]) <= hi:
                f.loc[row, ["p10_cal", "p90_cal", "range_source"]] = [lo, hi, "lightgbm"]
        con.register("_df", f)
        con.execute("CREATE OR REPLACE TABLE mart.f_forecast AS SELECT * FROM _df")
        con.unregister("_df")
    return adopted, cov


SCOPE_SQL = """SELECT b.fiscal_year, b.agency_code, b.subobject_code AS code, b.subobject_name AS spending_code,
      sum(b.budget) AS budget
FROM core.fact_budget_scope b JOIN ref.dim_stage s USING (fiscal_year)
WHERE b.controllable AND s.stage = 'Actual'
GROUP BY ALL"""


def write(con, cfg=None):
    from . import forecast as F
    cfg = cfg or assumptions()
    cal = C.settings()
    scope = con.execute(SCOPE_SQL).df()
    names = con.execute("SELECT agency_code, agency, fiscal_year FROM mart.agency_year").df()
    names = names.sort_values("fiscal_year", ascending=False).drop_duplicates("agency_code").set_index("agency_code").agency.to_dict()
    f, bt, detail, medians = build_all(scope, names, cfg, cal)
    tot = _statewide(f, cfg, statewide_tau(detail), int(detail.origin_fy.nunique()) if len(detail) else 0)
    # focus-area view of the same backtest, for the adoption rule
    amap = {(a, c): area for a, c, area in con.execute(AREA_SQL).fetchall()}
    area_of = lambda a, c: amap.get((a, c), OTHER)  # noqa: E731
    s = F.series(con.execute("SELECT * FROM mart.f_code").df(), con.execute("SELECT * FROM mart.f_scope").df())
    actual = {(r.area, int(r.fiscal_year)): float(r.spend) for r in s[s.stage == "Actual"].itertuples()}
    bt_area, margin, cov_area = area_backtest(detail, area_of, actual, cal)
    if len(medians):
        medians["area"] = [area_of(a, c) for a, c in zip(medians.agency_code, medians.code)]
    _, cov_series = series_calibration(detail, cal)
    adopted, cov_area = adopt_area_ranges(con, medians, bt_area, margin, cov_area, cfg, cal)
    cov = C.table(cov_series + cov_area)
    for name, df in (("f_challenger", f), ("d_challenger_backtest", bt), ("d_challenger_total", tot), ("d_challenger_series_backtest", detail)):
        con.register("_df", df)
        con.execute(f"CREATE OR REPLACE TABLE mart.{name} AS SELECT * FROM _df")
        con.unregister("_df")
    if con.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'mart' AND table_name = 'd_range_coverage'").fetchone()[0]:
        con.execute("DELETE FROM mart.d_range_coverage WHERE source IN ('lightgbm', 'naive band', 'lightgbm area')")
        con.register("_df", cov)
        con.execute("INSERT INTO mart.d_range_coverage BY NAME SELECT * FROM _df")
        con.unregister("_df")
    return {"f_challenger": len(f), "d_challenger_backtest": len(bt), "d_challenger_total": len(tot),
            "d_challenger_series_backtest": len(detail), "area_range_adopted": int(adopted)}
