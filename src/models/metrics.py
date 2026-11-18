"""Metric registry: every headline number is defined once in config/metrics.yml and evaluated here.

    python -m src.models.metrics                       # print every metric from the checked-in snapshot (site_data/)
    python -m src.models.metrics --out site/metrics.json   # also write metrics.json (definitions + current values)

The registry feeds the README facts (src/models/doc_facts.py), the tests and metrics.json; the dashboard and the MCP server can
read metrics.json, so a definition changes in one place. Each metric's SQL is one read-only SELECT over the marts (schema
`mart`), checked by src/mcp/guard.py before it runs.
"""
import argparse
import json
import math
import re
import sys
from pathlib import Path

import duckdb
import yaml

from src.mcp import guard

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "config" / "metrics.yml"
REQUIRED = ("id", "name", "definition", "unit", "grain", "tables", "owner", "shown_in", "sql")
UNITS = ("usd", "count", "ratio")
ID = re.compile(r"^[a-z][a-z0-9_]*$")


class RegistryError(ValueError):
    """The registry file is malformed."""


def load(path=REGISTRY):
    """The metrics, validated: unique snake_case ids, every field present, a known unit, a guarded SELECT."""
    data = yaml.safe_load(Path(path).read_text())
    metrics = (data or {}).get("metrics")
    if not isinstance(metrics, list) or not metrics:
        raise RegistryError("config/metrics.yml needs a non-empty `metrics:` list")
    seen = set()
    for m in metrics:
        missing = [k for k in REQUIRED if k not in m or m[k] in (None, "", [])]
        if missing:
            raise RegistryError(f"metric {m.get('id', '?')!r} is missing {missing}")
        if not ID.match(m["id"]) or m["id"] in seen:
            raise RegistryError(f"metric id {m['id']!r} must be unique snake_case")
        seen.add(m["id"])
        if m["unit"] not in UNITS:
            raise RegistryError(f"metric {m['id']}: unit must be one of {UNITS}")
        try:
            m["sql"] = guard.check(m["sql"])
        except guard.QueryRejected as e:
            raise RegistryError(f"metric {m['id']}: {e}") from None
    return metrics


def value(con, metric_id, registry=None):
    """The current value of one metric (a float, or an int for counts); None when the data has no rows for it."""
    for m in registry or load():
        if m["id"] == metric_id:
            v = con.execute(m["sql"]).fetchone()[0]
            if v is None:
                return None
            v = float(v)
            return int(v) if m["unit"] == "count" and v == int(v) else v
    raise KeyError(metric_id)


def evaluate(con, registry=None, strict=True):
    """Every metric with its current value, as plain dicts (what metrics.json holds).

    strict=False records value null for a metric whose marts are not in this export (a partial export in a test), instead of failing.
    """
    out = []
    for m in registry or load():
        try:
            v = con.execute(m["sql"]).fetchone()[0]
        except (duckdb.CatalogException, duckdb.BinderException):
            if strict:
                raise
            v = None
        if v is not None:
            v = float(v)
            if math.isnan(v) or math.isinf(v):
                v = None
            elif m["unit"] == "count" and v == int(v):
                v = int(v)
        out.append({k: m[k] for k in ("id", "name", "definition", "unit", "grain", "tables", "owner", "shown_in")} | {"value": v})
    return out


def write_json(export_dir, path):
    """Write metrics.json (every definition with its current value) from an export directory of marts."""
    from src.mcp.store import Store
    rows = evaluate(Store(export_dir=export_dir, prefer="export").con, strict=False)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps({"source": "config/metrics.yml", "metrics": rows}, indent=1) + "\n")
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--export", help="export directory to read (default: the checked-in site_data snapshot)")
    ap.add_argument("--out", help="write metrics.json here")
    a = ap.parse_args(argv)
    export = a.export or ROOT / "site_data"
    if a.out:
        rows = write_json(export, a.out)
        print(f"wrote {a.out} ({len(rows)} metrics)")
    else:
        from src.mcp.store import Store
        rows = evaluate(Store(export_dir=export, prefer="export").con)
    for r in rows:
        print(f"{r['id']:42} {r['value']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
