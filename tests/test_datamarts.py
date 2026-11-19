"""Test the scoped warehouse views and the exported bundle against the offline portal."""
import csv
import json

import duckdb
import pytest

from src.pipeline import datamarts, extract


def test_coverage_distinguishes_missing_failed_partial_and_zero():
    cfg = {"coverage": {"first_fy": 2025, "last_fy": 2027, "partial_years": {"budget": [2027]}},
           "datasets": {"budget": {"id": "a"}, "fund": {"id": "b"}, "fte": {"id": "c"}}}
    totals = [{"fiscal_year": 2025, "rows": 1, "total": 0}, {"fiscal_year": 2027, "rows": 3, "total": 40}]
    man = {"run": "r", "datasets": [{"dataset": "budget", "id": "a", "match": True, "portal_totals": totals},
                                     {"dataset": "fund", "id": "b", "match": False, "portal_totals": totals}]}
    rows = list(datamarts.coverage(cfg, man))
    assert len(rows) == 9
    assert [r[4:] for r in rows[:3]] == [("published", 1, 0), ("not_published", None, None), ("partial", 3, 40)]
    assert {r[4] for r in rows[3:6]} == {"extract_failed"}
    assert {r[4] for r in rows[6:]} == {"not_loaded"}


def test_offline_extract_to_scoped_bundle(soda_portal, extract_dirs, tmp_path):
    assert extract.run() == 0
    raw, = (extract_dirs / "raw").iterdir()
    man = json.loads((raw / "manifest.json").read_text())
    db = tmp_path / "test.duckdb"
    cfg = extract.CFG
    with duckdb.connect(str(db)) as con:
        con.execute("CREATE SCHEMA raw")
        for name in cfg["datasets"]:
            con.execute(f"CREATE TABLE raw.{name} AS SELECT * FROM read_parquet(?)", [str(raw / f"{name}.parquet")])
        con.execute("INSERT INTO raw.payments BY NAME SELECT * REPLACE ('2008' AS fiscal_year) FROM raw.payments LIMIT 1")
        datamarts.build(con, cfg, man)
        assert con.execute("SELECT count(*) FROM raw.payments WHERE fiscal_year = '2008'").fetchone()[0] > 0
        assert con.execute("SELECT count(*) FROM datamart.payments WHERE fiscal_year = '2008'").fetchone()[0] == 0
        assert con.execute("SELECT status FROM datamart.coverage WHERE dataset='school_spending' AND fiscal_year=2010").fetchone() == ("partial",)
    out = datamarts.export(db, tmp_path / "bundle")
    assert {p.stem for p in out.glob("*.parquet")} == set(cfg["datasets"])
    with (out / "coverage.csv").open(newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 19 * len(cfg["datasets"])
    assert {r["dataset_id"] for r in rows} == {d["id"] for d in cfg["datasets"].values()}
    with pytest.raises(FileExistsError):
        datamarts.export(db, out)
