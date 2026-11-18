"""docs/asset-map.csv names only tabs, tables and files that exist, and uses the four statuses."""
import csv
import re
from pathlib import Path

import pytest

from src import published as P

ROOT = Path(__file__).resolve().parents[1]
ROWS = list(csv.DictReader((ROOT / "docs" / "asset-map.csv").open(encoding="utf-8")))
TABS = set(re.findall(r'role="tab" id="t-(\w+)"', (ROOT / "legacy" / "gst" / "page" / "index.html").read_text()))
COLUMNS = ["row_id", "source", "source_phase", "title", "v3_status", "v3_tab", "v3_tables", "v3_code", "roadmap_ref", "portfolio_asset", "action",
           "verified", "note"]


def test_columns_and_unique_ids():
    assert list(ROWS[0].keys()) == COLUMNS
    ids = [r["row_id"] for r in ROWS]
    assert len(ids) == len(set(ids)) and len([i for i in ids if i.startswith("SL")]) == 16


def test_statuses_sources_and_verification_flags():
    assert {r["v3_status"] for r in ROWS} <= {"done", "built", "partial", "not_started"}
    assert {r["source"] for r in ROWS} == {"spend-lens", "v3-only"}
    assert {r["verified"] for r in ROWS} <= {"yes", "unverified"}


def test_every_tab_exists_on_the_dashboard():
    assert len(TABS) == 11
    assert {r["v3_tab"] for r in ROWS if r["v3_tab"]} <= TABS


@pytest.mark.parametrize("row", ROWS, ids=lambda r: r["row_id"])
def test_every_table_and_file_exists(row):
    for t in filter(None, row["v3_tables"].split(";")):
        assert P.has(t), f"{row['row_id']}: published table {t} not found"
    for f in filter(None, row["v3_code"].split(";")):
        assert (ROOT / f).exists(), f"{row['row_id']}: {f} not found"


def test_rows_with_work_left_say_what_it_is():
    for r in ROWS:
        if r["v3_status"] in ("not_started", "partial", "built"):
            assert r["action"].strip(), r["row_id"]
