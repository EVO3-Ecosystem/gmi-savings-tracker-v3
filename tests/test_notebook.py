"""The walkthrough notebook reads only the published tables, is committed executed, and its figures come from them too."""
import json
import re
from pathlib import Path

import pytest

from src import published as P

ROOT = Path(__file__).resolve().parents[1]
NB = json.loads((ROOT / "notebooks" / "walkthrough.ipynb").read_text())
CODE = [c for c in NB["cells"] if c["cell_type"] == "code"]
SRC = "\n".join("".join(c["source"]) for c in CODE)


def test_published_tables_load_and_the_run_is_described():
    info = P.run_info()
    assert info["tables"] == len(P.tables()) > 50 and info["checks"] == info["passed"] + info["warnings"] + info["failed"]
    assert P.has("f_forecast") and not P.has("no_such_table") and len(P.load("f_forecast"))


def test_notebook_never_touches_the_warehouse_or_refits_a_model():
    for banned in ("md_transparency", "duckdb", "data/raw", "mart.", "core.", "src.pipeline.build", "src.pipeline.extract"):
        assert banned not in SRC, banned
    models = set(re.findall(r"from src\.models import (\w+)", SRC))
    assert models <= {"forecast_published"}  # the one stated exception: rebuilding the forecast from its published inputs


def test_every_table_the_notebook_loads_is_published():
    names = set(re.findall(r"P\.load\(\"(\w+)\"\)", SRC))
    assert names and not [n for n in names if not P.has(n)]


def test_notebook_is_committed_executed_without_errors():
    assert all(c["execution_count"] for c in CODE)
    outputs = [o for c in CODE for o in c["outputs"]]
    assert not [o for o in outputs if o["output_type"] == "error"]
    assert sum("image/png" in o.get("data", {}) for o in outputs) >= 6


def test_rendered_walkthrough_loads_nothing_from_another_host():
    html = (ROOT / "notebooks" / "walkthrough.html").read_text()
    assert not re.search(r"<(script|link|img)\b[^>]*\b(src|href)=\"https?://", html)


@pytest.mark.parametrize("name", ["forecast_fan", "range_coverage", "spending_base", "savings_status", "opportunities", "checks"])
def test_overview_figures_exist(name):
    assert (ROOT / "docs" / "figures" / "overview" / f"{name}.png").stat().st_size > 10_000
