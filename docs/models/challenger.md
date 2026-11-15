# Model card — LightGBM quantile challenger (`src/models/challenger.py`)

## What it does
Forecasts next year's controllable spending for every agency x spending-code series (2,609 series for FY2026) with a
global LightGBM quantile model (alpha 0.1 / 0.5 / 0.9 — the fiscal risk corridor), **kept only where it beats the
naive last-value forecast** in rolling-origin validation. Everything else stays naive, and each row names its model.

## Why quantile regression
Decision #25/#26 of the review: P10-P90 corridors instead of a point estimate, produced by quantile objectives rather
than bootstrap alone, so best- and worst-case bounds come from the model itself.

## Features (lagged only — no current or future value enters a training row)
Log spend lags 1-3, lag-1 log growth, 3-lag mean, the agency's and the code's prior-year log totals, and the year index.

## Validation (rolling origin, never shuffled)
- Origins FY2022, FY2023, FY2024: train through the origin, predict the next year
- MASE per series, scale from each origin's own training window; adoption requires at least 2 scored origins and a
  strictly lower mean MASE than naive (a stop check re-verifies this on every build)
- Band coverage measured on the same origins and reported as a build warning: 73.2% vs the nominal 80%
  (bands are honest but narrow; treat the p10/p90 as "likely", not "certain")
- First build: challenger kept for 1,083 of 2,609 series (41.5%)

## Calibrated bands (added Nov 15, 2026)
Quantile regression has no finite-sample coverage guarantee, and the raw bands held 73.2% against a nominal 80%.
Each band is now widened by conformalized quantile regression
([Romano, Patterson and Candes 2019](https://arxiv.org/abs/1905.03222)): the margin added to both ends on the log
scale is the conformal quantile of how far outside its band each backtest outcome fell, fitted separately for the
LightGBM rows and the naive rows. `f_challenger` keeps the raw `p10`/`p90` and adds `p10_cal`/`p90_cal`.
- Out-of-sample coverage is measured at each origin after the first, with a margin fitted only on earlier origins
  (`mart.d_range_coverage`, source `lightgbm` and `naive band`). **Measured coverage: pending the next pipeline run**
  (the challenger needs the warehouse).
- The per-series backtest rows are kept in `mart.d_challenger_series_backtest`.

## Area ranges for the adoption rule
The area forecast ([forecast.md](forecast.md)) may take a LightGBM-based range for its first forecast year. Per-series
quantiles are not additive, so the area range is not built from them. The challenger's growth for an area (sum of its
series medians over the sum of their last actuals) is applied to the area's actual total, and the range is that point
times exp(+/- margin), where the margin is the conformal quantile of the absolute log error of the same construction
at earlier origins, pooled over areas. With origins FY2022 to FY2024 and eight areas this gives 16 out-of-sample
forecasts, compared with the calibrated bootstrap range at horizon 1 under the rule in `config/assumptions.yaml`
(`calibration.adopt_rule`). **Result: pending the next pipeline run.**

## Statewide corridor (`mart.d_challenger_total`)
Per-series p10/p90 are not additive — every series does not hit its own tail in the same year — so the statewide
corridor is simulated: each series is drawn log-normally around its median with the log sigma of its calibrated band,
times one shock shared by every series in the path, and the draws are summed path by path (4,000 paths, seeded).
The shared shock's log sigma is the root mean square of the statewide miss over the backtest origins
(`common_shock_sigma` in the table). Until Nov 15, 2026 the draws were independent and clamped to each band's edges,
which removed both tails and left out the year-wide shock, so the corridor was too narrow. The published corridor
predates this change and will move on the next pipeline run.
One row per build: fiscal_year, p10/p50/p90, n_series, n_adopted, common_shock_sigma. A stop check verifies the band
is ordered, covers every series, and sits within 0.5x-2x of the last actual controllable total.

## Limits
- One-year-ahead only; nine actual years is a short history for a global model
- No macro regressors yet (CPI is loaded; BLS employment and BEA GDP are the planned additions)
- Revenue is forecast separately (`reference/gf_revenue_history.csv`); this model covers spending only
