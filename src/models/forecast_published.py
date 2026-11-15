"""Rebuild the area forecast from the published tables alone and check it against what was published.

    python -m src.models.forecast_published --check       # exit 1 unless the rebuild equals site_data/f_forecast.csv
    python -m src.models.forecast_published --out DIR     # also write the rebuilt tables, calibrated ranges included

The forecast reads only three marts (f_code, f_scope, f_fund), and all three are published unfiltered, so anyone
with the repository can reproduce the published forecast, its rolling backtest and the range calibration without
the warehouse. The check compares the raw columns: the published files were rounded to cents on export.
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

from . import forecast as F

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site_data"


def load(site=SITE):
    return tuple(pd.read_csv(site / f"{t}.csv", dtype={"agency_code": str, "code": str}) for t in ("f_code", "f_scope", "f_fund"))


def rebuild(site=SITE, cfg=None):
    """(f_forecast with calibrated ranges, d_forecast_model, d_forecast_backtest, d_forecast_calibration, d_range_coverage)."""
    f, m, bt = F.build(*load(site), cfg)
    cal = F.calibration(bt, m)
    f, cov = F.calibrate(f, m, bt, cfg)
    return {"f_forecast": f, "d_forecast_model": m, "d_forecast_backtest": bt, "d_forecast_calibration": cal, "d_range_coverage": cov}


def differences(tables, site=SITE, tolerance=1.0):
    """Mismatches between the rebuild and the published f_forecast / d_forecast_model, as a list of messages."""
    out = []
    for name, keys in (("f_forecast", ["area", "fiscal_year", "kind"]), ("d_forecast_model", ["area"])):
        pub = pd.read_csv(site / f"{name}.csv")
        new = tables[name][[c for c in pub.columns if c in tables[name].columns]]
        missing = [c for c in pub.columns if c not in new.columns]
        if missing:
            out.append(f"{name}: published columns not rebuilt: {missing}")
        j = pub.merge(new, on=keys, how="outer", suffixes=("_pub", "_new"), indicator=True)
        if (j._merge != "both").any():
            out.append(f"{name}: {(j._merge != 'both').sum()} rows differ in {keys}")
        for c in (c for c in pub.columns if c not in keys and c in new.columns):
            a, b = j[f"{c}_pub"], j[f"{c}_new"]
            if pd.api.types.is_numeric_dtype(a) and pd.api.types.is_numeric_dtype(b):
                tol = tolerance if a.abs().max() > 1000 else 1e-4
                bad = ~(((a - b).abs() <= tol) | (a.isna() & b.isna()))
            else:
                bad = ~((a.fillna("") == b.fillna("")))
            if bad.any():
                out.append(f"{name}.{c}: {int(bad.sum())} values differ")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="exit 1 unless the rebuild matches the published forecast")
    ap.add_argument("--out", help="write the rebuilt tables as CSV into this directory")
    args = ap.parse_args(argv)
    tables = rebuild()
    diffs = differences(tables)
    for d in diffs:
        print("DIFFERENT", d)
    if not diffs:
        print(f"forecast rebuilt from site_data matches the published f_forecast ({len(tables['f_forecast'])} rows) and d_forecast_model")
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        for name, df in tables.items():
            df.to_csv(out / f"{name}.csv", index=False)
    if not args.check or args.out:
        cov = tables["d_range_coverage"]
        print(cov[cov.area == "All areas"].to_string(index=False))
    return 1 if (args.check and diffs) else 0


if __name__ == "__main__":
    sys.exit(main())
