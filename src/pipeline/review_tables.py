"""Dump the model-evaluation tables of the last build as CSV and print a short summary, for review after a run.

    python -m src.pipeline.review_tables [OUT_DIR]     # default data/review

Reads the built database, or the failed one when the last build stopped on a check, so the evidence is available either
way. Used by the Actions run: the CSVs are uploaded as an artifact and the summary goes to the job summary.
"""
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
TABLES = ("d_range_coverage", "f_forecast", "d_forecast_calibration", "d_challenger_backtest", "d_challenger_total", "d_revenue_model",
          "d_detector_backtest", "d_detector_outcomes", "d_detector_lift", "d_program_screen")


def main(out=None):
    out = Path(out or DATA / "review")
    out.mkdir(parents=True, exist_ok=True)
    good, failed = DATA / "md_transparency.duckdb", DATA / "md_transparency.failed.duckdb"
    db = failed if failed.exists() and (not good.exists() or failed.stat().st_mtime > good.stat().st_mtime) else good
    if not db.exists():
        print("no database to review")
        return 1
    con = duckdb.connect(str(db), read_only=True)
    have = {r[0] for r in con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'mart'").fetchall()}
    print(f"## Model evaluation tables ({db.name})\n")
    for t in TABLES:
        if t not in have:
            print(f"- `{t}`: not built")
            continue
        con.execute(f"COPY (SELECT * FROM mart.{t}) TO '{out / (t + '.csv')}' (HEADER)")
        print(f"- `{t}`: {con.execute(f'SELECT count(*) FROM mart.{t}').fetchone()[0]} rows")
    if "d_range_coverage" in have:
        print("\n### Range coverage (pooled rows)\n\n```")
        print(con.execute("""SELECT source, area, horizon, scope, calibrated, n, hits, coverage, cov_lo, cov_hi, factor, adopted
                             FROM mart.d_range_coverage WHERE area IN ('All areas', 'All series', 'General Fund revenue')
                             ORDER BY source, scope, calibrated, horizon""").df().to_string(index=False))
        print("```")
    if "f_forecast" in have:
        print("\n### Range source by area, first forecast year\n\n```")
        print(con.execute("""SELECT area, fiscal_year, range_source FROM mart.f_forecast WHERE kind = 'Forecast'
                             QUALIFY fiscal_year = min(fiscal_year) OVER () ORDER BY area""").df().to_string(index=False))
        print("```")
    if "d_detector_lift" in have:
        print("\n### Detector lift (flagged against not flagged, pooled over as-of years)\n\n```")
        print(con.execute("SELECT * FROM mart.d_detector_lift ORDER BY detector, outcome, horizon").df().round(3).to_string(index=False))
        print("```")
    chk = con.execute("SELECT * FROM ops.check_result").df()
    col = "status" if "status" in chk.columns else "result"  # the database names it result, the published file status
    bad = chk[chk[col] != "pass"]
    print("\n### Checks that did not pass\n\n```")
    print(bad.to_string(index=False) if len(bad) else "none")
    print("```")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:2]))
