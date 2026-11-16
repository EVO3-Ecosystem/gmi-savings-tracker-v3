"""Statewide program screen: every budget program of every agency screened the same way, with audit findings beside it.

The child care overpayments reported in November 2026 (docs/research/childcare-overpayments.md) could not have been
detected from open data, but the program stood out in it: spending rose sevenfold in eight years and swung by a third
from year to year. This module applies that reading to all programs, not one.

For each agency, unit and program with enough actual years and enough spending (config/assumptions.yaml,
`program_screen`), from the operating budget's actual spending:
  growth_multiple   last actual year over the first
  largest_swing     the largest year-to-year change, up or down, as a share of the earlier year
  signals           how many of the two thresholds the program crosses (fast growth, large swing): 0, 1 or 2
Beside it, by agency: the latest Office of Legislative Audits report (findings, repeat findings), and by program: any
reported finding in reference/audit_findings_override.csv with its amount and recoupment status.

What it is: an order in which to ask questions. What it is not: a finding, a risk score or evidence of error. Programs
grow and swing for ordinary reasons (new law, federal relief money, a program renamed or merged), and an audit of an
agency says little about any one of its programs.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
KEY = ["agency_code", "unit_name", "program_code"]
COLUMNS = ["agency_code", "agency", "unit_name", "program_code", "program_name", "years", "first_fy", "last_fy", "spend_first", "spend_last",
           "growth_multiple", "largest_swing", "swing_fy", "fast_growth", "large_swing", "signals", "ola_report_date", "ola_findings",
           "ola_repeat_findings", "reported_findings", "reported_amount", "recoupment_status"]


def assumptions():
    return yaml.safe_load((ROOT / "config" / "assumptions.yaml").read_text())["program_screen"]


def screen(f_program, ola=None, reported=None, agencies=None, cfg=None):
    """One row per screened program, most signals first, then largest. f_program: fiscal_year, stage, agency_code,
    unit_name, program_code, program_name, budget. ola: reference/ola_findings.csv. reported: the override file.
    agencies: agency_code -> name."""
    cfg = cfg or assumptions()
    a = f_program[(f_program.stage == "Actual") & f_program.fiscal_year.between(cfg["first_fy"], cfg["last_actual_fy"])]
    s = a.groupby(KEY + ["fiscal_year"], dropna=False).budget.sum().reset_index().sort_values(KEY + ["fiscal_year"])
    name = a.sort_values("fiscal_year").groupby(KEY, dropna=False).program_name.last()
    rows = []
    for k, g in s.groupby(KEY, dropna=False):
        g = g[g.budget > 0]
        if len(g) < cfg["min_years"] or g.budget.iloc[-1] < cfg["min_spend"]:
            continue
        y, v = g.fiscal_year.to_numpy(), g.budget.to_numpy(dtype=float)
        consecutive = np.diff(y) == 1  # a swing is only measured between adjacent years
        change = np.where(consecutive, v[1:] / v[:-1] - 1, np.nan)
        i = int(np.nanargmax(np.abs(change))) if np.isfinite(change).any() else None
        mult = v[-1] / v[0]
        swing = float(change[i]) if i is not None else np.nan
        fast, big = bool(mult >= cfg["fast_growth_multiple"]), bool(abs(swing) >= cfg["large_swing"]) if i is not None else False
        rows.append({**dict(zip(KEY, k)), "program_name": name.get(k), "years": len(g), "first_fy": int(y[0]), "last_fy": int(y[-1]),
                     "spend_first": v[0], "spend_last": v[-1], "growth_multiple": mult, "largest_swing": swing,
                     "swing_fy": int(y[i + 1]) if i is not None else None, "fast_growth": fast, "large_swing": big, "signals": int(fast) + int(big)})
    out = pd.DataFrame(rows)
    if out.empty:
        return pd.DataFrame(columns=COLUMNS)
    out["agency"] = [(agencies or {}).get(a, a) for a in out.agency_code]
    if ola is not None and len(ola):
        o = ola.sort_values("report_date").groupby("agency_code").last()
        for col, src in (("ola_report_date", "report_date"), ("ola_findings", "findings"), ("ola_repeat_findings", "repeat_findings")):
            out[col] = out.agency_code.map(o[src])
    if reported is not None and len(reported):
        r = reported[reported.program_code.astype(str) != ""].copy()
        r["amount"] = pd.to_numeric(r.amount, errors="coerce")
        g = r.groupby(["agency_code", "program_code"]).agg(
            reported_findings=("finding_id", "size"), reported_amount=("amount", "max"),  # rows can contain each other, so the largest, not the sum
            recoupment_status=("recoupment_status", lambda x: "; ".join(sorted({v for v in x if v}))))
        out = out.join(g, on=["agency_code", "program_code"])
    for c in COLUMNS:
        if c not in out:
            out[c] = None
    out["reported_findings"] = out.reported_findings.fillna(0).astype(int)
    for c in ("growth_multiple", "largest_swing"):
        out[c] = out[c].round(4)
    return out.sort_values(["signals", "spend_last"], ascending=[False, False])[COLUMNS].reset_index(drop=True)


def reference():
    """(ola findings, reported findings) from reference/."""
    ola = pd.read_csv(ROOT / "reference" / "ola_findings.csv", dtype={"agency_code": str})
    rep = pd.read_csv(ROOT / "reference" / "audit_findings_override.csv", dtype=str, keep_default_na=False)
    return ola, rep


def write(con, cfg=None):
    """Build mart.d_program_screen from mart.f_program and the reference files."""
    have = {r[0] for r in con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'mart'").fetchall()}
    if not {"f_program", "agency_year"} <= have:
        return 0  # the program mart is not part of this build
    f = con.execute("SELECT * FROM mart.f_program").df()
    names = con.execute("SELECT agency_code, agency, fiscal_year FROM mart.agency_year").df()
    names = names.sort_values("fiscal_year").groupby("agency_code").agency.last().to_dict()
    ola, rep = reference()
    df = screen(f, ola, rep, names, cfg)
    con.register("_df", df)
    con.execute("CREATE OR REPLACE TABLE mart.d_program_screen AS SELECT * FROM _df")
    con.unregister("_df")
    return len(df)
