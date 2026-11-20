"""Fiscal-year coverage guard: every published table covers every year its source has.

    python -m src.pipeline.coverage [--data site_data]     # report; exit 1 when a table loses years

Each published table with a fiscal_year column is listed in reference/year_coverage.csv with a family:
  payments  first year <= years.history_first_fy, last year = the latest payments year (the open year when there is one)
  grants    first year <= years.history_first_fy, last year = the latest grants year
  budget    first year = the budget data's first year, last year = the latest budget year
  mixed     first year <= years.history_first_fy, last year = the latest budget or payments year
  narrow    a deliberate subset of years; the reason column says why, and nothing is checked
A table with a fiscal_year column that is not listed fails too, so a new table cannot skip the guard.
The same rules run in the build (src/pipeline/checks.py, against the marts) and in tests/test_year_coverage.py
(against the published site_data/), so a lost year stops the build and fails CI.
"""
import argparse
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / "reference" / "year_coverage.csv"


def history_first():
    return int(yaml.safe_load((ROOT / "config" / "assumptions.yaml").read_text())["years"]["history_first_fy"])


def bounds(years_of):
    """years_of(name) -> (min, max) for a table, or None when it is missing. Returns the source bounds by family."""
    pay, bud, gr = years_of("totals_by_fy"), years_of("f_function"), years_of("f_grants")
    return {"payments": pay, "budget": bud, "grants": gr,
            "mixed": (min(pay[0], bud[0]), max(pay[1], bud[1])) if pay and bud else None}


def problems(tables, years_of, first=None, require_listed=True):
    """tables: names of published tables that have a fiscal_year column. years_of(name) -> (min, max).
    Returns a list of plain-language problems; empty when every table covers its source's years."""
    first = history_first() if first is None else first
    ref = pd.read_csv(REF).set_index("table")
    src = bounds(years_of)
    out = []
    for t in sorted(set(tables) - set(ref.index)):
        out.append(f"{t} has a fiscal_year column but no row in reference/year_coverage.csv")
    for t, r in ref.iterrows():
        if r.family == "narrow":
            if not str(r.reason).strip():
                out.append(f"{t} is listed as narrow without a reason")
            continue
        if t not in tables:
            if require_listed:  # the published snapshot must carry every listed table; a partial build checks what it has
                out.append(f"{t} is listed ({r.family}) but not published")
            continue
        lo, hi = years_of(t)
        want = src.get(r.family)
        if want is None:
            out.append(f"{t}: the {r.family} source bounds are unknown")
            continue
        need_lo = want[0] if r.family == "budget" else max(first, want[0])
        if lo > need_lo:
            out.append(f"{t} starts FY{lo}; its {r.family} source has FY{need_lo} (years.history_first_fy = FY{first})")
        if hi < want[1]:
            out.append(f"{t} ends FY{hi}; its {r.family} source runs to FY{want[1]}")
    return out


def from_csv(folder):
    """Fiscal-year bounds of the published CSVs in folder (site_data/ or an export)."""
    folder = Path(folder)
    have = {}
    for f in sorted(folder.glob("*.csv")):
        cols = pd.read_csv(f, nrows=0).columns
        if "fiscal_year" in cols:
            y = pd.read_csv(f, usecols=["fiscal_year"]).fiscal_year.dropna()
            if len(y):
                have[f.stem] = (int(y.min()), int(y.max()))
    return have


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", default=str(ROOT / "site_data"))
    a = ap.parse_args(argv)
    have = from_csv(a.data)
    bad = problems(set(have), lambda t: have.get(t))
    for t, (lo, hi) in sorted(have.items()):
        print(f"FY{lo}-FY{hi}  {t}")
    print("\n" + ("\n".join("FAIL " + b for b in bad) if bad else f"year coverage: {len(have)} tables, every one covers its source's years"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
