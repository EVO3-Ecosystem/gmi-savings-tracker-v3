"""Phase 1 — Extract: Maryland open data portal (SODA) -> data/raw/<run_id>/*.parquet + manifest.json

For each dataset in config/datasets.yaml:
  1. Read the portal's metadata (rowsUpdatedAt) and its own row count and per-year totals.
  2. Freshness check: if rowsUpdatedAt is unchanged since the last good run, reuse that run's Parquet file
     (hard link, or copy) instead of downloading again. --force always downloads.
  3. Otherwise download in 20,000-row pages ordered by :id, retrying each page with exponential backoff.
  4. Verify row counts and totals for every fiscal year, and verify that the portal did not change
     during paging. Re-download up to heal_attempts times; if still inconsistent, fail the run.
  5. Write manifest.json: per dataset rows, portal count, match, rowsUpdatedAt, source (downloaded/reused),
     seconds, heal attempts, and the portal's per-year totals (saved for the Phase 2 totals check).

Every run is appended to data/runs.csv (the feedback loop), including failed ones. A run that fails a check
exits non-zero and is not marked good, so the next run cannot reuse its files.

Usage:  python -m src.pipeline.extract [--force] [--gate]
  --gate   Phase 1 gate: the last two runs both matched portal row counts for every dataset.
"""
import argparse
import datetime as dt
import json
import os
import shutil
import sys
import time
from pathlib import Path

import duckdb
import pandas as pd
import requests
import yaml
from sodapy import Socrata

from . import datamarts

ROOT = Path(__file__).resolve().parents[2]
CFG = yaml.safe_load((ROOT / "config" / "datasets.yaml").read_text())
DATA = ROOT / "data"
RAW = DATA / "raw"
RUNS = DATA / "runs.csv"
FAULT = os.environ.get("EXTRACT_FAULT")  # test hook, e.g. EXTRACT_FAULT=fte


def log(msg):
    print(f"{dt.datetime.now(dt.timezone.utc):%H:%M:%S} {msg}", flush=True)


TOKEN_USED = bool(os.environ.get("MD_SODA_APP_TOKEN"))  # whether this run sends a token; checked_client() sets it for the run


def client(use_token=True):
    token = os.environ.get("MD_SODA_APP_TOKEN") if use_token else None
    return Socrata(CFG["domain"], token or None, timeout=300)


def token_rejected(e):
    """True when the portal refused the app token itself (HTTP 401 or 403 naming app_token): retrying cannot fix that."""
    r = getattr(e, "response", None)
    return r is not None and r.status_code in (401, 403) and "app_token" in (r.text or "").lower()


def call(fn, what, tries=None):
    """Run one SODA call with exponential backoff (self-healing for dropped connections and throttling).
    A rejected app token is not retried: it stops at once and says how to fix it."""
    tries = tries or CFG["retries"]
    for i in range(tries):
        try:
            return fn()
        except requests.exceptions.HTTPError as e:
            if token_rejected(e):
                raise RuntimeError(
                    f"The portal rejected the Socrata app token on {what} (HTTP {e.response.status_code}: {e.response.text.strip()[:120]}). Not retrying. "
                    "Create an app token (the App Token, not the Secret Token; no spaces or newline) in your Socrata developer settings "
                    "(https://dev.socrata.com/docs/app-tokens) and update the MD_SODA_APP_TOKEN secret.") from e
            if i == tries - 1:
                raise RuntimeError(f"gave up on {what} after {tries} tries: {type(e).__name__}: {e}") from e
            wait = CFG["backoff_seconds"] * 2 ** i
            log(f"  retry {i + 1} {what}: {type(e).__name__}; waiting {wait}s")
            time.sleep(wait)
        except (requests.exceptions.RequestException, ValueError) as e:
            if i == tries - 1:
                raise RuntimeError(f"gave up on {what} after {tries} tries: {type(e).__name__}: {e}") from e
            wait = CFG["backoff_seconds"] * 2 ** i
            log(f"  retry {i + 1} {what}: {type(e).__name__}; waiting {wait}s")
            time.sleep(wait)


def checked_client():
    """The portal client for a run. The token is optional: the datasets are public and SODA 2.1 serves them without one.
    If a token is set, test it once on a cheap metadata call. A portal that rejects it also refuses the requests it
    would have served tokenless, so the run drops the token and continues with the public limits, with a loud warning."""
    global TOKEN_USED
    c = client()
    TOKEN_USED = bool(os.environ.get("MD_SODA_APP_TOKEN"))
    if not TOKEN_USED:
        return c
    try:
        c.get_metadata(next(iter(CFG["datasets"].values()))["id"])  # not via call(): a rejection must not be retried
    except requests.exceptions.RequestException as e:
        if not token_rejected(e):
            return c  # some other trouble: the retrying calls that follow deal with it
        msg = ("The portal rejected MD_SODA_APP_TOKEN, so this run continues without it at the public (throttled) limits. "
               "Replace the secret to restore the higher limits; nothing else is needed.")
        log("WARNING: " + msg)
        if os.environ.get("GITHUB_ACTIONS"):
            print(f"::warning title=Socrata app token rejected::{msg}", flush=True)
        TOKEN_USED = False
        return client(use_token=False)
    return c


def portal_facts(c, fid, spec):
    meta = call(lambda: c.get_metadata(fid), f"{fid} metadata")
    n = int(call(lambda: c.get(fid, select="count(*) as n"), f"{fid} count")[0]["n"])
    y, s = spec["year_col"], spec["sum_col"]
    tot = call(lambda: c.get(fid, select=f"{y} as fiscal_year, sum({s}) as total, count(*) as rows", group=y, order=y, limit=1000), f"{fid} totals")
    totals = [{"fiscal_year": int(float(r["fiscal_year"])), "total": float(r.get("total") or 0), "rows": int(r["rows"])} for r in tot if r.get("fiscal_year") is not None]
    return meta.get("rowsUpdatedAt"), n, totals, meta.get("name")


def download(c, fid, path):
    rows, off, size = [], 0, CFG["page_size"]
    while True:
        page = call(lambda o=off: c.get(fid, order=":id", limit=size, offset=o), f"{fid} offset {off}")
        rows += page
        if len(page) < size:
            break
        off += size
    pd.DataFrame.from_records(rows).to_parquet(path, index=False)
    return len(rows)


def parquet_rows(path):
    import pyarrow.parquet as pq
    return pq.ParquetFile(path).metadata.num_rows


def validate_download(path, spec, expect, totals):
    """Check every year, not just the grand count (different bad pages can cancel each other out)."""
    try:
        n = parquet_rows(path)
    except (ValueError, OSError) as err:
        return 0, f"unreadable Parquet: {err}"
    if n != expect or n != sum(t["rows"] for t in totals):
        return n, f"{n:,} rows vs {expect:,} on the portal; portal year groups sum to {sum(t['rows'] for t in totals):,}"
    if not n:
        return n, "portal returned an empty datamart"
    y, s = spec["year_col"], spec["sum_col"]
    with duckdb.connect() as con:
        try:
            rows = con.execute(f"""SELECT CAST("{y}" AS INTEGER), count(*),
                sum(CAST("{s}" AS DECIMAL(38, 9))),
                count(*) FILTER (WHERE "{y}" IS NULL OR "{s}" IS NULL)
                FROM read_parquet(?) GROUP BY 1""", [str(path)]).fetchall()
        except duckdb.Error as err:
            return n, f"unexpected year/measure schema or values: {err}"
    actual = {fy: (count, total, nulls) for fy, count, total, nulls in rows}
    if actual.keys() != {t["fiscal_year"] for t in totals}:
        return n, "fiscal years in Parquet differ from the portal"
    for t in totals:
        fy = t["fiscal_year"]
        count, total, nulls = actual[fy]
        if nulls or count != t["rows"] or total is None or abs(float(total) - t["total"]) >= 0.01:
            return n, f"FY{fy}: {count:,}/{t['rows']:,} rows, {total}/{t['total']} total, {nulls} null rows"
    return n, None


def last_good_run():
    if not RUNS.exists():
        return None
    r = pd.read_csv(RUNS)
    r = r[r.status == "passed"]
    return None if r.empty else str(r.run_id.iloc[-1])


def reuse(prev_dir, name, dest):
    src = prev_dir / f"{name}.parquet"
    try:
        os.link(src, dest)
    except OSError:
        shutil.copy2(src, dest)


def run(force=False):
    run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = RAW / run_id
    out.mkdir(parents=True)
    c = checked_client()
    prev_id = last_good_run()
    prev = json.loads((RAW / prev_id / "manifest.json").read_text()) if prev_id else {"datasets": []}
    prev_by = {d["dataset"]: d for d in prev["datasets"]}
    entries, t_run = [], time.time()
    for name, spec in CFG["datasets"].items():
        fid, t = spec["id"], time.time()
        updated, expect, totals, pname = portal_facts(c, fid, spec)
        dest = out / f"{name}.parquet"
        p = prev_by.get(name)
        fresh = (not force) and p and updated is not None and p.get("id") == fid and p.get("rowsUpdatedAt") == updated and p.get("match") and (RAW / prev_id / f"{name}.parquet").exists()
        heals = 0
        while True:
            if fresh and not heals:
                reuse(RAW / prev_id, name, dest)
                source = f"reused from {prev_id} (portal unchanged)"
            else:
                download(c, fid, dest)
                source = f"re-downloaded ({heals})" if heals else "downloaded"
            if FAULT == name and not heals:  # unlink first: a reused Parquet file may be hard-linked
                truncated = pd.read_parquet(dest).iloc[: expect // 2]
                dest.unlink()
                truncated.to_parquet(dest, index=False)
                log(f"  test fault: dropped half of {name}")
            n, error = validate_download(dest, spec, expect, totals)
            end_revision = call(lambda fid=fid: c.get_metadata(fid), f"{fid} post-download metadata").get("rowsUpdatedAt")
            if updated != end_revision:
                error = "portal revision changed during extraction"
            if error is None or heals >= CFG["heal_attempts"]:
                break
            heals += 1
            log(f"  {name}: {error}; re-downloading (attempt {heals})")
            dest.unlink(missing_ok=True)
            updated, expect, totals, pname = portal_facts(c, fid, spec)
        e = {"dataset": name, "id": fid, "rows": n, "portal_count": expect, "match": error is None, "rowsUpdatedAt": updated, "portal_name": pname,
             "rowsUpdatedAt_utc": dt.datetime.fromtimestamp(updated, dt.timezone.utc).isoformat() if updated else None,
             "source": source, "heal_attempts": heals, "secs": round(time.time() - t, 1), "portal_totals": totals, "error": error}
        entries.append(e)
        log(f"{name:9s} {fid}  {n:>8,} rows  portal {expect:>8,}  {'OK' if e['match'] else 'MISMATCH'}  {source}  {e['secs']}s")
    from . import enrich  # context sources for the six recommendations; warnings never block the core extract
    extra = enrich.run_all(out, (RAW / prev_id) if prev_id else None, log)
    ok = all(e["match"] for e in entries)
    manifest = {"run": run_id, "status": "passed" if ok else "failed", "forced": force, "seconds": round(time.time() - t_run, 1),
                "coverage_scope": CFG["coverage"],
                "domain": CFG["domain"], "page_size": CFG["page_size"], "app_token": TOKEN_USED, "datasets": entries, "enrichment": extra}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1))
    datamarts.write_coverage(out / "coverage.csv", CFG, manifest)
    row = {"run_id": run_id, "status": manifest["status"], "forced": force, "seconds": manifest["seconds"],
           "rows": sum(e["rows"] for e in entries), "downloaded": sum(not e["source"].startswith("reused") for e in entries),
           "reused": sum(e["source"].startswith("reused") for e in entries), "heals": sum(e["heal_attempts"] for e in entries),
           "mismatches": sum(not e["match"] for e in entries), "enrichment_warnings": sum(x["status"] != "pass" for x in extra)}
    hist = pd.read_csv(RUNS) if RUNS.exists() else pd.DataFrame()
    pd.concat([hist, pd.DataFrame([row])], ignore_index=True).to_csv(RUNS, index=False)
    log(f"run {run_id} {manifest['status']} in {manifest['seconds']}s -> {out}")
    return 0 if ok else 1


def gate():
    """Phase 1 gate: the last two runs both matched portal row counts for every dataset."""
    r = pd.read_csv(RUNS) if RUNS.exists() else pd.DataFrame()
    last = r.tail(2)
    ok = len(last) == 2 and (last.status == "passed").all() and (last.mismatches == 0).all()
    for _, x in last.iterrows():
        m = json.loads((RAW / x.run_id / "manifest.json").read_text())
        print(f"{x.run_id}: {x.status}; " + ", ".join(f"{d['dataset']} {d['rows']:,}/{d['portal_count']:,}" for d in m["datasets"]))
    print("PHASE 1 GATE:", "PASSED" if ok else "NOT PASSED")
    return 0 if ok else 1


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("--force", action="store_true", help="download every dataset even if the portal has not changed")
    a.add_argument("--gate", action="store_true", help="check the Phase 1 gate")
    a.add_argument("--require-token", action="store_true",
                   help="stop unless MD_SODA_APP_TOKEN is set (opt-in; decision D5 was revised: tokenless runs are allowed, with backoff, "
                        "because the datasets are public and a missing or rejected token only lowers the request limits)")
    args = a.parse_args()
    if args.require_token and not os.environ.get("MD_SODA_APP_TOKEN"):
        sys.exit("MD_SODA_APP_TOKEN is not set: --require-token needs a Socrata app token (https://dev.socrata.com/docs/app-tokens)")
    if os.environ.get("GMI_SCHEDULED") and not os.environ.get("MD_SODA_APP_TOKEN"):
        log("scheduled run without a Socrata app token: using the public limits (slower if the portal throttles; retries absorb it)")
    sys.exit(gate() if args.gate else run(args.force))
