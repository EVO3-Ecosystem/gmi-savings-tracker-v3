"""Counts typed in the docs equal the files they count (src/pipeline/doc_counts.py)."""
from pathlib import Path

from src.pipeline import doc_counts as D

ROOT = Path(__file__).resolve().parents[1]


def tree(tmp_path):
    """A small repository: 3 checks (2 pass, 1 warn), 2 marts, 3 reference files, 2 datasets, 4 tabs, 3 tests, 2 published tables."""
    for folder in ("site_data", "sql/mart", "reference", "config", "legacy/gst/page", "tests", "docs/schemas", "docs/models", "docs/wiki"):
        (tmp_path / folder).mkdir(parents=True)
    (tmp_path / "site_data" / "run_checks.csv").write_text('run_id,stage,check,status,detail\nr,raw,a,pass,x\nr,core,b,pass,"y, z"\nr,mart,c,warn,w\n')
    (tmp_path / "site_data" / "manifest.csv").write_text("file,source,rows,changed\n")
    (tmp_path / "site_data" / "f_area.csv").write_text("a\n1\n")
    (tmp_path / "site_data" / "snapshot.json").write_text("{}")
    for n in ("01_a.sql", "02_b.sql", "notes.txt"):
        (tmp_path / "sql" / "mart" / n).write_text("select 1")
    for n in ("a.csv", "b.csv", "c.csv"):
        (tmp_path / "reference" / n).write_text("x\n")
    (tmp_path / "config" / "datasets.yaml").write_text("domain: example.org\ndatasets:\n  budget: {id: aaaa-1111}\n  payments: {id: bbbb-2222}\n")
    (tmp_path / "legacy" / "gst" / "page" / "index.html").write_text(
        "".join(f'<button role="tab" id="t-{i}" data-tab="{i}">T{i}</button>' for i in range(4)) + '<button id="other">x</button>')
    (tmp_path / "tests" / "test_a.py").write_text("def test_one():\n    pass\n\n\nclass TestB:\n    def test_two(self):\n        pass\n\n\ndef helper_test_x():\n    pass\n")
    (tmp_path / "tests" / "test_b.py").write_text("async def test_three():\n    pass\n")
    (tmp_path / "tests" / "conftest.py").write_text("def test_not_collected_here():\n    pass\n")
    for n, rows in (("source", 2), ("warehouse", 3), ("dashboard", 1)):
        (tmp_path / "docs" / "schemas" / f"{n}_columns.csv").write_text("table,column\n" + "t,c\n" * rows)
    (tmp_path / "docs" / "models" / "forecast.md").write_text("# card\n")
    return tmp_path


def test_counts_on_a_small_tree(tmp_path):
    got = D.counts(tree(tmp_path))
    assert got == {"checks": 3, "checks_pass": 2, "checks_warn": 1, "checks_fail": 0, "marts": 2, "reference_files": 3, "datasets": 2,
                   "tabs": 4, "tests": 3, "published_tables": 2, "documented_columns": 6, "model_cards": 1}


def test_counts_are_zero_on_an_empty_tree(tmp_path):
    assert set(D.counts(tmp_path).values()) == {0}


def test_values_are_formatted_and_spelled():
    got = {"checks": 1234, "tabs": 10, "datasets": 6, "tests": 238}
    assert D.value("checks", got) == "1,234"
    assert D.value("tabs_word", got) == "ten" and D.value("tabs_Word", got) == "Ten" and D.value("datasets_word", got) == "six"
    assert D.value("tests_word", got) == "238"  # no word for a large number
    assert D.value("nothing", got) is None and D.value("nothing_word", got) is None


def test_a_stale_span_is_detected_and_then_rewritten(tmp_path, capsys):
    root = tree(tmp_path)
    readme = root / "README.md"
    readme.write_text("Runs <!-- n:checks -->99<!-- /n --> checks on <!-- n:datasets_word -->two<!-- /n --> datasets.\n")
    (root / "docs" / "wiki" / "Home.md").write_text("<!-- n:tabs_Word -->Nine<!-- /n --> tabs.\n")
    assert D.main(["--check"], root=root) == 1
    err = capsys.readouterr().err
    assert "README.md: n:checks says '99', the files give '3'" in err and "Home.md" in err and "datasets" not in err
    assert "99" in readme.read_text()  # --check writes nothing
    assert D.main([], root=root) == 0
    assert readme.read_text() == "Runs <!-- n:checks -->3<!-- /n --> checks on <!-- n:datasets_word -->two<!-- /n --> datasets.\n"
    assert (root / "docs" / "wiki" / "Home.md").read_text() == "<!-- n:tabs_Word -->Four<!-- /n --> tabs.\n"
    assert D.main(["--check"], root=root) == 0


def test_an_unknown_name_fails_in_both_modes_and_is_left_alone(tmp_path):
    root = tree(tmp_path)
    (root / "README.md").write_text("<!-- n:martz -->51<!-- /n -->\n")
    assert D.main(["--check"], root=root) == 1 and D.main([], root=root) == 1
    assert (root / "README.md").read_text() == "<!-- n:martz -->51<!-- /n -->\n"


def test_the_repository_docs_are_current():
    """If this fails, a count changed (a test, a mart, a check was added): run `make doc-counts`."""
    got = D.counts(ROOT)
    stale = {str(p.relative_to(ROOT)): problems for p in D.documents(ROOT) if (problems := D.apply(p.read_text(encoding="utf-8"), got)[1])}
    assert not stale, stale


def test_the_readme_uses_spans_for_the_counts_it_types():
    names = {m[1] for m in D.SPAN.findall((ROOT / "README.md").read_text(encoding="utf-8"))}
    assert {"checks", "marts", "reference_files", "tabs_Word"} <= names
