"""The metric registry (config/metrics.yml): well formed, evaluates on the published snapshot, and agrees with the README facts."""
import copy
import math
from pathlib import Path

import pytest
import yaml

from src.models import doc_facts, metrics
from src.models.doc_facts import mm
from src.mcp.store import Store

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def con():
    return Store(export_dir=ROOT / "site_data", prefer="export").con


@pytest.fixture(scope="module")
def reg():
    return metrics.load()


def test_registry_is_well_formed(reg):
    assert len(reg) >= 15
    ids = [m["id"] for m in reg]
    assert len(ids) == len(set(ids))
    for m in reg:
        assert m["unit"] in metrics.UNITS and m["definition"].strip().endswith(".") and m["shown_in"]


def test_every_metric_reads_only_marts_it_declares(con, reg):
    have = {r[0] for r in con.execute("select table_name from information_schema.tables where table_schema = 'mart'").fetchall()}
    for m in reg:
        assert set(m["tables"]) <= have, (m["id"], set(m["tables"]) - have)
        assert all(f"mart.{t}" in m["sql"] for t in m["tables"]), f"{m['id']}: declared tables not used in the SQL"


def test_every_metric_evaluates_to_a_finite_number(con, reg):
    for r in metrics.evaluate(con, reg):
        assert r["value"] is not None and math.isfinite(r["value"]), r["id"]
        if r["unit"] == "ratio":
            assert 0 <= r["value"] <= 5, r["id"]


def test_readme_facts_are_the_registry_values(con, reg):
    text = doc_facts.readme_facts(con)
    v = lambda mid: metrics.value(con, mid, reg)  # noqa: E731
    for needle in (mm(v("reported_saved_fy2026_usd")), f"{v('opportunity_findings')} findings", mm(v("opportunity_high_usd")),
                   mm(v("opportunity_likely_usd")), f"{int(v('possible_duplicate_groups'))} possible duplicate payment groups",
                   mm(v("possible_duplicate_review_usd")), mm(v("source_issue_amount_usd")), mm(v("path_total_usd")),
                   mm(v("path_low_usd")), mm(v("path_high_usd")), f"{v('gmi_reported_items')} items"):
        assert needle in text, needle


def test_overview_numbers_match_the_dashboard_text(con, reg):
    """The Overview tab's finding: controllable purchases $4.8B, up 17.7% from the FY2025 actual, 7.4% of $64.8B."""
    v = lambda mid: metrics.value(con, mid, reg)  # noqa: E731
    assert mm(v("controllable_fy2026_usd")) == "$4.8B" and f"{v('controllable_yoy_ratio'):.1%}" == "17.7%"
    assert f"{v('controllable_share_of_operating_ratio'):.1%}" == "7.4%" and mm(v("operating_spending_fy2026_usd")) == "$64.8B"


def test_checks_passed_never_exceeds_total(con, reg):
    assert metrics.value(con, "checks_passed", reg) <= metrics.value(con, "checks_total", reg)


@pytest.mark.parametrize("bad_sql", ["DELETE FROM mart.d_opps", "SELECT 1; SELECT 2", "SELECT * FROM read_csv('/etc/passwd')"])
def test_registry_rejects_unsafe_sql(tmp_path, bad_sql):
    data = yaml.safe_load((ROOT / "config" / "metrics.yml").read_text())
    data["metrics"] = [copy.deepcopy(data["metrics"][0])]
    data["metrics"][0]["sql"] = bad_sql
    p = tmp_path / "m.yml"
    p.write_text(yaml.safe_dump(data))
    with pytest.raises(metrics.RegistryError):
        metrics.load(p)


def test_registry_rejects_duplicate_ids_and_missing_fields(tmp_path):
    data = yaml.safe_load((ROOT / "config" / "metrics.yml").read_text())
    dup = copy.deepcopy(data)
    dup["metrics"] = [data["metrics"][0], copy.deepcopy(data["metrics"][0])]
    (tmp_path / "dup.yml").write_text(yaml.safe_dump(dup))
    with pytest.raises(metrics.RegistryError):
        metrics.load(tmp_path / "dup.yml")
    bad = copy.deepcopy(data)
    del bad["metrics"][0]["owner"]
    (tmp_path / "bad.yml").write_text(yaml.safe_dump(bad))
    with pytest.raises(metrics.RegistryError):
        metrics.load(tmp_path / "bad.yml")
