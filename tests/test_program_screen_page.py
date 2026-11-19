"""The dashboard computes the statewide program screen in the page. It must agree with src/models/program_screen.py."""
import glob
import json
import os
import re
import sys
from pathlib import Path

import pandas as pd
import pytest
import yaml

from src.models import program_screen as S

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "legacy" / "gst" / "page" / "index.html"
sys.path.insert(0, str(ROOT / "legacy" / "gst" / "scripts"))


def test_the_pages_settings_are_the_assumptions_file():
    m = re.search(r"const PSCFG = /\*program_screen\*/(\{.*?\});", PAGE.read_text())
    assert m and json.loads(m.group(1)) == yaml.safe_load((ROOT / "config" / "assumptions.yaml").read_text())["program_screen"]


def _chromium():
    found = os.environ.get("PAGE_TEST_CHROMIUM") or next(iter(sorted(glob.glob("/opt/pw-browsers/chromium*/chrome-linux*/chrome"))), None)
    return found if found and Path(found).exists() else None


def test_the_page_and_the_module_flag_the_same_programs():
    pw = pytest.importorskip("playwright.sync_api")
    import page_test as PT
    if not PT.D3.exists():
        pytest.skip("the vendored d3 the page harness needs is not here")
    tables = PT.tables_from([ROOT / "site_data", ROOT / "reference"])
    # the site build writes this file from reference/ (src/pipeline/site.py derived); without it the page shows no audit findings
    tables["audit_findings_by_program"] = S.reported_findings().to_csv(index=False)
    html = PT.build_html(tables, {"spendType": "All", "years": [], "areas": [], "agencies": [], "tab": "budget"})
    tmp = ROOT / "legacy" / "gst" / "model"
    tmp.mkdir(exist_ok=True)
    f = tmp / "program_screen_test.html"
    f.write_text(html)
    try:
        with pw.sync_playwright() as p:
            try:
                exe = _chromium()
                browser = p.chromium.launch(**({"executable_path": exe} if exe else {}))
            except Exception as e:  # noqa: BLE001
                pytest.skip(f"no browser: {e}")
            page = browser.new_page()
            page.goto(f.as_uri())
            page.wait_for_function("window.gstProgramScreen && window.gstProgramScreen() !== null", timeout=30000)
            page.evaluate("document.getElementById('t-budget').click()")  # a tab draws when it is opened
            page.wait_for_function("document.getElementById('prgFind').textContent.length > 0", timeout=30000)
            got = pd.DataFrame(page.evaluate("window.gstProgramScreen()"))
            phone = browser.new_page(viewport={"width": 390, "height": 900})
            phone.goto(f.as_uri())
            phone.evaluate("document.getElementById('t-budget').click()")
            phone.wait_for_function("document.getElementById('prgFind').textContent.length > 0", timeout=30000)
            overflow = phone.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            card = page.evaluate("document.getElementById('prgFind').textContent")
            browser.close()
    finally:
        f.unlink(missing_ok=True)
    want = S.screen(pd.read_csv(ROOT / "site_data" / "f_program.csv", dtype={"agency_code": str, "program_code": str}), *S.reference())
    key = lambda d: d.assign(k=d.agency_code.astype(str) + "|" + d.unit_name.astype(str) + "|" + d.program_code.astype(str).str.lstrip("0")).set_index("k")  # the page reads codes as numbers, so 05 is 5 there.sort_index()  # noqa: E731
    g, w = key(got), key(want)
    assert list(g.index) == list(w.index) and len(g) > 200
    assert (g.signals == w.signals).all() and (g.reported_findings == w.reported_findings).all()
    assert ((g.growth_multiple - w.growth_multiple).abs() < 1e-3).all() and ((g.spend_last - w.spend_last).abs() < 1).all()
    assert (g.swing_fy.astype(int) == w.swing_fy.astype(int)).all()
    assert f"{int((w.signals == 2).sum())} of {len(w)} programs" in card
    assert overflow <= 1  # the wide table scrolls inside its own box; the page does not scroll sideways on a phone
