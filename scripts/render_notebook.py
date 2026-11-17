"""Execute notebooks/walkthrough.ipynb in place, write notebooks/walkthrough.html (copied into the site by make site) and refresh docs/figures/overview/*.png.

    python scripts/render_notebook.py            # execute, save outputs, render, extract figures
    python scripts/render_notebook.py --check    # execute only; exit 1 on any cell error

The page is rendered here rather than with nbconvert's lab template so that it reads as a report, not a code listing:
the site's own styles, navigation and disclaimer; a skip link and a table of contents; code folded under "Show the code";
every chart a <figure> with alt text, a caption that states the finding and its data table; every table captioned with
header scopes. It loads nothing from another host. `validate` fails the render if any of that is missing.
"""
import html
import re
from urllib.parse import unquote
import sys
from pathlib import Path

import mistune
import nbformat
from bs4 import BeautifulSoup
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
NB = ROOT / "notebooks" / "walkthrough.ipynb"
OUT = NB.parent / "walkthrough.html"
MD = mistune.create_markdown(escape=False, plugins=["table", "strikethrough"])

EXTRA_CSS = """<style>
.skip{position:absolute;left:-9999px;top:0}.skip:focus{left:16px;top:8px;background:var(--s-bg);padding:6px 10px;z-index:10}
header.site{max-width:880px;margin:0 auto;padding:16px 16px 0}header.site .note{margin:0}
nav.toc{border:1px solid var(--s-line);border-radius:6px;padding:10px 16px;margin:16px 0;font-size:15px}nav.toc ul{margin:.3em 0;padding-left:0;list-style:none}nav.toc li{margin:.15em 0}td a{white-space:nowrap}
h1 + p.dek{font-size:18px;color:var(--s-muted);margin-top:0}
h2{border-top:1px solid var(--s-line);padding-top:1em}h2 a.anchor{opacity:0;text-decoration:none;margin-left:.3em}h2:hover a.anchor,h2 a.anchor:focus{opacity:1}
details{margin:.6em 0}summary{cursor:pointer;color:var(--s-link);font-size:14px}details.code pre{margin-top:.5em}
pre{overflow-x:auto;border:1px solid var(--s-line);border-radius:6px;padding:10px 12px;font-size:13px;line-height:1.45}
pre.out{border-style:dashed}
figure.chart{margin:1.4em 0}figure.chart figcaption{font-size:15px;margin:.5em 0}
table caption{caption-side:top;text-align:left;font-weight:600;padding:4px 0 8px;font-size:14px}
.tbl{overflow-x:auto;margin:1em 0}td{font-variant-numeric:tabular-nums}
footer{max-width:880px;margin:0 auto;padding:0 16px 48px;color:var(--s-muted);font-size:14px}
</style>"""


def anchor(text):
    """The id Jupyter gives a heading (spaces to hyphens), so the same #links work in Jupyter and on the page."""
    return re.sub(r"\s+", "-", text.strip())


def output_html(o):
    t = o["output_type"]
    if t == "stream":
        return f'<pre class="out">{html.escape("".join(o["text"]))}</pre>'
    if t == "error":
        raise SystemExit(f"cell error: {o['ename']}: {o['evalue']}")
    d = o.get("data", {})
    if "text/html" in d:
        h = "".join(d["text/html"]) if isinstance(d["text/html"], list) else d["text/html"]
        return h if "<figure" in h or "<details" in h else f'<div class="tbl">{h}</div>' if "<table" in h else h
    if "text/markdown" in d:
        return MD("".join(d["text/markdown"]))
    if "image/png" in d:
        alt = o.get("metadata", {}).get("image/png", {}).get("alt", "")
        return f'<img alt="{html.escape(alt)}" src="data:image/png;base64,{d["image/png"].strip()}">'
    if "text/plain" in d:
        return f'<pre class="out">{html.escape("".join(d["text/plain"]))}</pre>'
    return ""


def render(nb):
    from src.pipeline.site import DISCLAIMER, FY_NOTE, NAV, PAGE_CSS, REPO
    title = nb.metadata.get("title", "GMI Savings Tracker walkthrough")
    parts = []
    for cell in nb.cells:
        if cell.cell_type == "markdown":
            parts.append(MD(cell.source))
        elif cell.cell_type == "code":
            label = "Show the code for this step" if cell.outputs else "Show the setup code"
            parts.append(f'<details class="code"><summary>{label}</summary><pre><code class="language-python">{html.escape(cell.source)}</code></pre></details>')
            parts.extend(output_html(o) for o in cell.outputs)
    soup = BeautifulSoup("".join(parts), "html.parser")
    toc = []
    for h in soup.find_all(["h1", "h2", "h3"]):
        h["id"] = anchor(h.get_text())
        if h.name == "h2":
            toc.append(f'<li><a href="#{h["id"]}">{html.escape(h.get_text())}</a></li>')
            a = soup.new_tag("a", href=f'#{h["id"]}', attrs={"class": "anchor", "aria-label": f"Link to {h.get_text()}"})
            a.string = "#"
            h.append(a)
    for th in soup.select("thead th"):
        th["scope"] = "col"
    for th in soup.select("tbody th"):
        th["scope"] = "row"
    for box in soup.select("div.tbl, pre"):  # scrollable on a phone, so reachable by keyboard (WCAG 2.1.1)
        box["tabindex"] = "0"
        cap = box.find("caption")
        box["role"] = "region"
        box["aria-label"] = cap.get_text() if cap else ("Code" if box.find("code") else "Output")
    nav = soup.new_tag("nav", attrs={"class": "toc", "aria-label": "Contents"})
    nav.append(BeautifulSoup(f"<strong>Contents</strong><ul>{''.join(toc)}</ul>", "html.parser"))
    (soup.select_one("details.code") or soup.find("h2")).insert_before(nav)  # after the introduction, before any code
    desc = ("A walkthrough of Maryland's GMI reported savings checked against State payments, spending forecasts with calibrated "
            "ranges, and savings leads, computed from the published tables.")
    page = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{html.escape(title)}</title><meta name="description" content="{html.escape(desc)}">{PAGE_CSS}{EXTRA_CSS}</head><body>'
            f'<a class="skip" href="#content">Skip to main content</a>'
            f'<header class="site"><div class="note">{html.escape(DISCLAIMER)}. {html.escape(FY_NOTE)}<nav aria-label="Site">{NAV} · '
            f'<a href="{REPO}">Source code</a></nav></div></header>'
            f'<main id="content">{soup}</main>'
            f'<footer>Rendered from <a href="{REPO}/blob/main/notebooks/walkthrough.ipynb">notebooks/walkthrough.ipynb</a> by '
            f'scripts/render_notebook.py. {html.escape(DISCLAIMER)}.</footer></body></html>')
    return page


def validate(page):
    """The accessibility and self-containment rules this page promises; returns a list of problems (empty when clean)."""
    s = BeautifulSoup(page, "html.parser")
    bad = []
    if not s.html.get("lang"):
        bad.append("no lang on <html>")
    if not s.title or s.title.get_text().strip() in ("", "Notebook"):
        bad.append("missing or generic <title>")
    if len(s.find_all("h1")) != 1:
        bad.append("not exactly one <h1>")
    levels = [int(h.name[1]) for h in s.find_all(re.compile(r"^h[1-6]$"))]
    if any(b - a > 1 for a, b in zip(levels, levels[1:])):
        bad.append("a heading level is skipped")
    for img in s.find_all("img"):
        alt = img.get("alt", "").strip()
        if not alt or alt.startswith("No description"):
            bad.append("an image without alt text")
    for fig in s.select("figure.chart"):
        if not fig.find("figcaption") or not fig.find("table"):
            bad.append(f"figure {fig.get('id')} lacks a caption or data table")
    for t in s.find_all("table"):
        if t.find("caption") is None and not _is_markdown_table(t):
            bad.append("a data table without a <caption>")
        if t.find("thead") and t.select("thead th:not([scope])"):
            bad.append("a table header cell without scope")
    if re.search(r"<(script|link|img)\b[^>]*\b(src|href)=\"https?://", page):
        bad.append("loads something from another host")
    for a in s.select('a[href^="#"]'):
        if len(a["href"]) > 1 and not s.find(id=unquote(a["href"][1:])):  # browsers decode %27 before matching the id
            bad.append(f"broken in-page link {a['href']}")
    return bad


def _is_markdown_table(t):
    return "dataframe" not in (t.get("class") or []) and not (t.get("id") or "").startswith("T_")


def main(check=False):
    nb = nbformat.read(NB, as_version=4)
    NotebookClient(nb, timeout=600, kernel_name="python3", resources={"metadata": {"path": str(NB.parent)}}).execute()
    if check:
        print("notebook executed without errors")
        return 0
    nbformat.write(nb, NB)
    page = render(nb)
    problems = validate(page)
    if problems:
        raise SystemExit("walkthrough.html fails its checks: " + "; ".join(sorted(set(problems))))
    OUT.write_text(page, encoding="utf-8")  # src/pipeline/site.py copies it into the site
    import subprocess
    subprocess.run([sys.executable, "-m", "src.pipeline.overview_figures"], cwd=ROOT, check=True)
    print("wrote notebooks/walkthrough.html", f"({len(page) / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main("--check" in sys.argv))
