"""Range calibration: make a nominal 80% range hold about 80% of outcomes, and say honestly how well it did.

The bootstrap ranges of the area forecasts (forecast.py) held 63.5% of 63 past outcomes against a nominal 80%, and
the LightGBM quantile ranges (challenger.py) about 73%. This module widens a range by a conformal factor fitted on
backtest misses (split conformal prediction: Angelopoulos and Bates 2021; for quantile models, conformalized quantile
regression: Romano, Patterson and Candes 2019) and measures coverage out of sample, so the reported figure is not the
one the factor was fitted on.

Pure functions, no I/O apart from reading config/assumptions.yaml (`calibration:`). Nothing here draws random numbers,
so calibrated bounds are a deterministic function of the raw range and the backtest.

Two out-of-sample designs, both nested (the model is re-chosen without the held-out rows):
  * leave one outcome year out: every forecast of fiscal year Y is widened by a factor fitted on the other years.
    Grouping by outcome year matters because origins share outcome years (origin 2021 horizon 2 and origin 2022
    horizon 1 both score FY2023);
  * expanding origin: a forecast made at origin O is widened by a factor fitted only on outcomes known at O. This is
    what could have been done in real time; early origins have little or nothing to fit on.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
ALL = "All areas"
COLS = ["source", "area", "horizon", "scope", "calibrated", "n", "hits", "coverage", "cov_lo", "cov_hi", "mean_interval_score", "relative_interval_score", "factor", "adopted"]


def settings(cfg=None):
    cfg = cfg if cfg is not None else yaml.safe_load((ROOT / "config" / "assumptions.yaml").read_text())
    return cfg["calibration"]


def wilson(hits, n, z=1.96):
    """Wilson score interval for a share (Brown, Cai and DasGupta 2001): (low, high); (nan, nan) when n = 0."""
    if not n:
        return float("nan"), float("nan")
    p = hits / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return float(max(0.0, centre - half)), float(min(1.0, centre + half))


def interval_score(lo, hi, outcome, alpha=0.2):
    """Interval score of a central (1 - alpha) range (Gneiting and Raftery 2007); lower is better."""
    lo, hi, outcome = (np.asarray(v, dtype=float) for v in (lo, hi, outcome))
    return (hi - lo) + (2 / alpha) * np.maximum(lo - outcome, 0) + (2 / alpha) * np.maximum(outcome - hi, 0)


def miss(p10, p50, p90, outcome):
    """How many times wider than its own range each outcome's miss was, on the log scale around the median: below 1 the
    outcome is inside the range, above 1 outside. The same score forecast.calibration uses."""
    lo, mid, hi, out = (np.log(np.asarray(v, dtype=float)) for v in (p10, p50, p90, outcome))
    up = np.clip(hi - mid, 1e-9, None)
    down = np.clip(mid - lo, 1e-9, None)
    return np.where(out >= mid, (out - mid) / up, (mid - out) / down)


def conformal_quantile(scores, alpha=0.2):
    """The (1 - alpha) quantile of the scores with the finite-sample rank ceil((n + 1)(1 - alpha)); nan when empty.
    When the rank exceeds n (too few scores for the level), the largest score is used."""
    s = np.sort(np.asarray(scores, dtype=float))
    n = len(s)
    if not n:
        return float("nan")
    return float(s[min(n - 1, int(np.ceil((n + 1) * (1 - alpha))) - 1)])


def factor(scores, alpha=0.2, min_factor=1.0):
    """The widening factor: the conformal quantile of the misses, never below `min_factor` (a range is not narrowed).
    With no scores there is nothing to fit, so the range is left as it is."""
    q = conformal_quantile(scores, alpha)
    return float(min_factor) if np.isnan(q) else float(max(min_factor, q))


def widen(p10, p50, p90, k):
    """Stretch a range by k on the log scale around its median. k = 1 returns the range unchanged; p50 never moves."""
    lo, mid, hi = (np.log(np.asarray(v, dtype=float)) for v in (p10, p50, p90))
    k = np.asarray(k, dtype=float)
    return np.exp(mid - k * (mid - lo)), np.exp(mid + k * (hi - mid))


def factors(scored, cal):
    """Widening factors from scored backtest rows (columns: horizon, miss). One per horizon when every horizon has at
    least `min_scores_per_horizon` scores; otherwise one pooled factor under key 0."""
    alpha, floor = 1 - cal["nominal"], cal["min_factor"]
    if scored.empty:
        return {0: float(floor)}
    counts = scored.groupby("horizon").size()
    if len(counts) > 1 and counts.min() >= cal["min_scores_per_horizon"]:
        return {int(h): factor(g.miss.values, alpha, floor) for h, g in scored.groupby("horizon")}
    return {0: factor(scored.miss.values, alpha, floor)}


def factor_for(fs, horizon):
    """The factor for a horizon: its own, else the pooled one, else the longest fitted horizon's (for years beyond the
    backtest's longest horizon)."""
    if int(horizon) in fs:
        return fs[int(horizon)]
    return fs[0] if 0 in fs else fs[max(fs)]


def _scored(rows):
    rows = rows.copy()
    rows["miss"] = miss(rows.p10, rows.p50, rows.p90, rows.outcome) if len(rows) else []
    return rows


def _apply(rows, fs):
    """Rows with calibrated bounds, coverage and interval score under the factors `fs`."""
    rows = rows.copy()
    k = np.array([factor_for(fs, h) for h in rows.horizon], dtype=float)
    rows["factor"] = k
    rows["p10_cal"], rows["p90_cal"] = widen(rows.p10, rows.p50, rows.p90, k) if len(rows) else ([], [])
    # inside the widened range exactly when the miss is at most the factor; compared on the score so the forecast that
    # sets the factor (miss == factor) counts as covered instead of falling to floating-point rounding at the edge
    rows["covered_cal"] = (rows.miss <= k + 1e-12) if len(rows) else []
    rows["iscore_cal"] = interval_score(rows.p10_cal, rows.p90_cal, rows.outcome)
    return rows


def coverage_row(source, area, horizon, scope, calibrated, covered, iscore, k, z=1.96, adopted=0, outcome=None):
    """One row of the coverage table. relative_interval_score = mean interval score as a share of the outcome, so ranges
    for series of different sizes can be compared."""
    covered = np.asarray(covered, dtype=bool)
    rel = float(np.mean(np.asarray(iscore, dtype=float) / np.asarray(outcome, dtype=float))) if outcome is not None and len(covered) else None
    n, hits = int(len(covered)), int(covered.sum())
    lo, hi = wilson(hits, n, z)
    return {"source": source, "area": area, "horizon": int(horizon), "scope": scope, "calibrated": int(calibrated), "n": n, "hits": hits,
            "coverage": hits / n if n else None, "cov_lo": lo if n else None, "cov_hi": hi if n else None,
            "mean_interval_score": float(np.mean(iscore)) if n else None, "relative_interval_score": rel, "factor": k, "adopted": int(adopted)}


def _cuts(rows, source, scope, calibrated, cov, isc, z, by_area=True):
    """Coverage rows for one design: all areas pooled, each horizon, and (optionally) each area."""
    k = float(rows.factor.mean()) if calibrated and len(rows) else (1.0 if not calibrated else None)
    out = [coverage_row(source, ALL, 0, scope, calibrated, rows[cov], rows[isc], k, z, outcome=rows.outcome)]
    for h, g in rows.groupby("horizon"):
        out.append(coverage_row(source, ALL, h, scope, calibrated, g[cov], g[isc], float(g.factor.mean()) if calibrated else 1.0, z, outcome=g.outcome))
    if by_area:
        for a, g in rows.groupby("area"):
            out.append(coverage_row(source, a, 0, scope, calibrated, g[cov], g[isc], float(g.factor.mean()) if calibrated else 1.0, z, outcome=g.outcome))
    return out


def evaluate(bt, model, rechoose, cal, source="bootstrap"):
    """Published factors and the coverage table for ranges scored in a rolling backtest.

    bt: backtest rows (area, method, origin_fy, horizon, forecast_fy, target, outcome, p10, p50, p90, covered,
    interval_score). model: the published choice (area, method). rechoose(rows) -> (area, method): the model that would
    have been chosen from a subset of the backtest, so the out-of-sample designs do not borrow the held-out rows.
    Returns (factors, coverage rows as a DataFrame with the columns COLS).
    """
    z = cal["wilson_z"]
    act = bt[bt.target == "actual"]
    chosen = _scored(act.merge(model[["area", "method"]], on=["area", "method"]))
    fs = factors(chosen, cal)
    rows = []
    if len(chosen):
        raw = chosen.assign(factor=1.0)
        rows += _cuts(raw, source, "in_sample", 0, "covered", "interval_score", z)
        rows += _cuts(_apply(chosen, fs), source, "in_sample", 1, "covered_cal", "iscore_cal", z)

    held = []
    for year in sorted(act.forecast_fy.unique()):
        train, test = act[act.forecast_fy != year], act[act.forecast_fy == year]
        m = rechoose(train)
        fit = _scored(train.merge(m, on=["area", "method"]))
        held.append(_apply(_scored(test.merge(m, on=["area", "method"])), factors(fit, cal)))
    if held:
        loyo = pd.concat(held, ignore_index=True)
        rows += _cuts(loyo.assign(factor=1.0), source, "out_of_sample", 0, "covered", "interval_score", z)
        rows += _cuts(loyo, source, "out_of_sample", 1, "covered_cal", "iscore_cal", z)

    held = []
    for origin in sorted(act.origin_fy.unique()):
        train, test = act[act.forecast_fy <= origin], act[act.origin_fy == origin]
        if train.empty:
            continue  # nothing was known at this origin to fit on, so its forecasts are not scored
        m = rechoose(train)
        fit = _scored(train.merge(m, on=["area", "method"]))
        if fit.empty:
            continue
        held.append(_apply(_scored(test.merge(m, on=["area", "method"])), factors(fit, cal)))
    if held:
        exp = pd.concat(held, ignore_index=True)
        rows += _cuts(exp.assign(factor=1.0), source, "expanding_origin", 0, "covered", "interval_score", z, by_area=False)
        rows += _cuts(exp, source, "expanding_origin", 1, "covered_cal", "iscore_cal", z, by_area=False)
    return fs, table(rows)


def table(rows):
    out = pd.DataFrame(rows, columns=COLS)
    for c in ("coverage", "cov_lo", "cov_hi", "factor", "relative_interval_score"):
        out[c] = pd.to_numeric(out[c]).round(4)
    out["mean_interval_score"] = pd.to_numeric(out["mean_interval_score"]).round(0)
    return out


def cqr_scores(lo, hi, outcome):
    """Conformalized quantile regression scores on the log1p scale: how far outside the range the outcome fell
    (negative when it is inside)."""
    lo, hi, y = (np.log1p(np.asarray(v, dtype=float)) for v in (lo, hi, outcome))
    return np.maximum(lo - y, y - hi)


def cqr_margin(scores, alpha=0.2):
    """The log1p margin added to both ends of a quantile range; never negative (a range is not narrowed)."""
    q = conformal_quantile(scores, alpha)
    return 0.0 if np.isnan(q) else float(max(0.0, q))


def cqr_widen(lo, hi, margin):
    lo, hi = (np.log1p(np.asarray(v, dtype=float)) for v in (lo, hi))
    return np.maximum(np.expm1(lo - margin), 0.0), np.expm1(hi + margin)


def adopt(candidate, incumbent, cal):
    """The pre-registered adoption rule for one horizon. candidate / incumbent: dicts with n, coverage and
    relative_interval_score, both measured out of sample. The candidate range replaces the incumbent only when both
    sides have at least `min_scored_for_adoption` scored forecasts, its coverage is strictly closer to nominal, and its
    interval score (relative to the outcome) is no worse. A tie keeps the incumbent."""
    need, nominal = cal["min_scored_for_adoption"], cal["nominal"]
    for side in (candidate, incumbent):
        if not side or side.get("n", 0) < need or side.get("coverage") is None or side.get("relative_interval_score") is None:
            return False
    closer = abs(candidate["coverage"] - nominal) < abs(incumbent["coverage"] - nominal) - 1e-12
    return bool(closer and candidate["relative_interval_score"] <= incumbent["relative_interval_score"] + 1e-12)
