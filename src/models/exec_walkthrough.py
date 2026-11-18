"""The executive walkthrough: eight plain-language steps from the data to the decision, plus the asks, as one table.

    python -m src.models.exec_walkthrough [--src site_data] [--out FILE]

The dashboard's 'Executive walkthrough' tab (legacy/gst/page/index.html) draws this table (`exec_walkthrough.csv`, written
beside the other data files by src/pipeline/site.py). Every number in the text is computed here from the metric registry
(config/metrics.yml, src/models/metrics.py) and the published tables, never typed, so the story cannot drift from the data.
The text is the only thing written by hand: short sentences (about US grade 8), one finding per step, a caveat on each.

Columns: kind (step | ask), step, title, finding, evidence, tables (the published tables the step draws on), metric_ids
(registry ids used in the finding), tab_link and tab_label (the dashboard tab that holds the detail), caveat, owner, as_of, version.

What it is: a guide to the evidence. What it is not: a finding of savings or of error. Owners of the asks are not named here:
they are for GMI and the Governor's office to name.
"""
import argparse
import re
from datetime import date
from pathlib import Path

import pandas as pd

from . import metrics as metric_registry

ROOT = Path(__file__).resolve().parents[2]
COLUMNS = ["kind", "step", "title", "finding", "evidence", "tables", "metric_ids", "tab_link", "tab_label", "caveat", "owner", "as_of", "version"]
TABS = {"over": "Overview", "areas": "Focus areas", "track": "Savings tracker", "opp": "Opportunities", "calc": "Calculator",
        "fcast": "Forecasts & results", "vend": "Vendors", "agency": "Agencies", "budget": "Budget", "data": "Data & pipeline"}
OWNER = "To be named by GMI and the Governor's office"


def usd(x):
    """Compact dollars: $29M, $52.6M, $4.8B (one decimal at most, no trailing .0)."""
    x = float(x)
    if abs(x) >= 1e9:
        s, u = x / 1e9, "B"
    elif abs(x) >= 1e6:
        s, u = x / 1e6, "M"
    else:
        s, u = x / 1e3, "K"
    return "$" + (f"{s:.1f}".rstrip("0").rstrip(".")) + u


def pct(x, nd=1):
    return f"{x * 100:.{nd}f}".rstrip("0").rstrip(".") + "%"


def count(n):
    return f"{int(n):,}"


def millions(n):
    return f"{n / 1e6:.2f}M"


def _read(src, name):
    return pd.read_csv(Path(src) / f"{name}.csv")


def _version():
    m = re.search(r'^version\s*=\s*"([^"]+)"', (ROOT / "pyproject.toml").read_text(), re.M)
    return m.group(1) if m else ""


def _as_of(src):
    runs = _read(src, "run_checks").run_id.astype(str)
    d = runs.iloc[0][:8]
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}"


def _long_date(iso):
    d = date.fromisoformat(iso)
    return d.strftime("%B ") + str(d.day) + d.strftime(", %Y")


def facts(src):
    """Every number the text uses, computed from the registry and the published tables. Returns (dict of values, dict of registry values)."""
    from src.mcp.store import Store
    reg = {m["id"]: m["value"] for m in metric_registry.evaluate(Store(export_dir=str(src), prefer="export").con, strict=False)}
    st = _read(src, "d_savings_status")
    st["change"] = st.after / st.before - 1
    fell = st[st.status.isin(["Payments fell", "Seen"])].sort_values("change")
    plan = _read(src, "d_plan50")
    cov = _read(src, "d_range_coverage")
    oos = cov[(cov.source == "bootstrap") & (cov.area == "All areas") & (cov.horizon == 0) & (cov.scope == "out_of_sample")]
    raw, cal = oos[oos.calibrated == 0].iloc[0], oos[oos.calibrated == 1].iloc[0]
    books = _read(src, "d_book_reconciliation")
    act = books[(books.stage == "Actual") & (books.kind == "reconcile")]
    site = _read(src, "d_site_reconciliation")
    sources = _read(src, "sources")
    from src.pipeline import doc_counts
    return {
        "areas_checked": int(len(st)), "areas_fell": int(len(fell)),
        "fell_top": [(r["item"], r["change"]) for _, r in fell.head(2).iterrows()],
        "carried": float(plan.iloc[0].saving),
        "cal_hits": int(cal.hits), "cal_n": int(cal.n), "cal_cov": cal.hits / cal.n, "cal_lo": float(cal.cov_lo), "cal_hi": float(cal.cov_hi),
        "raw_hits": int(raw.hits), "raw_n": int(raw.n), "raw_cov": raw.hits / raw.n,
        "book_years": int(act.fiscal_year.nunique()), "book_first": int(act.fiscal_year.min()), "book_last": int(act.fiscal_year.max()),
        "book_diff_max": float(act.difference_share.abs().max()), "book_exact_min": float(act.exact_share.min()),
        "site_n": int(len(site)), "site_equal": int((site.difference.abs() < 0.005).sum()),
        "datasets": int(len(sources)), "portal_updated": str(sources.portal_updated.max()),
        "marts": int(doc_counts.mart_count(ROOT)),
        "largest_reported": float(st.reported.max()),
    }, reg


def build(src=None):
    """The table: 8 step rows then 3 ask rows."""
    src = Path(src) if src else ROOT / "site_data"
    need = ("run_checks", "sources", "d_savings_status", "d_plan50", "d_range_coverage", "d_book_reconciliation", "d_site_reconciliation")
    if not all((src / f"{t}.csv").exists() for t in need):  # a partial export (a test, a trimmed build): no walkthrough, the tab says so
        return pd.DataFrame(columns=COLUMNS)
    f, r = facts(src)
    if any(v is None for v in r.values()):
        return pd.DataFrame(columns=COLUMNS)
    as_of, ver = _as_of(src), _version()
    ex1, ex2 = f["fell_top"]
    ex = lambda t: t[0].split(" (")[0].split(" at ")[0].lower()  # noqa: E731
    steps = [
        ("The question and the bottom line",
         f"Did the savings GMI reported show up in what Maryland paid? Payments to the vendors tied to GMI fell in {f['areas_fell']} of {f['areas_checked']} areas checked. "
         f"That is evidence, not proof. Neither reported total is verified.",
         "Source: the savings checks and the reported figures, each kept by source and date.",
         "d_savings_status;d_reported_claims", "reported_saved_fy2026_usd;reported_actions_june_2026_usd", "track",
         "Payments are cash paid. Agency records are needed to confirm any saving."),
        ("Where the data comes from",
         f"{f['datasets']} State open datasets, {millions(r['rows_checked_against_portal'])} rows in all, were downloaded from the State's data portal. "
         f"Every download matched the portal's own row count. The portal was last updated {_long_date(f['portal_updated'])}.",
         "Source: row counts saved with each download, compared with the portal.",
         "sources", "rows_checked_against_portal", "data",
         "The public payment data has no vendor number, so companies are matched by name and ZIP."),
        ("How the data is checked",
         f"{r['checks_passed']} of {r['checks_total']} stop checks pass. Nothing is published unless every check passes. "
         f"The data is loaded in layers and built into {f['marts']} tables that the dashboard reads.",
         "Source: the check results saved with every run.",
         "run_checks", "checks_passed;checks_total", "data",
         "Checks test the data's consistency. They do not test that the State's records are right."),
        ("Checked against the State's own documents",
         f"Every actual year from FY{f['book_first']} to FY{f['book_last']} matches the State's printed budget books. Statewide totals are within {pct(f['book_diff_max'], 3)}, "
         f"and {pct(f['book_exact_min'], 1)} or more of programs match to the dollar. {f['site_equal']} of {f['site_n']} yearly totals equal the State's Open Finance sites to the cent.",
         "Source: the budget books and the State's Open Finance websites, checked on the dates shown.",
         "d_book_reconciliation;d_site_reconciliation", "", "data",
         "The current year and next year are bridged and explained, not exact."),
        ("What GMI reported",
         f"GMI's January 26, 2026 report counts {usd(r['reported_saved_fy2026_usd'])} saved in FY2026. The Governor's page, as of June 2026, says actions to save {usd(r['reported_actions_june_2026_usd'])}. "
         f"They count different things and neither is verified here. Savings are kept in three kinds: reported, supported by payments, and assumed.",
         "Source: each reported figure with its source, date and quoted words.",
         "d_reported_claims", "reported_saved_fy2026_usd;reported_actions_june_2026_usd;gmi_reported_items", "track",
         "The page does not say whether its figure is one-time or yearly."),
        ("Did payments move?",
         f"Payments to the matching vendors fell in {f['areas_fell']} of {f['areas_checked']} areas, for example {ex(ex1)} ({pct(ex1[1], 0)}) and {ex(ex2)} ({pct(ex2[1], 0)}). "
         f"The other areas are newer or rose, and need agency records to confirm.",
         "Source: State payments to the matching vendors, FY2025 and FY2026.",
         "d_savings_status;f_savings_check", "", "track",
         "A drop in payments is evidence that a change is working. It does not measure the saving."),
        ("The path to $50M and the leads",
         f"Carrying GMI's reported rates forward gives about {usd(f['carried'])} a year. With labeled assumptions the path is {usd(r['path_total_usd'])} "
         f"(range {usd(r['path_low_usd'])} to {usd(r['path_high_usd'])}). The tracker also flags {r['opportunity_findings']} leads worth up to {usd(r['opportunity_high_usd'])} a year.",
         "Source: the savings path and the opportunity detectors.",
         "d_plan50;d_opps", "path_total_usd;path_low_usd;path_high_usd;opportunity_findings;opportunity_high_usd", "calc",
         "Leads overlap and are not savings. The path depends on assumptions you can change."),
        ("How sure we are, and the limits",
         f"A range meant to hold 8 in 10 outcomes held {f['raw_hits']} of {f['raw_n']} ({pct(f['raw_cov'])}) before calibration and {f['cal_hits']} of {f['cal_n']} ({pct(f['cal_cov'])}) after. "
         f"One {usd(r['source_issue_amount_usd'])} block in the published FY2022 payments is reported as a source issue, not a finding. This is not an audit.",
         "Source: forecast ranges tested on years they had not seen; the source-issue record.",
         "d_range_coverage;d_source_issues", "source_issue_amount_usd", "fcast",
         "Written for a prototype built from open data. It is not an audit under government auditing standards."),
    ]
    rows = []
    for i, (title, finding, evidence, tables, mids, tab, caveat) in enumerate(steps, 1):
        rows.append(["step", i, title, finding, evidence, tables, mids, tab, TABS[tab], caveat, "", as_of, ver])
    asks = [
        ("Name the seven renegotiated vendors",
         f"GMI's largest saving ({usd(f['largest_reported'])}) names contract types, not vendors. Naming them lets the State check it against payments.",
         "d_savings_status", "vend", "Vendors"),
        ("Share agency records for the newer savings",
         "Agency invoices or records would confirm the savings that payments cannot show yet.",
         "d_savings_status", "track", "Savings tracker"),
        ("Agree one savings ledger",
         "Agree what counts as a saving (cash saved or cost avoided), the baseline, and how to avoid counting the same saving twice.",
         "d_reported_claims", "track", "Savings tracker"),
    ]
    for title, finding, tables, tab, label in asks:
        rows.append(["ask", 1, title, finding, "", tables, "", tab, label, "", OWNER, as_of, ver])
    return pd.DataFrame(rows, columns=COLUMNS)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(ROOT / "site_data"))
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    df = build(a.src)
    if a.out:
        df.to_csv(a.out, index=False)
    else:
        for _, r in df.iterrows():
            print(f"[{r.kind} {r.step}] {r.title}\n    {r.finding}\n    caveat: {r.caveat}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
