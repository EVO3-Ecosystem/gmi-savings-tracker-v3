"""Model registry and drift monitor (roadmap Phase 5 closure, item 6).

mart.d_model_registry: one row per model the tracker runs. What it predicts or labels, its method, the baseline it must
beat, the window it learned from, the score it is judged on and the baseline's score on the same test, and the decision
(adopted, kept for review only, not promoted). Every number is read from the model's own evaluation table in this build;
nothing is typed in. A model that does not beat its baseline is never shown as a result (docs/roadmap.md, gates).

mart.d_drift: population stability index (PSI) and the two-sample Kolmogorov-Smirnov statistic between each Maryland
fiscal year and the one before, for the inputs the models learn from: payment amounts (log scale, decile bins of the
earlier year), the agency mix of payments, and the agency mix of the controllable budget. PSI below 0.10 is stable,
0.10-0.25 a moderate shift, above 0.25 a major shift (the usual credit-risk convention; Yurdakul 2018). A major shift
does not mean an error: FY2021-FY2022 federal relief moved the State's spending mix. It says which training years a
model's errors should be read against. When the previous run's payments are kept (data/raw/<run>/payments.parquet),
the same statistics compare the two runs' copies of each year (a republished year shows up here).
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
COLUMNS = ["model", "task", "method", "baseline", "training_window", "metric", "model_score", "baseline_score", "beats_baseline",
           "decision", "shown_as", "model_card"]


def _q(con, sql):
    try:
        return con.execute(sql).df()
    except Exception:  # noqa: BLE001 - a model whose table is missing is listed as not built
        return pd.DataFrame()


def registry(con):
    rows = []
    bt = _q(con, """SELECT b.method = m.method AS chosen, b.method, b.mase FROM mart.d_forecast_backtest b
                    JOIN mart.d_forecast_model m USING (area) WHERE b.target = 'actual'""")
    cal = _q(con, "SELECT * FROM mart.d_forecast_calibration WHERE area = 'All areas'")
    if len(bt):
        ch, nv = bt[bt.chosen].mase.mean(), bt[bt.method == "Naive (last actual)"].mase.mean()
        cov = f"; ranges cover {cal.calibrated_share.iloc[0]:.0%} out of sample after conformal widening ({cal.covered_share.iloc[0]:.0%} before)" if len(cal) and "calibrated_share" in cal else ""
        rows.append(["Spending forecast", "Controllable spending by focus area, FY2026-FY2031", "Per area: trend, drift, naive or their average, chosen by rolling-origin MASE",
                     "Naive (last actual)", "FY2017-FY2025 actuals; origins FY2021-FY2024", "Mean MASE, rolling origin, against actuals", ch, nv, ch <= nv + 1e-9,
                     "Adopted" + cov, "Forecasts tab ranges; calculator baseline", "docs/models/forecast.md"])
    cb = _q(con, "SELECT model, avg(mean_mase) AS mase, avg(coverage_80) AS cov80 FROM mart.d_challenger_backtest GROUP BY 1")
    ct = _q(con, "SELECT n_series, n_adopted FROM mart.d_challenger_total")
    if len(cb):
        lg = cb[cb.model.str.startswith("LightGBM")].iloc[0]
        nv = cb[cb.model.str.startswith("Naive")].iloc[0]
        ad = f"Adopted per series where it beats naive: {int(ct.n_adopted.iloc[0]):,} of {int(ct.n_series.iloc[0]):,}" if len(ct) else "Adopted per series"
        rows.append(["Spending challenger", "Agency x spending code x year (one global model)", "LightGBM quantile regression (p10/p50/p90)", "Naive (last actual)",
                     "FY2017-FY2025 actuals; origins FY2022-FY2024", f"Mean MASE (coverage of p10-p90: {lg.cov80:.0%} vs naive {nv.cov80:.0%})", lg.mase, nv.mase,
                     lg.mase <= nv.mase, ad, "Forecasts tab statewide corridor", "docs/models/challenger.md"])
    rv = _q(con, "SELECT * FROM mart.d_revenue_model")
    if len(rv):
        r = rv.iloc[0]
        rows.append(["General Fund revenue", "General Fund revenue, next fiscal years", r.method, "Naive (last actual)", f"Sourced closeouts through FY{int(r.last_actual_fy)}",
                     f"MASE, rolling origin (coverage of p10-p90: {r.coverage_80:.0%})", r.chosen_mase, r.naive_mase, r.chosen_mase <= r.naive_mase + 1e-9,
                     "Adopted", "Forecasts tab revenue corridor", "docs/models/revenue.md"])
    pc = _q(con, "SELECT method, metric, value FROM mart.d_payee_class_eval WHERE class = 'all'")
    if len(pc):
        v = {(m, k): x for m, k, x in pc.itertuples(index=False)}
        prom = v.get(("decision", "combined_promoted"), 0)
        rows.append(["Payee classifier", "Payee type for each payee name (business, government, non-profit, ...)", "TF-IDF character n-grams + logistic regression, combined with the name rules",
                     "Name rules (reference/payee_type_rules.csv)", f"{int(v.get(('model', 'training_names'), 0)):,} rule-labeled names; scored on {int(v.get(('sample', 'labeled'), 0)):,} hand-labeled",
                     "Macro F1 on the hand-labeled sample (model alone; combined with the rules it ties them)", v.get(("model", "macro_f1")), v.get(("rules", "macro_f1")),
                     bool(max(v.get(("model", "macro_f1"), 0), v.get(("combined", "macro_f1"), 0)) > v.get(("rules", "macro_f1"), 0)),
                     "Promoted" if prom else "Not promoted: the rules stay the label; the model feeds the review queue",
                     "Vendors tab payee types (rules); AI page review queue", "docs/models/payee_classifier.md"])
    gs = _q(con, "SELECT cosine_threshold, overlap_leads AS leads, groups FROM mart.d_grant_groups_sensitivity ORDER BY 1")
    if len(gs):
        rows.append(["Grant groups", "Grant descriptions grouped by meaning across grantor agencies", "TF-IDF word 1-2 grams, cosine threshold 0.85",
                     "No labeled baseline (unsupervised)", "FY2025 grants", "Overlap leads at cosine 0.80 / 0.85 / 0.90",
                     None, None, None, "Leads only: " + " / ".join(str(int(x)) for x in gs.leads) + " overlap leads at cosine " + " / ".join(f"{t:.2f}" for t in gs.cosine_threshold) + " (stable)", "Opportunities tab overlap leads", "docs/models/grant_groups.md"])
    cl = _q(con, "SELECT any_value(k_chosen) AS k, any_value(silhouette) AS s, any_value(fiscal_year) AS fy FROM mart.agency_clusters")
    if len(cl) and cl.k.iloc[0] is not None:
        rows.append(["Agency peer groups", "Agencies grouped by what they buy", "K-Means on spending-mix shares, k by silhouette", "k = 1 (no groups)",
                     f"FY{int(cl.fy.iloc[0])} actual spending", "Silhouette (0 = no structure, 1 = perfect)", cl.s.iloc[0], 0.0, bool(cl.s.iloc[0] > 0.25),
                     f"Shown, k = {int(cl.k.iloc[0])}", "Opportunities tab agency map", "docs/models/clustering.md"])
    an = _q(con, "SELECT count(*) AS n, count(*) FILTER (WHERE rule_detector_overlap <> 'none') AS both FROM mart.review_queue")
    if len(an):
        rows.append(["Anomaly flags", "Unusual vendor-agency payments and spending codes", "Isolation forest", "The rule detectors and bid list",
                     "FY2017-FY2025", "Flags also found by a rule detector or the bid list", float(an.both.iloc[0]) / max(1, int(an.n.iloc[0])), None, None,
                     f"Review queue only: {int(an.n.iloc[0]):,} flags, never savings", "Opportunities tab anomaly audit queue", "docs/models/anomaly.md"])
    db = _q(con, """SELECT avg(flagged_next_share) FILTER (WHERE cohort = 'Flagged') AS f, avg(flagged_next_share) FILTER (WHERE cohort = 'Not flagged') AS n
                    FROM mart.d_detector_backtest""")
    if len(db) and db.f.iloc[0] is not None:
        rows.append(["Opportunity detectors", "Peer gap, growth above trend, tail spend, leverage", "Rules with fixed thresholds (config/assumptions.yaml)",
                     "Like-sized units not flagged", "Rerun as of FY2022-FY2024, followed one year", "Share flagged again the next year (persistence)",
                     db.f.iloc[0], db.n.iloc[0], bool(db.f.iloc[0] > db.n.iloc[0]), "Leads, sized with stated rates", "Opportunities tab; detector backtest card",
                     "docs/models/opportunities.md"])
    out = pd.DataFrame(rows, columns=COLUMNS)
    for c in ("model_score", "baseline_score"):
        out[c] = pd.to_numeric(out[c]).round(4)
    return out


def psi(a, b, bins):
    """Population stability index of sample b against reference a over the given bin edges (empty bins floored at 1e-4)."""
    pa = np.histogram(a, bins)[0] / max(1, len(a))
    pb = np.histogram(b, bins)[0] / max(1, len(b))
    pa, pb = np.clip(pa, 1e-4, None), np.clip(pb, 1e-4, None)
    return float(np.sum((pb - pa) * np.log(pb / pa)))


def psi_shares(a, b):
    """PSI between two category-share Series (same categories; missing = 0)."""
    k = a.index.union(b.index)
    pa, pb = (s.reindex(k).fillna(0) for s in (a, b))
    pa, pb = np.clip(pa / pa.sum(), 1e-4, None), np.clip(pb / pb.sum(), 1e-4, None)
    return float(np.sum((pb - pa) * np.log(pb / pa)))


def ks(a, b):
    """Two-sample Kolmogorov-Smirnov statistic (largest gap between the two empirical distributions)."""
    a, b = np.sort(a), np.sort(b)
    grid = np.concatenate([a, b])
    return float(np.max(np.abs(np.searchsorted(a, grid, "right") / len(a) - np.searchsorted(b, grid, "right") / len(b))))


def level(p):
    return "Stable" if p < 0.10 else "Moderate shift" if p < 0.25 else "Major shift"


def drift(con):
    pay = con.execute("""SELECT fiscal_year, agency_code, amount, partial_year FROM core.fact_payment_mapped WHERE amount > 0""").df()
    bud = con.execute("SELECT fiscal_year, agency_code, sum(spend) AS b FROM mart.f_code WHERE stage = 'Actual' GROUP BY 1, 2").df() \
        if con.execute("SELECT count(*) FROM information_schema.columns WHERE table_schema = 'mart' AND table_name = 'f_code' AND column_name = 'stage'").fetchall()[0][0] else pd.DataFrame()
    rows = []
    years = sorted(pay.fiscal_year.unique())
    for y0, y1 in zip(years, years[1:]):
        a, b = np.log10(pay[pay.fiscal_year == y0].amount.values), np.log10(pay[pay.fiscal_year == y1].amount.values)
        edges = np.unique(np.quantile(a, np.linspace(0, 1, 11)))
        edges[0], edges[-1] = -np.inf, np.inf
        p = psi(a, b, edges)
        part = bool(pay[pay.fiscal_year == y1].partial_year.any())
        rows.append(["Payments", "Payment amount (log scale)", y0, y1, p, ks(a, b), level(p), part])
        s0 = pay[pay.fiscal_year == y0].groupby("agency_code").amount.sum()
        s1 = pay[pay.fiscal_year == y1].groupby("agency_code").amount.sum()
        p = psi_shares(s0, s1)
        rows.append(["Payments", "Agency mix of payments", y0, y1, p, None, level(p), part])
    if len(bud):
        by = sorted(bud.fiscal_year.unique())
        for y0, y1 in zip(by, by[1:]):
            p = psi_shares(bud[bud.fiscal_year == y0].set_index("agency_code").b, bud[bud.fiscal_year == y1].set_index("agency_code").b)
            rows.append(["Budget", "Agency mix of controllable spending (actual)", y0, y1, p, None, level(p), False])
    out = pd.DataFrame(rows, columns=["dataset", "measure", "from_fy", "to_fy", "psi", "ks", "level", "partial_year"])
    out["psi"] = out.psi.round(4)
    out["ks"] = pd.to_numeric(out.ks).round(4)
    return out


def write(con):
    for name, df in (("d_model_registry", registry(con)), ("d_drift", drift(con))):
        con.register("_df", df)
        con.execute(f"CREATE OR REPLACE TABLE mart.{name} AS SELECT * FROM _df")
        con.unregister("_df")
