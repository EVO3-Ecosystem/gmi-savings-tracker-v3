"""Counts typed in the docs come from the files they describe, so they cannot go stale.

    python -m src.pipeline.doc_counts            # rewrite every span in README.md, CHANGELOG.md, docs/*.md and docs/wiki/*.md
    python -m src.pipeline.doc_counts --check    # exit 1 and list the stale spans; changes nothing
    python -m src.pipeline.doc_counts --list     # print every count

A span is `<!-- n:NAME -->value<!-- /n -->`. NAME is one of the counts below, or NAME_word / NAME_Word for the number
spelled out ("ten" / "Ten"). Works offline: it reads only files in the repository, never the database.

    checks, checks_pass, checks_warn, checks_fail   rows of site_data/run_checks.csv (the last published run)
    marts                 SQL files in sql/mart/
    reference_files       files in reference/
    datasets              portal datasets in config/datasets.yaml
    tabs                  tab buttons in legacy/gst/page/index.html
    tests                 test functions (`def test_`) under tests/; parametrized cases are counted once
    published_tables      CSV files in site_data/ other than manifest.csv
    documented_columns    rows of docs/schemas/{source,warehouse,dashboard}_columns.csv
    model_cards           Markdown files in docs/models/
"""
import argparse
import csv
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SPAN = re.compile(r"(<!-- n:([A-Za-z0-9_]+) -->)(.*?)(<!-- /n -->)", re.S)
WORDS = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen "
         "eighteen nineteen twenty").split()
TAB = re.compile(r"<button\b[^>]*\brole=\"tab\"[^>]*>")
TEST = re.compile(r"^\s*(?:async\s+)?def test_\w+\s*\(", re.M)


def _rows(path):
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _files(folder, pattern="*"):
    return sorted(p for p in folder.glob(pattern) if p.is_file() and not p.name.startswith(".")) if folder.is_dir() else []


def check_counts(root):
    """Checks of the last published run, by result (the column is `status` in the published file, `result` in the database)."""
    rows = _rows(root / "site_data" / "run_checks.csv")
    got = [r.get("status") or r.get("result") or "" for r in rows]
    return {"checks": len(rows), "checks_pass": got.count("pass"), "checks_warn": got.count("warn"), "checks_fail": got.count("fail")}


def mart_count(root):
    return len(_files(root / "sql" / "mart", "*.sql"))


def reference_count(root):
    return len(_files(root / "reference"))


def dataset_count(root):
    path = root / "config" / "datasets.yaml"
    return len((yaml.safe_load(path.read_text()) or {}).get("datasets") or {}) if path.is_file() else 0


def tab_count(root):
    path = root / "legacy" / "gst" / "page" / "index.html"
    return len(TAB.findall(path.read_text(encoding="utf-8"))) if path.is_file() else 0


def test_count(root):
    return sum(len(TEST.findall(p.read_text(encoding="utf-8"))) for p in _files(root / "tests", "test_*.py"))


test_count.__test__ = False  # a counter, not a test, if a test module imports it by name


def published_count(root):
    return len([p for p in _files(root / "site_data", "*.csv") if p.name != "manifest.csv"])


def column_count(root):
    return sum(len(_rows(root / "docs" / "schemas" / f"{n}_columns.csv")) for n in ("source", "warehouse", "dashboard"))


def model_card_count(root):
    return len(_files(root / "docs" / "models", "*.md"))


def counts(root=ROOT):
    root = Path(root)
    return {**check_counts(root), "marts": mart_count(root), "reference_files": reference_count(root), "datasets": dataset_count(root),
            "tabs": tab_count(root), "tests": test_count(root), "published_tables": published_count(root),
            "documented_columns": column_count(root), "model_cards": model_card_count(root)}


def value(name, got):
    """The text a span should hold, or None when the name is not a known count."""
    base, _, form = name.rpartition("_")
    if form in ("word", "Word") and base in got:
        n = got[base]
        text = WORDS[n] if 0 <= n < len(WORDS) else f"{n:,}"
        return text.capitalize() if form == "Word" else text
    return f"{got[name]:,}" if name in got else None


def documents(root=ROOT):
    root = Path(root)
    return [p for p in [root / "README.md", root / "CHANGELOG.md", *_files(root / "docs", "*.md"), *_files(root / "docs" / "wiki", "*.md")] if p.is_file()]


def apply(text, got):
    """(new text, problems): every span set to its count; a span naming an unknown count is a problem and left alone."""
    problems = []

    def sub(m):
        want = value(m.group(2), got)
        if want is None:
            problems.append(f"unknown count n:{m.group(2)}")
            return m.group(0)
        if m.group(3) != want:
            problems.append(f"n:{m.group(2)} says {m.group(3).strip()!r}, the files give {want!r}")
        return m.group(1) + want + m.group(4)
    return SPAN.sub(sub, text), problems


def main(argv=None, root=ROOT):
    ap = argparse.ArgumentParser(description="Keep the counts typed in the docs equal to the files they count.")
    ap.add_argument("--check", action="store_true", help="exit 1 if any span is stale; write nothing")
    ap.add_argument("--list", action="store_true", help="print every count and exit")
    a = ap.parse_args(argv)
    got = counts(root)
    if a.list:
        print("\n".join(f"{k}: {v:,}" for k, v in got.items()))
        return 0
    stale = spans = 0
    for path in documents(root):
        text = path.read_text(encoding="utf-8")
        new, problems = apply(text, got)
        spans += len(SPAN.findall(text))
        unknown = [p for p in problems if p.startswith("unknown")]
        for p in problems if a.check else unknown:
            print(f"{path.relative_to(root)}: {p}", file=sys.stderr)
        stale += len(problems) if a.check else len(unknown)
        if not a.check and new != text:
            path.write_text(new, encoding="utf-8")
            print(f"updated {path.relative_to(root)} ({len(problems) - len(unknown)} spans)")
    print(f"doc-counts: {spans} spans in {len(documents(root))} files; {stale} {'stale or unknown' if a.check else 'unknown'}")
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
