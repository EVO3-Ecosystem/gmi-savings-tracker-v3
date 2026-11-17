"""Detector backtest, first stage: do opportunity flags recur, and what did flagged spending do next year? (roadmap gap 16)

Each detector in src/models/opportunities.py is rerun as of an earlier year T (FY2022, FY2023, FY2024) on data up to T only,
with the live thresholds and the same look-back (growth compares T with T-3; the payment detectors use year-T payments). It
is then rerun as of T+1, and the year-T units are followed into T+1. Everything below was fixed before measuring:

  Units      Peer gap and Growth: an agency and spending code (controllable, actual budget). Tail spend: a focus area.
             Leverage: a private vendor.
  Cohorts    Flagged: the detector's own flags at T (before the two budget detectors are de-duplicated against each other).
             Not flagged: units that passed the detector's size and comparability filters at T but were not flagged, so the
             comparison is between like-sized units:
               Peer gap  agency with 50+ positions, 8+ comparable agencies on the code, $250k+ on the code
               Growth    $1M+ prior-year base (T-3) and $500k+ at T, with a finite statewide growth rate on the code
               Tail spend  every focus area with private payments at T
               Leverage  private vendors paid $5M+ at T
  Window     T to T+1, one year. T+1 is always an actual year (FY2023-FY2025 budget, FY2023-FY2025 payments).
  Measures   units; flagged at T+1 (the same detector, rerun as of T+1); spending at T and T+1 summed over the cohort's units
             (controllable budget for the budget detectors, private payments for the payment detectors: the area's vendors
             outside the ten largest at T for Tail spend, the vendor's payments for Leverage); the pooled change; the median
             per-unit change (units with spending at T); units with no spending at T+1.

Descriptive only: flagged and unflagged units differ in more than the flag, budgets are re-coded between years, and a fall
next year is not evidence that a saving was made or could be. Cohorts of different detectors overlap (the same spending is
seen from the budget and the payments side), so no row may be added to another.
"""
import numpy as np
import pandas as pd

from . import calibration as C
from . import opportunities

AS_OF = (2022, 2023, 2024)
DETECTORS = ("Peer gap", "Growth above trend", "Tail spend", "Leverage")
COLUMNS = ["detector", "as_of_fy", "next_fy", "cohort", "units", "flagged_next", "flagged_next_share", "spend_as_of", "spend_next",
           "pooled_change", "median_change", "units_zero_next"]


def _cfg(cfg, t):
    c = {k: (dict(v) if isinstance(v, dict) else v) for k, v in cfg.items()}
    c["current_fy"], c["base_fy"], c["payments_fy"] = t, t - (cfg["current_fy"] - cfg["base_fy"]), t
    return c


def screen(code_agency, agency_year, payments, cfg):
    """Every detector's eligible units at cfg['current_fy'] / cfg['payments_fy'] with a `flag` column, using exactly the rules of
    opportunities.detect (tests/test_backtest.py checks that the flags equal detect()'s findings). Returns {detector: frame}."""
    y, y0, py = cfg["current_fy"], cfg["base_fy"], cfg["payments_fy"]
    pg, gr, tl, lv = cfg["peer_gap"], cfg["growth"], cfg["tail_spend"], cfg["leverage"]
    c = code_agency[(code_agency.controllable.astype(str) == "True") & (code_agency.stage == "Actual")]
    fte = agency_year[agency_year.fiscal_year == y].set_index("agency_code").fte
    key = ["agency_code", "code", "comptroller_subobject_name", "area"]
    cur = c[c.fiscal_year == y].groupby(key, dropna=False).budget.sum().reset_index()
    cur["fte"] = pd.to_numeric(cur.agency_code.map(fte), errors="coerce")  # a year with no rows maps to a string dtype in pandas 3
    pe = cur[(cur.fte >= pg["min_positions"]) & (cur.budget > 0)].copy()
    pe["per"] = pe.budget / pe.fte
    st = pe.groupby("code").per.agg(p75=lambda s: s.quantile(pg["percentile"]), n="count")
    pe = pe.join(st, on="code")
    pe = pe[(pe.n >= pg["min_agencies"]) & (pe.budget >= pg["min_budget"])].copy()
    pe["flag"] = pe.per > pe.p75
    old = c[c.fiscal_year == y0].groupby(key, dropna=False).budget.sum().rename("old")
    g = cur.set_index(key).join(old).reset_index()
    state = g.groupby("code")[["budget", "old"]].sum()
    g = g.join((state.budget / state.old - 1).rename("sg"), on="code")
    g = g[(g.old > gr.get("min_base_budget", 0)) & (g.budget >= gr["min_budget"]) & np.isfinite(g.sg)].copy()
    g["flag"] = (g.budget / g.old - 1) > g.sg + gr["points_above_state"]
    unit = lambda d: d.groupby(["agency_code", "code"]).agg(flag=("flag", "any"), spend=("budget", "sum")).reset_index()  # noqa: E731
    p = payments[(payments.fiscal_year == py) & ~payments.is_government.astype(bool) & ~payments.passthrough.astype(bool)]
    a = p[p.area.notna()].groupby(["area", "vendor"]).amount.sum().reset_index().sort_values(["area", "amount"], ascending=[True, False], kind="stable")
    a["rank"] = a.groupby("area").cumcount()
    tail = a[a["rank"] >= tl["top_vendors"]].groupby("area").agg(spend=("amount", "sum"), vendors=("vendor", list))
    tail = tail.reindex(pd.Index(a.area.unique(), name="area"), fill_value=0).reset_index()
    tail["vendors"] = [v if isinstance(v, list) else [] for v in tail.vendors]
    tail["flag"] = tail.spend > tl["min_tail"]
    v = p.groupby("vendor").agg(spend=("amount", "sum"), agencies=("agency_code", "nunique")).reset_index()
    v = v[v.spend >= lv["min_spend"]].copy()
    v["flag"] = v.agencies >= lv["min_agencies"]
    return {"Peer gap": unit(pe), "Growth above trend": unit(g), "Tail spend": tail, "Leverage": v}


def _next_spend(det, units, code_agency, payments, t1):
    if det in ("Peer gap", "Growth above trend"):
        c = code_agency[(code_agency.controllable.astype(str) == "True") & (code_agency.stage == "Actual") & (code_agency.fiscal_year == t1)]
        s = c.groupby(["agency_code", "code"]).budget.sum()
        return units.set_index(["agency_code", "code"]).index.map(lambda k: s.get(k, 0.0)).to_numpy(dtype=float)
    p = payments[(payments.fiscal_year == t1) & ~payments.is_government.astype(bool) & ~payments.passthrough.astype(bool)]
    if det == "Leverage":
        s = p.groupby("vendor").amount.sum()
        return units.vendor.map(s).fillna(0.0).to_numpy(dtype=float)
    s = p[p.area.notna()].groupby(["area", "vendor"]).amount.sum()
    return np.array([sum(s.get((ar, vn), 0.0) for vn in vs) for ar, vs in zip(units.area, units.vendors)], dtype=float)


def _key(det):
    return {"Tail spend": ["area"], "Leverage": ["vendor"]}.get(det, ["agency_code", "code"])


def run(code_agency, agency_year, payments, cfg=None, as_of=AS_OF):
    """One row per detector, as-of year and cohort (Flagged / Not flagged), in COLUMNS order."""
    cfg = cfg or opportunities.assumptions()
    rows = []
    for t in as_of:
        upto = lambda d, yr: d[d.fiscal_year <= yr]  # noqa: E731  only data up to the as-of year
        now = screen(upto(code_agency, t), upto(agency_year, t), upto(payments, t), _cfg(cfg, t))
        nxt = screen(upto(code_agency, t + 1), upto(agency_year, t + 1), upto(payments, t + 1), _cfg(cfg, t + 1))
        for det in DETECTORS:
            u, k = now[det].copy(), _key(det)
            later = set(map(tuple, nxt[det].loc[nxt[det].flag, k].to_numpy()))
            u["flag_next"] = [tuple(r) in later for r in u[k].to_numpy()]
            u["spend_next"] = _next_spend(det, u, code_agency, payments, t + 1)
            for cohort, part in (("Flagged", u[u.flag]), ("Not flagged", u[~u.flag])):
                s0, s1 = float(part.spend.sum()), float(part.spend_next.sum())
                pos = part[part.spend > 0]
                rows.append({"detector": det, "as_of_fy": t, "next_fy": t + 1, "cohort": cohort, "units": len(part),
                             "flagged_next": int(part.flag_next.sum()), "flagged_next_share": part.flag_next.mean() if len(part) else None,
                             "spend_as_of": s0, "spend_next": s1, "pooled_change": s1 / s0 - 1 if s0 else None,
                             "median_change": float((pos.spend_next / pos.spend - 1).median()) if len(pos) else None,
                             "units_zero_next": int((part.spend_next <= 0).sum())})
    return pd.DataFrame(rows, columns=COLUMNS)


BID = "Bid list"
OUTCOMES = ("flagged_again", "fell", "grew_slower_than_peers")
OUT_COLS = ["detector", "as_of_fy", "horizon", "follow_fy", "cohort", "units", "outcome", "hits", "rate", "rate_lo", "rate_hi", "spend_as_of",
            "spend_follow", "pooled_change", "median_change"]
LIFT_COLS = ["detector", "horizon", "outcome", "as_of_years", "flagged_units", "flagged_hits", "flagged_rate", "base_units", "base_hits",
             "base_rate", "lift", "lift_lo", "lift_hi", "rate_diff"]


def _full():
    import yaml
    return yaml.safe_load((opportunities.ROOT / "config" / "assumptions.yaml").read_text())


def _bid_units(agency_year, payments, cfg):
    """The bid list as a fifth detector: units are private vendors paid at least the bid list's minimum in the payments
    year (agencies the list excludes left out); flagged = on the list opportunities.bid_list builds from the same data."""
    bl, py = cfg["bid_list"], cfg["payments_fy"]
    p = payments[(payments.fiscal_year == py) & ~payments.is_government.astype(bool) & ~payments.passthrough.astype(bool)
                 & ~payments.agency_code.isin(bl["excluded_agency_codes"])]
    v = p.groupby("vendor").amount.sum().rename("spend").reset_index()
    v = v[v.spend >= bl["min_spend"]].copy()
    listed = set(opportunities.bid_list(payments, agency_year, cfg).vendor.str.upper()) if len(v) else set()
    v["flag"] = v.vendor.str.upper().isin(listed)
    return v


def _screen_all(code_agency, agency_year, payments, cfg, t):
    upto = lambda d: d[d.fiscal_year <= t]  # noqa: E731  only data up to the as-of year
    c = _cfg(cfg, t)
    out = screen(upto(code_agency), upto(agency_year), upto(payments), c)
    out[BID] = _bid_units(upto(agency_year), upto(payments), c)
    return out


def katz(a, n1, c, n2, z=1.96):
    """Risk ratio (a / n1) / (c / n2) with the Katz log interval for two independent groups; (ratio, low, high), or
    (None, None, None) when either group has no hits (the log interval is undefined)."""
    if not a or not c or not n1 or not n2:
        return None, None, None
    rr = (a / n1) / (c / n2)
    se = np.sqrt(1 / a - 1 / n1 + 1 / c - 1 / n2)
    return float(rr), float(rr * np.exp(-z * se)), float(rr * np.exp(z * se))


def outcomes(code_agency, agency_year, payments, cfg=None, bt=None):
    """How past flags turned out. Returns (d_detector_outcomes, d_detector_lift).

    Every detector is rerun as of each year T in the pre-registered list on data up to T only, and its units are followed
    1 to 3 years on (while T + h is an actual year). Three descriptive outcomes per unit, defined in config before any
    real run: flagged_again (the same detector flags the unit at T + h), fell (spending at T + h is at least `min_drop`
    below spending at T), grew_slower_than_peers (the unit's change is below the pooled change of every eligible unit).
    Lift compares flagged with not-flagged units, pooled over as-of years, with a Katz log interval.

    These are shares of flags followed by an outcome, not precision and not savings. Growth flags are selected on a high
    value, so some later fall is regression to the mean; the comparison with unflagged units reduces that but does not
    remove it, because unflagged units were not selected on a high value."""
    cfg = cfg or opportunities.assumptions()
    bt = bt or _full()["detector_backtest"]
    z, need, drop = bt["wilson_z"], bt["min_units_for_rate"], bt["outcomes"]["fell"]["min_drop"]
    budget_years, pay_years = list(bt["as_of"]), list(bt["as_of"]) + list(bt.get("payment_as_of_extra", []))
    cache = {}

    def at(t):
        if t not in cache:
            cache[t] = _screen_all(code_agency, agency_year, payments, cfg, t)
        return cache[t]
    rows = []
    for det in (*DETECTORS, BID):
        budget = det in ("Peer gap", "Growth above trend")
        last = bt["last_actual_fy"] if budget else bt["last_payments_fy"]
        key = ["vendor"] if det == BID else _key(det)
        for t in (budget_years if budget else pay_years):
            u0 = at(t)[det]
            for h in bt["horizons"]:
                if t + h > last or not len(u0):
                    continue
                u = u0.copy()
                later = at(t + h)[det]
                again = set(map(tuple, later.loc[later.flag, key].to_numpy()))
                u["follow"] = _next_spend("Leverage" if det == BID else det, u, code_agency, payments, t + h)
                pos = u.spend > 0
                pooled = float(u.follow.sum() / u.spend.sum() - 1) if u.spend.sum() else np.nan
                change = np.where(pos, u.follow / u.spend.where(pos, 1) - 1, np.nan)
                u["flagged_again"] = [tuple(r) in again for r in u[key].to_numpy()]
                u["fell"] = pos & (u.follow <= (1 - drop) * u.spend)
                u["grew_slower_than_peers"] = pos & (change < pooled)
                u["change"] = change
                for cohort, part in (("Flagged", u[u.flag]), ("Not flagged", u[~u.flag]), ("All eligible", u)):
                    s0, s1 = float(part.spend.sum()), float(part.follow.sum())
                    for o in OUTCOMES:
                        n, hits = len(part), int(part[o].sum())
                        lo, hi = C.wilson(hits, n, z)
                        ok = n >= need
                        rows.append({"detector": det, "as_of_fy": t, "horizon": h, "follow_fy": t + h, "cohort": cohort, "units": n, "outcome": o,
                                     "hits": hits, "rate": hits / n if ok else None, "rate_lo": lo if ok else None, "rate_hi": hi if ok else None,
                                     "spend_as_of": s0, "spend_follow": s1, "pooled_change": s1 / s0 - 1 if s0 else None,
                                     "median_change": float(np.nanmedian(part.change)) if part.change.notna().any() else None})
    out = pd.DataFrame(rows, columns=OUT_COLS)
    lift = []
    for (det, h, o), g in out.groupby(["detector", "horizon", "outcome"], sort=False):
        f, b = g[g.cohort == "Flagged"], g[g.cohort == "Not flagged"]
        a, n1, c, n2 = int(f.hits.sum()), int(f.units.sum()), int(b.hits.sum()), int(b.units.sum())
        ok = n1 >= need and n2 >= need
        rr, lo, hi = katz(a, n1, c, n2, z) if ok else (None, None, None)
        lift.append({"detector": det, "horizon": h, "outcome": o, "as_of_years": int(f.as_of_fy.nunique()), "flagged_units": n1, "flagged_hits": a,
                     "flagged_rate": a / n1 if ok else None, "base_units": n2, "base_hits": c, "base_rate": c / n2 if ok else None,
                     "lift": rr, "lift_lo": lo, "lift_hi": hi, "rate_diff": a / n1 - c / n2 if ok else None})
    return out, pd.DataFrame(lift, columns=LIFT_COLS)


def write(con, cfg=None):
    code_agency, agency_year, payments, _ = opportunities.inputs(con)  # clusters are FY2025-only; the historical screen stays statewide
    df = run(code_agency, agency_year, payments, cfg)
    out, lift = outcomes(code_agency, agency_year, payments, cfg)
    for name, d in (("d_detector_backtest", df), ("d_detector_outcomes", out), ("d_detector_lift", lift)):
        con.register("_df", d)
        con.execute(f"CREATE OR REPLACE TABLE mart.{name} AS SELECT * FROM _df")
        con.unregister("_df")
    return len(df)
