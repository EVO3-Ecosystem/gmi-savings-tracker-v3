"""The executive walkthrough table: every number in its text comes from the metric registry or the published tables, never typed."""
import re
from pathlib import Path

import pandas as pd
import pytest

from src.models import exec_walkthrough as ew

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "site_data"
pytestmark = pytest.mark.skipif(not (SRC / "run_checks.csv").exists(), reason="no site_data/ snapshot")


@pytest.fixture(scope="module")
def table():
    return ew.build(SRC)


@pytest.fixture(scope="module")
def values():
    return ew.facts(SRC)


def grade(text):
    """Flesch-Kincaid grade level: a rough ceiling check on plain language."""
    sents = max(1, len(re.findall(r"[.!?]+(?:\s|$)", text)))
    words = re.findall(r"[A-Za-z']+", text)
    syl = sum(max(1, len(re.findall(r"[aeiouy]+", w.lower().rstrip("e")))) for w in words)
    return 0.39 * len(words) / sents + 11.8 * syl / max(1, len(words)) - 15.59


def test_shape_and_columns(table):
    assert list(table.columns) == ew.COLUMNS
    assert (table.kind == "step").sum() == 8 and (table.kind == "ask").sum() == 3
    assert list(table[table.kind == "step"].step) == list(range(1, 9))


def test_every_step_has_a_finding_source_caveat_and_a_real_tab(table):
    for _, r in table[table.kind == "step"].iterrows():
        assert r.finding and r.evidence and r.caveat and r.tables, r.title
        assert r.tab_link in ew.TABS and r.tab_label == ew.TABS[r.tab_link]
        assert len(r.finding.split()) <= 60, r.title


def test_cited_tables_are_published(table):
    for t in {x for row in table.tables for x in str(row).split(";") if x}:
        assert (SRC / f"{t}.csv").exists(), t


def test_numbers_come_from_the_registry_and_tables(table, values):
    f, r = values
    text = " ".join(table[table.kind == "step"].finding)
    must = [ew.usd(r["reported_saved_fy2026_usd"]), ew.usd(r["reported_actions_june_2026_usd"]), ew.usd(r["path_total_usd"]), ew.usd(r["path_low_usd"]),
            ew.usd(r["path_high_usd"]), ew.usd(r["opportunity_high_usd"]), ew.usd(r["source_issue_amount_usd"]), ew.usd(f["carried"]),
            f"{r['checks_passed']} of {r['checks_total']}", str(r["opportunity_findings"]), f"{f['areas_fell']} of {f['areas_checked']}",
            f"{f['cal_hits']} of {f['cal_n']}", f"{f['raw_hits']} of {f['raw_n']}", f"{f['site_equal']} of {f['site_n']}"]
    for token in must:
        assert token in text, token
    allowed = {ew.usd(r[k]) for k in r if k.endswith("_usd") and r[k]} | {ew.usd(f["carried"]), ew.usd(f["largest_reported"])}
    for token in re.findall(r"\$[\d.]+[KMB]", " ".join(table.finding)):
        assert token in allowed, f"{token} is not computed from the registry or a table"


def test_asks_do_not_invent_owners(table):
    assert set(table[table.kind == "ask"].owner) == {ew.OWNER}
    assert set(table[table.kind == "step"].owner.fillna("")) == {""}


def test_plain_language(table):
    for _, r in table.iterrows():
        assert grade(r.finding) <= 11, (r.title, round(grade(r.finding), 1))


def test_as_of_and_version_are_set(table):
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", table.as_of.iloc[0]) and re.fullmatch(r"\d+\.\d+\.\d+", table.version.iloc[0])


def test_deterministic(table):
    pd.testing.assert_frame_equal(table, ew.build(SRC))
