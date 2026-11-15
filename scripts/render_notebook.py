"""Execute notebooks/walkthrough.ipynb in place, write notebooks/walkthrough.html (copied into the site by make site) and refresh docs/figures/overview/*.png.

    python scripts/render_notebook.py            # execute, save outputs, render, extract figures
    python scripts/render_notebook.py --check    # execute only; exit 1 on any cell error

The HTML embeds its images and has every external script and stylesheet link removed, because the site loads
nothing from a third-party host.
"""
import re
import sys
from pathlib import Path

import nbformat
from nbclient import NotebookClient
from nbconvert import HTMLExporter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
NB = ROOT / "notebooks" / "walkthrough.ipynb"
EXTERNAL = re.compile(r"<(script|link)\b[^>]*\b(?:src|href)=\"https?://[^\"]*\"[^>]*>(?:\s*</script>)?", re.I)


def main(check=False):
    nb = nbformat.read(NB, as_version=4)
    NotebookClient(nb, timeout=600, kernel_name="python3", resources={"metadata": {"path": str(NB.parent)}}).execute()
    if check:
        print("notebook executed without errors")
        return 0
    nbformat.write(nb, NB)
    body, _ = HTMLExporter(template_name="lab", embed_images=True).from_notebook_node(nb)
    body = EXTERNAL.sub("", body)
    (NB.parent / "walkthrough.html").write_text(body, encoding="utf-8")  # src/pipeline/site.py copies it into the site
    import subprocess
    subprocess.run([sys.executable, "-m", "src.pipeline.overview_figures"], cwd=ROOT, check=True)
    print("wrote notebooks/walkthrough.html", f"({len(body) / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main("--check" in sys.argv))
