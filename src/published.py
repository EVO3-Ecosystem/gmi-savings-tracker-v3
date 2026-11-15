"""Read-only access to the published tables in site_data/ (what the site, the data release and the notebook use).

    from src import published as P
    P.load("f_forecast")      # one published table as a DataFrame
    P.tables()                # names of every published table
    P.run_info()              # export id, run id, check counts of the last published run

No model logic lives here and nothing reads the warehouse.
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site_data"


def tables():
    return sorted(p.stem for p in (SITE / "parquet").glob("*.parquet"))


def has(name):
    return (SITE / "parquet" / f"{name}.parquet").is_file()


def load(name):
    return pd.read_parquet(SITE / "parquet" / f"{name}.parquet")


def run_info():
    snap = json.loads((SITE / "snapshot.json").read_text())
    run = load("pipeline_runs").iloc[-1]
    return {"export": snap["export"], "run_id": run.run_id, "started_utc": str(run.started_utc), "checks": int(run.checks),
            "passed": int(run.passed), "warnings": int(run.warnings), "failed": int(run.failed), "tables": len(tables())}
