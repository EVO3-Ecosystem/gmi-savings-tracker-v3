"""The monthly Extract and build workflow: the generated docs are refreshed from the new run before the tests that check them."""
from pathlib import Path

import yaml

WF = yaml.safe_load((Path(__file__).resolve().parents[1] / ".github/workflows/extract-smoke.yml").read_text())
STEPS = WF["jobs"]["extract"]["steps"]


def _index(needle):
    for i, s in enumerate(STEPS):
        if needle in (s.get("run") or "") or needle in (s.get("name") or ""):
            return i
    raise AssertionError(f"no step mentions {needle!r}")


def test_docs_are_regenerated_from_the_run_before_pytest():
    # a new run has a new as-of date, so the committed README is always behind it: pytest compares against regenerated facts
    assert _index("python -m src.models.doc_facts") < _index("pytest -q")


def test_the_refresh_patch_is_kept_with_the_run_evidence():
    step = STEPS[_index("docs-refresh.patch")]
    assert step.get("if") == "always()"
    upload = next(s for s in STEPS if "upload-artifact" in (s.get("uses") or ""))
    assert "data/review/*" in upload["with"]["path"]


def test_build_comes_before_the_doc_refresh():
    assert _index("src.pipeline.build") < _index("python -m src.models.doc_facts")
