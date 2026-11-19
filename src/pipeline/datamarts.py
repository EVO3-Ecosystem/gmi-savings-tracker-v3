"""Full-fidelity, fiscal-year-scoped access to the Maryland portal feeds.

The existing analytical marts still read their original inputs. These views and the local
Parquet bundle retain every source row and field in the requested window, independently
of the dashboard's filters and aggregation rules.
"""
import argparse
import csv
from pathlib import Path
from tempfile import TemporaryDirectory

import duckdb

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data" / "md_transparency.duckdb"
COLUMNS = ("run_id", "dataset", "dataset_id", "fiscal_year", "status", "portal_rows", "portal_total")


def coverage(cfg, manifest):
    """One cell per requested dataset and fiscal year, with null totals for unavailable data."""
    scope = manifest.get("coverage_scope", cfg["coverage"])
    entries = {d["dataset"]: d for d in manifest["datasets"]}
    for name, spec in cfg["datasets"].items():
        entry = entries.get(name)
        totals = {t["fiscal_year"]: t for t in entry["portal_totals"]} if entry else {}
        partial = scope.get("partial_years", {}).get(name, ())
        for fy in range(scope["first_fy"], scope["last_fy"] + 1):
            t = totals.get(fy)
            if entry is None:
                status = "not_loaded"
            elif not entry["match"]:
                status = "extract_failed"
            elif t is None:
                status = "not_published"
            else:
                status = "partial" if fy in partial else "published"
            yield (manifest["run"], name, entry["id"] if entry else spec["id"], fy, status,
                   t["rows"] if t else None, t["total"] if t else None)


def write_coverage(path, cfg, manifest):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(COLUMNS)
        writer.writerows(coverage(cfg, manifest))


def build(con, cfg, manifest):
    con.execute("CREATE SCHEMA datamart")
    con.execute("""CREATE TABLE datamart.coverage (run_id VARCHAR, dataset VARCHAR, dataset_id VARCHAR,
        fiscal_year INTEGER, status VARCHAR, portal_rows BIGINT, portal_total DOUBLE,
        PRIMARY KEY (dataset, fiscal_year))""")
    con.executemany("INSERT INTO datamart.coverage VALUES (?, ?, ?, ?, ?, ?, ?)", list(coverage(cfg, manifest)))
    scope = manifest.get("coverage_scope", cfg["coverage"])
    first, last = scope["first_fy"], scope["last_fy"]
    for d in manifest["datasets"]:
        name = d["dataset"]
        if name in cfg["datasets"]:
            col = cfg["datasets"][name]["year_col"]
            con.execute(f'CREATE VIEW datamart."{name}" AS SELECT * FROM raw."{name}" WHERE CAST("{col}" AS INTEGER) BETWEEN {first:d} AND {last:d}')


def export(db, dest=None):
    """Export each verified view and its coverage matrix as one immutable local bundle."""
    with duckdb.connect(str(db), read_only=True) as con:
        runs = con.execute("SELECT DISTINCT run_id FROM datamart.coverage").fetchall()
        if len(runs) != 1:
            raise RuntimeError("Expected exactly one build in datamart.coverage")
        run_id = runs[0][0]
        dest = Path(dest) if dest else ROOT / "data" / "datamarts" / run_id
        names = con.execute("""SELECT dataset, coalesce(sum(portal_rows), 0)::BIGINT
            FROM datamart.coverage GROUP BY dataset ORDER BY dataset""").fetchall()
        bad = con.execute("SELECT count(*) FROM datamart.coverage WHERE status IN ('not_loaded', 'extract_failed')").fetchone()[0]
        if bad:
            raise RuntimeError(f"{bad} unverified dataset-years; run a new successful extract and build first")
        if dest.exists() or dest.is_symlink():
            raise FileExistsError(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix=".datamarts-", dir=dest.parent) as tmp:
            tmp = Path(tmp)
            stage = tmp / "bundle"
            stage.mkdir()
            for name, expected in names:
                ident = '"' + name.replace('"', '""') + '"'
                path = stage / f"{name}.parquet"
                con.execute(f"COPY datamart.{ident} TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(path)])
                actual = con.execute("SELECT count(*) FROM read_parquet(?)", [str(path)]).fetchone()[0]
                if actual != expected:
                    raise RuntimeError(f"{name}: exported {actual:,} rows; expected {expected:,}")
            con.execute("COPY (SELECT * FROM datamart.coverage ORDER BY dataset, fiscal_year) TO ? (FORMAT CSV, HEADER)",
                        [str(stage / "coverage.csv")])
            stage.rename(dest)
    return dest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DB, help="successful warehouse build")
    parser.add_argument("--output", type=Path, help="new directory for the local bundle (default: data/datamarts/<run_id>)")
    args = parser.parse_args()
    print(f"Datamart bundle: {export(args.db, args.output)}")


if __name__ == "__main__":
    main()
