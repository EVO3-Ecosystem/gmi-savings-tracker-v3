"""Offline extract tests against the recorded SODA portal (tests/fixtures/soda, wired up in conftest.py).

These cover what tests/test_extract.py cannot in CI (it needs a real `make extract` run): metadata
and paging behavior, the retry/backoff wrapper, the freshness-reuse path, and the self-healing
re-download — all without any network access.
"""
import json
import re
import socket
import time

import pandas as pd
import pyarrow.parquet as pq
import pytest
import requests

from src.pipeline import extract

IDS = {name: spec["id"] for name, spec in extract.CFG["datasets"].items()}


def test_portal_facts_come_from_the_recordings(soda_portal):
    c = extract.client()
    for name, fid in IDS.items():
        spec = extract.CFG["datasets"][name]
        updated, n, totals, pname = extract.portal_facts(c, fid, spec)
        rows = soda_portal.rows(fid)
        assert updated == soda_portal.meta(fid)["rowsUpdatedAt"]
        assert pname == spec["portal_name"]
        assert n == len(rows)
        assert sum(t["rows"] for t in totals) == n
        assert abs(sum(t["total"] for t in totals) - sum(float(r.get(spec["sum_col"]) or 0) for r in rows)) < 0.01


def test_download_paginates_until_a_short_page(soda_portal, tmp_path, monkeypatch):
    monkeypatch.setitem(extract.CFG, "page_size", 2)  # 6 budget rows -> pages of 2, 2, 2, then a short page
    dest = tmp_path / "budget.parquet"
    n = extract.download(extract.client(), IDS["budget"], dest)
    assert n == len(soda_portal.rows(IDS["budget"])) == pq.ParquetFile(dest).metadata.num_rows
    pages = [c for c in soda_portal.calls if "/resource/" in c and "$offset=" in c]
    assert [int(re.search(r"\$offset=(\d+)", c).group(1)) for c in pages] == [0, 2, 4, 6]


def test_call_retries_a_dropped_connection_then_succeeds(soda_portal):
    soda_portal.fail_next("/api/views/", times=1)
    meta = extract.call(lambda: extract.client().get_metadata(IDS["budget"]), "budget metadata")
    assert meta["rowsUpdatedAt"] == soda_portal.meta(IDS["budget"])["rowsUpdatedAt"]
    assert soda_portal.count_calls("/api/views/") == 2  # one failure, one success


def test_call_gives_up_after_the_configured_tries(soda_portal):
    soda_portal.fail_next("/api/views/", times=99)
    with pytest.raises(RuntimeError, match="gave up on budget metadata after 3 tries"):
        extract.call(lambda: extract.client().get_metadata(IDS["budget"]), "budget metadata", tries=3)
    assert soda_portal.count_calls("/api/views/") == 3


def _http_error(status, body):
    r = requests.Response()
    r.status_code, r._content = status, body.encode()
    return requests.exceptions.HTTPError(f"{status} Client Error", response=r)


def test_a_rejected_app_token_stops_at_once_and_says_how_to_fix_it(monkeypatch):
    slept, calls = [], []
    monkeypatch.setattr(extract.time, "sleep", slept.append)

    def fn():
        calls.append(1)
        raise _http_error(403, "Invalid app_token specified")
    with pytest.raises(RuntimeError, match=r"rejected the Socrata app token on budget metadata.*MD_SODA_APP_TOKEN secret"):
        extract.call(fn, "budget metadata", tries=6)
    assert len(calls) == 1 and slept == []  # one attempt, no waiting


def test_other_http_errors_are_still_retried(monkeypatch):
    slept, calls = [], []
    monkeypatch.setattr(extract.time, "sleep", slept.append)

    def fn():
        calls.append(1)
        raise _http_error(429, "Too Many Requests")
    with pytest.raises(RuntimeError, match="gave up on budget metadata after 3 tries"):
        extract.call(fn, "budget metadata", tries=3)
    assert len(calls) == 3 and len(slept) == 2  # throttling is retried with backoff


def test_a_403_that_is_not_about_the_token_is_not_called_a_token_problem():
    assert not extract.token_rejected(_http_error(403, "Forbidden: dataset is private"))
    assert extract.token_rejected(_http_error(401, "Invalid app_token specified"))


class _FakeSocrata:
    """Stands in for sodapy.Socrata: a token spelled 'bad' is refused with 403 invalid app_token, as the portal does."""
    instances = []

    def __init__(self, domain, token, timeout=None):
        self.token, self.metadata_calls = token, 0
        _FakeSocrata.instances.append(self)

    def get_metadata(self, fid):
        self.metadata_calls += 1
        if self.token == "bad":
            raise _http_error(403, "Invalid app_token specified")
        if self.token == "flaky":
            raise _http_error(500, "Server Error")
        return {"rowsUpdatedAt": 1}


@pytest.fixture
def fake_portal(monkeypatch):
    _FakeSocrata.instances = []
    monkeypatch.setattr(extract, "Socrata", _FakeSocrata)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    return _FakeSocrata


def test_a_rejected_token_is_dropped_and_the_run_continues_without_it(fake_portal, monkeypatch, capsys):
    monkeypatch.setenv("MD_SODA_APP_TOKEN", "bad")
    c = extract.checked_client()
    assert c.token is None and extract.TOKEN_USED is False
    assert "continues without it" in capsys.readouterr().out
    assert [i.token for i in fake_portal.instances] == ["bad", None]  # tried once with the token, then a tokenless client


def test_a_working_token_is_kept_and_tested_once(fake_portal, monkeypatch):
    monkeypatch.setenv("MD_SODA_APP_TOKEN", "good")
    c = extract.checked_client()
    assert c.token == "good" and extract.TOKEN_USED is True and c.metadata_calls == 1


def test_no_token_means_no_preflight_and_a_tokenless_client(fake_portal, monkeypatch):
    monkeypatch.delenv("MD_SODA_APP_TOKEN", raising=False)
    c = extract.checked_client()
    assert c.token is None and extract.TOKEN_USED is False and c.metadata_calls == 0


def test_other_preflight_trouble_keeps_the_token_for_the_retrying_calls(fake_portal, monkeypatch):
    monkeypatch.setenv("MD_SODA_APP_TOKEN", "flaky")
    c = extract.checked_client()
    assert c.token == "flaky" and extract.TOKEN_USED is True  # a 500 is not a token problem


def test_on_github_the_fallback_raises_a_warning_annotation(fake_portal, monkeypatch, capsys):
    monkeypatch.setenv("MD_SODA_APP_TOKEN", "bad")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    extract.checked_client()
    assert "::warning title=Socrata app token rejected::" in capsys.readouterr().out


def test_extract_run_end_to_end_without_network(soda_portal, extract_dirs, monkeypatch):
    def no_network(*a, **k):
        raise AssertionError("extract touched the network outside the recorded portal")
    monkeypatch.setattr(socket, "create_connection", no_network)  # belt and braces: prove nothing escapes the mock
    assert extract.run() == 0
    run_dir = next((extract_dirs / "raw").iterdir())
    man = json.loads((run_dir / "manifest.json").read_text())
    assert man["status"] == "passed" and len(man["datasets"]) == len(IDS)
    for e in man["datasets"]:
        assert e["match"] and e["source"] == "downloaded" and e["heal_attempts"] == 0
        assert pq.ParquetFile(run_dir / f"{e['dataset']}.parquet").metadata.num_rows == e["portal_count"]
        assert sum(t["rows"] for t in e["portal_totals"]) == e["portal_count"]
    hist = pd.read_csv(extract_dirs / "runs.csv")
    assert len(hist) == 1 and hist.status.iloc[0] == "passed" and hist.downloaded.iloc[0] == len(IDS)


def test_second_run_reuses_unchanged_portal_data(soda_portal, extract_dirs):
    assert extract.run() == 0
    time.sleep(1.05)  # run ids have one-second resolution
    assert extract.run() == 0
    run_dir = sorted((extract_dirs / "raw").iterdir())[-1]
    man = json.loads((run_dir / "manifest.json").read_text())
    assert man["status"] == "passed"
    assert all(e["source"].startswith("reused") for e in man["datasets"])
    hist = pd.read_csv(extract_dirs / "runs.csv")
    assert len(hist) == 2 and hist.reused.iloc[-1] == len(IDS) and hist.downloaded.iloc[-1] == 0


def test_fault_hook_drives_self_healing_redownload(soda_portal, extract_dirs, monkeypatch):
    monkeypatch.setattr(extract, "FAULT", "fte")  # drops half the fte rows after download; the run must repair itself
    assert extract.run() == 0
    run_dir = next((extract_dirs / "raw").iterdir())
    man = json.loads((run_dir / "manifest.json").read_text())
    fte = next(e for e in man["datasets"] if e["dataset"] == "fte")
    assert fte["heal_attempts"] == 1 and fte["source"] == "re-downloaded (1)" and fte["match"]
    assert pq.ParquetFile(run_dir / "fte.parquet").metadata.num_rows == fte["portal_count"]


def test_equal_grand_counts_do_not_hide_wrong_years_or_totals(soda_portal, tmp_path):
    spec = extract.CFG["datasets"]["school_spending"]
    fid = spec["id"]
    _, n, totals, _ = extract.portal_facts(extract.client(), fid, spec)
    path = tmp_path / "school.parquet"
    rows = pd.DataFrame(soda_portal.rows(fid))
    rows.loc[0, "amount"] = "100.00"
    rows.to_parquet(path)
    count, error = extract.validate_download(path, spec, n, totals)
    assert count == n and "FY2010" in error
    rows.loc[0, "fiscal_year"] = "2009"
    rows.to_parquet(path)
    assert extract.validate_download(path, spec, n, totals)[1] == "fiscal years in Parquet differ from the portal"


def test_mid_run_portal_revision_triggers_redownload(soda_portal, extract_dirs, monkeypatch):
    fid = IDS["budget"]
    original = soda_portal.meta
    hits = 0

    def changed(dataset):
        nonlocal hits
        data = original(dataset)
        if dataset == fid:
            hits += 1
            if hits >= 2:
                data["rowsUpdatedAt"] += 1
        return data

    monkeypatch.delenv("MD_SODA_APP_TOKEN", raising=False)
    monkeypatch.setattr(soda_portal, "meta", changed)
    assert extract.run() == 0
    raw, = (extract_dirs / "raw").iterdir()
    budget = json.loads((raw / "manifest.json").read_text())["datasets"][0]
    assert budget["source"] == "re-downloaded (1)"
    assert budget["rowsUpdatedAt"] == original(fid)["rowsUpdatedAt"] + 1
