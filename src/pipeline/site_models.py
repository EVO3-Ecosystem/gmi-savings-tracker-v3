"""models.html: every model card of the tracker, each headed by its live score from mart.d_model_registry, and the analysis figures.

The cards are docs/models/*.md rendered with site.md_to_html; the scores come from the export (d_model_registry.csv), so the
page shows the same held-out numbers as the dashboard's Data tab. Retired cards are listed last, marked as retired.
"""
import csv
import html
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CARDS = ROOT / "docs" / "models"

# reading order: what the dashboard shows first, then the supporting models; a card not listed here is added at the end
ORDER = ["forecast", "challenger", "revenue", "savings", "recommendations", "opportunities", "anomaly", "clustering",
         "payment_screen", "payee_classifier", "grant_groups", "grant_clusters"]

# analysis figures under docs/figures/ (copied to site/figures/), with what each one shows
FIGURES = [
    ("overview/forecast_fan.png", "Spending forecast with calibrated ranges", "Actual controllable purchases, the forecast to FY2031 and its conformally calibrated 10th–90th percentile range."),
    ("overview/range_coverage.png", "Range coverage, raw and calibrated", "Share of held-out outcomes that fell inside the forecast range, against the nominal 80%, with 95% Wilson intervals."),
    ("overview/spending_base.png", "The controllable spending base", "Operating budget split into what an agency can change and what it cannot."),
    ("overview/savings_status.png", "GMI's reported savings, checked", "Each reported item and whether the change in payments to the matching vendors shows it."),
    ("overview/opportunities.png", "Opportunity leads by detector", "Likely value of each detector's leads at stated rates; detectors overlap, so bars are never added."),
    ("readme/detector_backtest.png", "Detector backtest: persistence", "Share of flagged units flagged again the next year, against like-sized unflagged units."),
    ("readme/detector_divergence.png", "Detector backtest: next-year change", "Median next-year change in spending, flagged against unflagged units."),
    ("readme/model_registry.png", "Model registry", "Every model, its baseline and its held-out score, read from each model's own evaluation."),
    ("readme/drift.png", "Data drift by year", "Population stability index and KS statistic between consecutive fiscal years."),
    ("readme/fund_shift.png", "General Fund shift", "Programs whose General Fund share rose 20+ points in two years."),
    ("readme/payment_screen.png", "Payment screen", "Possible duplicate and repeated payment lines, as leads to review."),
    ("reconciliation.png", "Reconciliation with DBM's budget books", "Every fiscal year's total against the State's own documents."),
    ("vendor_concentration_hhi.png", "Vendor concentration (HHI)", "Herfindahl–Hirschman Index of vendor shares by focus area."),
    ("budget_by_stage.png", "Budget by stage", "Each year's operating budget at the stage confirmed for it."),
    ("check_history.png", "Check history", "Pipeline checks passed on every run."),
]

TOKENS = """<style>
.mc-score{display:flex;flex-wrap:wrap;gap:8px 18px;margin:8px 0 4px;padding:10px 12px;border:1px solid var(--s-line);border-radius:8px;font-size:14px}
.mc-score b{font-variant-numeric:tabular-nums}.mc-yes{color:#1a7f37}.mc-no{color:#9a6700}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]) .mc-yes{color:#7ee2a8}:root:not([data-theme="light"]) .mc-no{color:#f2cc60}}
:root[data-theme="dark"] .mc-yes{color:#7ee2a8}:root[data-theme="dark"] .mc-no{color:#f2cc60}
.mc-toc{columns:2;column-gap:24px;padding-left:18px}@media (max-width:600px){.mc-toc{columns:1}}
.mc-card{border-top:1px solid var(--s-line);margin-top:28px;padding-top:4px}.mc-card h2{margin-top:.8em}
.mc-retired{opacity:.75}.mc-figs{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:16px}
.mc-figs figure{margin:0}.mc-figs figcaption{font-size:13px;color:var(--s-muted);margin-top:4px}
</style>"""


def registry(src):
    f = Path(src) / "d_model_registry.csv"
    if not f.is_file():
        return {}
    with f.open(newline="") as fh:
        return {Path(r["model_card"]).stem: r for r in csv.DictReader(fh) if r.get("model_card")}


def _num(v):
    try:
        return f"{float(v):.2f}"
    except (TypeError, ValueError):
        return ""


def score_box(r):
    if not r:
        return ""
    beats = str(r.get("beats_baseline", "")).lower() in ("true", "1")
    bits = [f"<span>Metric: {html.escape(r['metric'])}</span>"]
    if _num(r.get("model_score")):
        bits.append(f"<span>Model <b>{_num(r['model_score'])}</b></span>")
    if _num(r.get("baseline_score")):
        bits.append(f"<span>{html.escape(r.get('baseline') or 'Baseline')} <b>{_num(r['baseline_score'])}</b></span>")
    if r.get("beats_baseline", "") != "":
        bits.append(f'<span class="{"mc-yes" if beats else "mc-no"}">{"Beats" if beats else "Does not beat"} its baseline</span>')
    bits.append(f"<span>Decision: {html.escape(r.get('decision', ''))}</span>")
    if r.get("shown_as"):
        bits.append(f"<span>Shown as: {html.escape(r['shown_as'])}</span>")
    return '<div class="mc-score" role="note" aria-label="Live score from this build">' + "".join(bits) + "</div>"


def cards():
    found = {f.stem: f for f in CARDS.glob("*.md")}
    return [found[k] for k in ORDER if k in found] + sorted(v for k, v in found.items() if k not in ORDER)


def body(src, md_to_html):
    reg = registry(src)
    items, toc = [], []
    for f in cards():
        text = f.read_text(encoding="utf-8")
        title, rest = (text.split("\n", 1) + [""])[:2]
        title = title.lstrip("#").strip().replace("`", "")
        retired = title.upper().startswith("RETIRED")
        toc.append(f'<li><a href="#{f.stem}">{html.escape(title)}</a></li>')
        items.append(f'<section class="mc-card{" mc-retired" if retired else ""}" id="{f.stem}"><h2>{html.escape(title)}</h2>'
                     + score_box(reg.get(f.stem)) + md_to_html(rest) + "</section>")
    figs = "".join(f'<figure><a href="figures/{p}"><img src="figures/{p}" alt="{html.escape(t)}" loading="lazy"></a>'
                   f"<figcaption><b>{html.escape(t)}.</b> {html.escape(c)}</figcaption></figure>"
                   for p, t, c in FIGURES if (ROOT / "docs" / "figures" / p).is_file())
    return ("<h1>Models and analysis</h1><p>Every model behind the dashboard, with what it does, the data it uses, how it was "
            "validated and where it falls short. The box under each title is read from this build's model registry, so it shows "
            "the same held-out score as the dashboard's Data tab. A model that does not beat its baseline is never shown as a result.</p>"
            '<p>Jump to: <a href="#figures">analysis figures</a> · <a href="walkthrough.html">the analysis walkthrough</a> '
            "(the notebook, step by step).</p>"
            f'<ol class="mc-toc">{"".join(toc)}</ol>'
            f'<section id="figures"><h2>Analysis figures</h2><div class="mc-figs">{figs}</div></section>'
            + "".join(items))
