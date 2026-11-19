"""Full-fidelity, fiscal-year-scoped access to the Maryland portal feeds.

The existing analytical marts still read their original inputs. These views and the local
Parquet bundle retain every source row and field in the requested window, independently
of the dashboard's filters and aggregation rules.
"""
import argparse
import csv
import datetime as dt
import json
from concurrent.futures import ThreadPoolExecutor
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


def fiscal_filter(spec, scope):
    """Socrata's school-board year is text; all other configured year columns are numeric."""
    col = spec["year_col"]
    start, end = int(scope["first_fy"]), int(scope["last_fy"])
    if spec.get("year_type") == "text":
        return f"{col} between '{start:04d}' and '{end:04d}'"
    return f"{col} between {start:d} and {end:d}"


def pull(dest=None, datasets=None):
    """Pull only the configured fiscal years from SODA. No analytics build or context fetch."""
    from . import extract

    cfg = extract.CFG
    selected = {n: cfg["datasets"][n] for n in (datasets or cfg["datasets"])}
    cfg = {**cfg, "datasets": selected}
    run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    dest = Path(dest) if dest else ROOT / "data" / "datamarts" / run_id
    if dest.exists() or dest.is_symlink():
        raise FileExistsError(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    extract.checked_client().close()  # establish whether to use the optional app token
    scope = cfg["coverage"]
    with TemporaryDirectory(prefix=".datamarts-", dir=dest.parent) as tmp:
        stage = Path(tmp) / "bundle"
        stage.mkdir()

        def download(item):
            name, spec = item
            # One HTTP session per worker; cap concurrency on the public API.
            with extract.client(use_token=extract.TOKEN_USED) as c:
                e = extract.fetch_dataset(c, name, spec, stage, where=fiscal_filter(spec, scope))
            if not e["match"]:
                raise RuntimeError(f"{name}: {e['error']}")
            if any(not scope["first_fy"] <= t["fiscal_year"] <= scope["last_fy"] for t in e["portal_totals"]):
                raise RuntimeError(f"{name}: the portal returned fiscal years outside the requested window")
            return e

        with ThreadPoolExecutor(max_workers=min(3, len(selected))) as pool:
            entries = list(pool.map(download, selected.items()))
        manifest = {"run": run_id, "status": "passed", "domain": cfg["domain"], "coverage_scope": scope, "datasets": entries}
        (stage / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        write_coverage(stage / "coverage.csv", cfg, manifest)
        stage.rename(dest)
    return dest


def main():
    from . import extract

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-warehouse", action="store_true", help="export an existing verified warehouse instead of calling SODA")
    parser.add_argument("--db", type=Path, default=DB, help="successful warehouse build used with --from-warehouse")
    parser.add_argument("--output", type=Path, help="new directory for the local bundle (default: data/datamarts/<run_id>)")
    parser.add_argument("--dataset", action="append", choices=extract.CFG["datasets"], help="pull one named feed; repeat for several (default: all)")
    args = parser.parse_args()
    if args.from_warehouse and args.dataset:
        parser.error("--dataset is only supported for direct pulls")
    print(f"Datamart bundle: {export(args.db, args.output) if args.from_warehouse else pull(args.output, args.dataset)}")


if __name__ == "__main__":
    main()
