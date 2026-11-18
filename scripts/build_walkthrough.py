"""Write notebooks/walkthrough.ipynb from scratch (unexecuted): the walkthrough's text and code live here.

    python scripts/build_walkthrough.py    # rewrite the notebook's cells
    python scripts/render_notebook.py      # then execute it, render notebooks/walkthrough.html, refresh the figures

Edit the walkthrough here, not in the .ipynb: the notebook is regenerated from this file.
"""
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
cells = []
md = lambda s: cells.append(nbf.v4.new_markdown_cell(s.strip()))
code = lambda s: cells.append(nbf.v4.new_code_cell(s.strip()))

md("""
# GMI Savings Tracker: a walkthrough of the evidence

**What this is.** Maryland's Government Modernization Initiative (GMI) reported savings and set a yearly savings target. This page checks those reports against the State's own payment records. It shows what the data supports, what it does not, and where to look next. It is also a worked example of how any government or school system could check its own savings claims. You do not need to read code to follow it.

**How to read it.**
- For a one-page path from the data to the decision, open the dashboard's *Executive walkthrough* tab. This page is the detailed evidence behind it.
- Start with *At a glance* and the key findings below; each section after them gives the evidence for one finding.
- Every number in the text is computed from the published tables in `site_data/` (the same files as the dashboard and the data release), so the text cannot drift from the data. The code for each step is folded under *Show the code*.
- Three kinds of figure are kept apart throughout: **reported** savings (GMI's own figures), what is **observed in payment data** (evidence, not verification), and **leads** (places worth a look, not savings).
- Fiscal years run July 1 to June 30 (FY2026 is July 2025 to June 2026). Budget years are plans, not outcomes.
- Terms such as *calibrated range* and *backtest* are explained in the [glossary](#Glossary).

""")

code("""
import sys, subprocess, platform
from pathlib import Path
root = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "pyproject.toml").is_file())
sys.path.insert(0, str(root))
import yaml
import matplotlib
import pandas as pd
from IPython.display import HTML, Markdown, display
from src import published as P
from src.pipeline import overview_figures as V
cfg = yaml.safe_load((root / "config" / "assumptions.yaml").read_text())
info = P.run_info()
money = V.money
pct = lambda x: f"{x:.0%}"
""")

md("""
## At a glance
""")
code("""
st0 = P.load("d_savings_status")
wf0 = st0[st0.reported.notna()]
seen0, not0, none0 = wf0[wf0.status == "Seen"], wf0[wf0.status == "Not seen yet"], st0[st0.reported.isna()]
pl0 = P.load("d_plan50")
tgt0 = cfg["recommendations"]["target_saving"]
cov0 = V.coverage_summary().set_index(["scope", "calibrated"])
raw0 = cov0.loc[("in_sample", 0)]
cl0 = P.load("d_reported_claims")
jan_saved0 = cl0[(cl0.source_id == "JCR_2026_01") & cl0.basis.str.contains("Saved in FY2026")].amount_low.sum()
page0 = cl0[cl0.claim_id == "GOVPAGE_2026_06-G00"].amount_low.iloc[0]
ex = info["export"]
asof = f"{ex[:4]}-{ex[4:6]}-{ex[6:8]}"
portal = P.load("sources").portal_updated.max()
display(Markdown(f\"\"\"
**Data as of {asof}** (the six portal datasets were last updated on or before {portal}). Pipeline run {info['run_id']}; {info['checks']} automated checks, {info['passed']} passed.

**The bottom line.**
- Of {len(wf0)} reported savings items with a dollar figure, **{len(seen0)} show up in the State's payments** and **{len(not0)} do not yet**. Payments falling is evidence, not proof.
- The plan to reach the {money(tgt0)} target adds up to **{money(pl0.cumulative.iloc[-1])}**, but only **{money(pl0.saving.iloc[0])}** of that uses GMI's own reported rates. The rest rests on assumed rates that no recorded outcome has tested.
- **GMI reports two totals.** Its January 2026 report says {money(jan_saved0)} was saved in FY2026; its June 2026 page says it has implemented actions to save {money(page0)}. They count different things, and the tracker has verified neither (section 4).
- The published forecast range was meant to hold 80% of outcomes but held **{raw0.coverage:.0%}**. A recalibrated range does better on years it had not seen (section 5).

**What this evidence could help a budget office, audit team or school-system finance office do.**
1. Ask for the dollar basis behind the {len(none0)} reported items that have no dollar figure.
2. Treat the leads as a review list with a named owner, and record each outcome, so that a real hit rate can be measured later.
3. Publish a checked forecast range beside every budget forecast.
4. Repeat the reported-against-payments check every year, so claims are tested as they are made.
\"\"\"))
""")

md("## Key findings")
code("""
chk = P.load("run_checks")
s = P.load("f_scope")
base = s[s.scope == "Controllable purchases"].groupby(["fiscal_year", "stage"], as_index=False).budget.sum()
act, plan = base[base.stage == "Actual"], base[base.stage != "Actual"]
st = P.load("d_savings_status")
withfig = st[st.reported.notna()]
seen = withfig[withfig.status == "Seen"]
notseen = withfig[withfig.status == "Not seen yet"]
nofig = st[st.reported.isna()]
from src.models import forecast_published as FP
cov = V.coverage_summary().set_index(["scope", "calibrated"])
raw, cal = cov.loc[("in_sample", 0)], cov.loc[("out_of_sample", 1)]
opps = P.load("d_opps")
pl = P.load("d_plan50")
target = cfg["recommendations"]["target_saving"]
display(Markdown(f\"\"\"
1. **The part of the budget that savings work can reach was {money(act.budget.iloc[-1])} in FY{int(act.fiscal_year.iloc[-1])}.** This is "controllable purchases": spending on goods and services that buying decisions can change. FY{int(act.fiscal_year.iloc[-1])} is the last year with actual spending. The FY{int(plan.fiscal_year.iloc[-1])} budget plans {money(plan.budget.iloc[-1])}, but a plan is not a result. [Section 3](#3.-The-spending-base)
2. **Of {len(withfig)} reported savings with a dollar figure, {len(seen)} show up in State payments and {len(notseen)} do not yet.** The {len(seen)} that show up add up to {money(seen.reported.sum())} as reported; the {len(notseen)} that do not add up to {money(notseen.reported.sum())}. {len(nofig)} more items have no dollar figure, so the data can only say whether payments fell. Payments falling is evidence, not proof. GMI's June 2026 page gives a larger total ({money(page0)}) that counts differently; see [what GMI's public page says now](#What-GMI's-public-page-says-now). [Section 4](#4.-Reported-savings-against-the-State's-own-payments)
3. **The first forecast range was too narrow.** It was meant to hold 80% of outcomes but held {int(raw.hits)} of {int(raw.n)} past results ({raw.coverage:.0%}). A wider range, tested on years it had not seen, held {int(cal.hits)} of {int(cal.n)} ({cal.coverage:.0%}; the 95% interval is {cal.cov_lo:.0%} to {cal.cov_hi:.0%}). [Section 5](#5.-Forecasts,-and-how-far-to-trust-their-ranges)
4. **Four screens flag {len(opps)} places to look.** If the screening rates assumed here hold, they point to {money(opps.low.sum())} to {money(opps.high.sum())} a year in possible savings. These are leads, not savings. The ranges overlap, so they must not be added. [Section 6](#6.-Opportunities:-leads,-not-savings)
5. **A {len(pl)}-step plan reaches {money(pl.cumulative.iloc[-1])} against the {money(target)} target** (range {money(pl.low.sum())} to {money(pl.high.sum())}). Only {money(pl.saving.iloc[0])} of it uses GMI's own reported rates. The rest uses rates assumed here, which no recorded result has tested. [Section 8](#8.-The-path-to-the-target)
6. **All {info['checks']} automated data checks ran: {info['passed']} passed, {info['warnings']} warned and {info['failed']} failed.**{" The warning is the forecast range in finding 3." if info['warnings'] else ""} [Sections 1 and 2](#1.-Where-the-data-came-from)
\"\"\"))
""")

md("""
## 1. Where the data came from
Six datasets from the [Maryland Open Data Portal](https://opendata.maryland.gov/). Each download is compared with the portal's own row count; a mismatch stops the build.
""")
code("""
src = P.load("sources")
t = src.assign(link=[f'<a href="https://opendata.maryland.gov/d/{i}">{i}</a>' for i in src.dataset_id],
               ok=src.reconciled.map({1: "Yes", 0: "No"}))
t = t[["title", "link", "years", "rows_portal", "rows_downloaded", "ok", "portal_updated"]]
t.columns = ["Dataset", "Portal ID", "Years", "Rows on portal", "Rows downloaded", "Counts match", "Portal updated"]
display(V.table(t, f"The {len(src)} source datasets (export {info['export']})", ints=["Rows on portal", "Rows downloaded"]))
""")

md("""
## 2. The checks
Each build runs automated checks on every layer of the data. A build that fails a *stop* check keeps the last good database and publishes nothing, so a broken download cannot reach this page.
""")
code("""
V.show("checks", "Bars count checks by pipeline stage: raw downloads, reference tables, the cleaned core tables and the published tables.")
bad = chk[chk.status != "pass"][["stage", "check", "status", "detail"]].assign(stage=lambda d: d.stage.map(V.STAGE).fillna(d.stage))
bad.columns = ["Stage", "Check", "Status", "Detail"]
display(V.table(bad, "Checks that did not pass"))
""")

md("""
## 3. The spending base
Controllable purchases are the part of operating spending the savings work can act on: goods and services bought from vendors, not salaries, grants or debt service. Hatched bars are budgets (plans), not spending.
""")
code("""
V.show("spending_base", f"Actual spending to FY{int(act.fiscal_year.iloc[-1])}; FY{int(plan.fiscal_year.min())} onward are budgets. Nominal dollars, not adjusted for inflation.")
""")

md("""
## 4. Reported savings against the State's own payments
GMI reported savings items. For each, the tracker sums payments to the vendors that sell the thing being cut and compares the year before with the year after.

**How savings are counted here.** The tracker measures *payments*, meaning money that actually went out. It cannot see *cost avoidance* (a cost that would have grown but did not) or savings measured against a plan or appropriation; those need the agency's own baseline. The year-before against year-after comparison is a simple baseline: price changes, volume changes and one-time items can move payments for other reasons.
""")
code("""
ds = P.load("d_savings")
shared = ds[ds.check_id.notna() & (ds.check_id != ds.saving_id)]
parts = ds[ds.type.str.startswith("Part of")]
groups = "; ".join(f"{c} also covers {', '.join(g.saving_id)}" for c, g in shared.groupby("check_id"))
display(Markdown(f\"\"\"
**Items that overlap.** GMI's report says {len(parts)} items ({', '.join(parts.saving_id)}) are parts of one $18M figure, so they carry no dollar figure of their own. {len(shared)} more items act on spending that another item also acts on, so the tracker checks them together against one set of payments ({groups}) and adds their reported amounts in that one row. That treats them as separate savings on the same spending. The tracker cannot see how GMI estimated each amount, so it cannot confirm that. It also has no test for whether the payee-name patterns of two different checks match the same payments. Where this page adds up dollars, they are amounts GMI reported, and the sum is not a verified total.
\"\"\"))
""")
md("How each status is assigned:")
code("""
sc = cfg["savings"]
display(Markdown(f\"\"\"
| Status | When GMI gave a dollar figure |
|---|---|
| Seen | payments fell by at least {sc['seen_share']:.0%} of the reported saving, FY{sc['before_fy']} to FY{sc['after_fy']} |
| Partly seen | payments fell, but by less than that |
| Not seen yet | payments did not fall |

Where GMI gave no figure the status is only *Payments fell* or *Payments did not fall*; *Projected only* items are not due yet. **"Seen" means the payments move the way the claim implies; it is not an audit or a verification.** Payments can fall for other reasons, and a real saving measured against a plan, or bought on purchasing cards, may not show in payments at all (US GAO reports on claimed savings make the same distinction between reported and supported savings).
\"\"\"))
""")
code("""
items = st.assign(change=st["after"] - st["before"])[["check_id", "item", "reported", "before", "after", "change", "status"]]
items.columns = ["ID", "Reported item", "Reported saving", f"Payments FY{sc['before_fy']}", f"Payments FY{sc['after_fy']}", "Change", "Status"]
display(V.table(items, "Each reported savings item and the matching payments", money=list(items.columns[2:5]), signed=["Change"]))
V.show("savings_status", "Each bar counts reported savings items by what the payments show. Solid bars are items with a reported dollar figure.")
""")

md("""
### What GMI's public page says now
GMI's savings are reported in more than one place, and the places count different things. The tracker keeps every figure with its source and date (the published table `d_reported_claims`) and never mixes them. Two sources matter here: the January 26, 2026 report to the legislature, which this page uses for item-level checks because each item carries a page number and a quote, and the Governor's Government Modernization Initiative page, which states its status as of June 2026.
""")
code("""
cl, cmp = V.claims_view()
srcs = cl.drop_duplicates("source_id")[["source_title", "as_of", "retrieved", "url"]].copy()
srcs["link"] = [f'<a href="{u}">{u}</a>' for u in srcs.url]
srcs = srcs[["source_title", "as_of", "retrieved", "link"]]
srcs.columns = ["Source", "Status as of", "Retrieved", "Link"]
display(V.table(srcs, "The sources of reported savings figures, and their dates"))
jan_saved = cl[(cl.source_id == "JCR_2026_01") & cl.basis.str.contains("Saved in FY2026")].amount_low.sum()
page_total = cl[cl.claim_id == "GOVPAGE_2026_06-G00"].amount_low.iloc[0]
head = pd.DataFrame([
    ("January 26, 2026 report", "Saved in FY2026 (the items it describes as saved)", jan_saved, "The report's own FY2026 total; yearly savings under way or projected are not added."),
    ("Governor's page (as of June 2026)", "Implemented actions to save", page_total, "The page broadened the goal to a variety of fund sources and does not split one-time from yearly savings."),
], columns=["Source", "What it counts", "Amount", "Note"])
display(V.table(head, "The two headline totals", money=["Amount"]))
display(Markdown("The totals are different counts, not rival measurements of one thing, and **the tracker has verified neither**: payments can speak to only some items (section 4). "
                 "This page therefore quotes both, each with its source, and does not choose between them."))
""")
code("""
def amt(lo, hi):
    if pd.isna(lo):
        return "no figure"
    return money(lo) if lo == hi else f"{money(lo)} to {money(hi)}"
cmp2 = cmp.assign(
    january=[amt(a, b) for a, b in zip(cmp.january_low, cmp.january_high)],
    page=[money(x) for x in cmp.page_amount],
    gap=[("no January figure" if pd.isna(lo) else ("within 6%" if abs(p - (lo + hi) / 2) < 0.06 * p else ("page higher" if p > (lo + hi) / 2 else "page lower"))) for lo, hi, p in zip(cmp.january_low, cmp.january_high, cmp.page_amount)],
)
cmp2["match"] = cmp2.mapping.map(lambda m: "likely the same item" if "likely" in m else "same item")
view = cmp2[["saving_id", "item", "january", "page", "gap", "match"]]
view.columns = ["Item", "What", "January 2026 report", "June 2026 page", "Compared", "How matched"]
display(V.table(view, "Items that both sources describe, side by side"))
lev = cl[(cl.source_id == "GOVPAGE_2026_06") & cl.saving_id.isin(["S02", "S03", "S04", "S05"])]
display(Markdown(f"**Where they differ.** For the four contract types behind the report's $18M (items S02 to S05), the report gives no split; the page gives lines that add to {money(lev.amount_low.sum())} "
                 f"({', '.join(sorted(set(lev.saving_id)))}), and a further {money(cl[cl.claim_id == 'GOVPAGE_2026_06-G11'].amount_low.iloc[0])} for IT services contracts that matches no January item. "
                 f"Neither document says how its lines relate to the other. Differences of a few percent look like rounding; larger ones (mobile phone rates, the fleet maintenance tool) may be timing or scope. "
                 f"**Matching a page line to a January item is this tracker's reading.** Where the table says *likely*, the page does not name the item. The page also lists lines with no January item at all "
                 f"({len(cl[(cl.source_id == 'GOVPAGE_2026_06') & (cl.saving_id == '') & (cl.claim_id != 'GOVPAGE_2026_06-G00')])} of them, including about {money(cl[cl.claim_id == 'GOVPAGE_2026_06-G17'].amount_low.iloc[0])} projected for the Department of Information Technology)."))
""")

md("""
## 5. Forecasts, and how far to trust their ranges
Each focus area gets the simplest model that wins a rolling backtest (forecasting past years from earlier data). The published range is the 10th to 90th percentile of bootstrap paths, so it is meant to hold 80% of outcomes. The backtest shows it holds fewer, so a **calibrated range** is published beside it: the raw range widened around the median by a factor fitted on past misses (conformal calibration). The raw columns are unchanged.

The next step rebuilds the forecast from three published input tables using the pipeline's own code, and stops if the result differs from the published forecast in any row. This is the one place the walkthrough runs model code; it refits nothing.
""")
code("""
tables = V.rebuilt()
diffs = FP.differences(tables)
assert not diffs, diffs
print(f"Rebuilt forecast equals the published forecast: {len(tables['f_forecast'])} rows, 0 differences.")
m = P.load("d_forecast_model")[["area", "method", "growth", "backtest_mape", "baseline_fy2025"]]
m["growth"] = m.growth.where(m.method == "Log-linear trend")  # the naive model carries the last actual forward: no growth
m.columns = ["Focus area", "Model chosen", "Yearly growth (trend model only)", "Backtest error (MAPE)", "FY2025 actual"]
display(V.table(m, "The model chosen for each focus area", pct=["Yearly growth (trend model only)", "Backtest error (MAPE)"],
                money=["FY2025 actual"], na=""))
""")
code("""
c = V.coverage_summary().copy()
c["scope"] = c.scope.map({"in_sample": "All past outcomes (in sample)", "out_of_sample": "Each outcome year held out",
                          "expanding_origin": "Only outcomes known at the time"})
c["calibrated"] = c.calibrated.map({0: "Raw", 1: "Calibrated"})
c = c[["scope", "calibrated", "n", "hits", "coverage", "cov_lo", "cov_hi", "factor"]]
c.columns = ["Test design", "Range", "Forecasts", "Outcomes inside", "Coverage", "95% interval low", "95% interval high", "Widening factor"]
display(V.table(c, "How often past outcomes fell inside the range (target: 80%)", pct=["Coverage", "95% interval low", "95% interval high"], dec=["Widening factor"]))
e = cov.loc[("expanding_origin", 1)]
display(Markdown(f"The raw range held {int(raw.hits)} of {int(raw.n)} past outcomes ({raw.coverage:.1%}) against a target of 80%. "
                 f"Calibrated and tested with each outcome year held out, it held {int(cal.hits)} of {int(cal.n)} ({cal.coverage:.1%}; 95% interval "
                 f"{cal.cov_lo:.0%} to {cal.cov_hi:.0%}). Using only outcomes known at each forecast date, it held {int(e.hits)} of {int(e.n)} "
                 f"({e.coverage:.1%}) with a mean widening factor of {e.factor:.1f}: too wide, because early dates had few misses to learn from."))
V.show("forecast_fan", "Black: actual spending. Dashed: median forecast. Dark band: raw 80% range; light band: calibrated range. Orange circles: the State's budget, a plan rather than an outcome.")
""")
code("""
rc = V.rebuilt()["d_range_coverage"]
rc = rc[(rc.source == "bootstrap") & (rc.horizon == 0) & (rc.scope == "out_of_sample") & (rc.calibrated == 1) & (rc.area != "All areas")]
worst = rc.sort_values("coverage").iloc[0]
V.show("range_coverage", "Dots: share of past outcomes inside the range; bars: 95% Wilson interval. The dotted line marks the 80% target.")
display(Markdown(f\"\"\"**Reading it.** Tested on held-out years, the calibrated range covers about what it claims, and its 95% interval includes 80%. It is one pooled correction, so areas differ: {worst.area} stays under-covered ({int(worst.hits)} of {int(worst.n)}) because its model misses by more than a wider range can absorb. With {int(cal.n)} forecasts across {rc.area.nunique()} areas that share economic shocks, treat the calibrated range as a better-supported indication, not a guarantee.\"\"\"))
""")
md("""
**Would a machine-learning model give better ranges?** A LightGBM quantile model (a gradient-boosted model trained across all areas) was backtested as a challenger on many agency-level spending series (so its figures are not comparable with the area table above). On that test its 80% ranges come closer to 80% than the naive model's raw ranges, but still fall short, so they are not simply swapped in: the tracker adopts LightGBM per agency–code series only where it beats naive in that series' own backtest, and the registry and the Forecasts tab show the adopted count.
""")
code("""
cb0 = P.load("d_challenger_backtest")
cb = cb0.pivot(index="origin_fy", columns="model", values="coverage_80").reset_index()
cb = cb.rename(columns={"origin_fy": "Forecast made in FY"})
cb.insert(1, "Series scored", cb0.groupby("origin_fy").series_scored.max().to_numpy())
display(V.table(cb, "Share of outcomes inside the 80% range, by model and forecast year", ints=["Series scored"], pct=[c for c in cb.columns[2:]]))
""")

md("""
## 6. Opportunities: leads, not savings
Four detectors flag spending worth a closer look:
- **Growth above trend**: an agency's spending on a budget code grew much faster than the State's spending on the same code.
- **Peer gap**: an agency spends more per budgeted position on a code than most comparable agencies.
- **Leverage**: one vendor is paid separately by many agencies, a candidate for a single statewide contract.
- **Tail spend**: payments in a focus area to vendors outside its largest suppliers.

The dollar ranges apply assumed screening percentages (set in `config/assumptions.yaml`) to the flagged spending. They are not forecasts, and detectors can look at the same spending from different angles, so the ranges must not be added up.
""")
code("""
V.show("opportunities", "Each bar runs from the low to the high screening estimate for one detector.")
top = opps.sort_values("high", ascending=False).head(10)[["opp_id", "detector", "agency", "spending_code", "evidence", "low", "high"]]
top.columns = ["ID", "Detector", "Agency", "Spending", "Why it was flagged", "Screening low", "Screening high"]
display(HTML("<details><summary>The ten leads with the largest screening ranges</summary>"
             + V.table(top, "The ten leads with the largest screening ranges", money=["Screening low", "Screening high"], na="").to_html() + "</details>"))
""")

md("""
## 7. Every program, screened the same way
In November 2026 the press reported child care overpayments at the State Department of Education that the tracker had not found, and could not have: they are provider-level findings from internal audits, and the open data has one total per payee and year. But the program stood out in the budget data. This section applies that reading to every program of every agency: how many times it grew, its largest swing from one year to the next, and the audit findings on file beside it. It is an order in which to ask questions, not a finding.
""")
code("""
ps = V.program_screen_table()
both = ps[ps.signals == 2]
print(f"{len(ps)} programs screened across {ps.agency_code.nunique()} agencies; {len(both)} crossed both thresholds, {int((ps.signals == 1).sum())} crossed one.")
cc = ps[ps.program_name.str.contains("Child Care Assistance")].iloc[0]
print(f"Child care grants: {V.money(cc.spend_first)} in FY{cc.first_fy} to {V.money(cc.spend_last)} in FY{cc.last_fy} ({cc.growth_multiple:.1f}x), "
      f"largest swing {cc.largest_swing:+.0%} in FY{cc.swing_fy}; rank {list(both.index).index(cc.name) + 1} of {len(both)} by size among programs with both signals.")
top = both.head(12)[["agency_code", "program_name", "spend_last", "growth_multiple", "largest_swing", "ola_findings", "ola_repeat_findings", "reported_amount", "recoupment_status"]]
top.columns = ["Agency", "Program", "Spending, last year", "Growth multiple", "Largest swing", "OLA findings", "OLA repeat findings", "Reported amount", "Recoupment status"]
display(V.table(top, "The twelve largest programs that crossed both thresholds", money=["Spending, last year", "Reported amount"], dec=["Growth multiple"], pct=["Largest swing"], ints=["OLA findings", "OLA repeat findings"]))
V.program_screen();
""")
code("""
rep = V.PS.reported_findings()
shown = rep[["finding_id", "agency_code", "program_name", "finding", "amount", "period", "recoupment_status", "confirmation"]].copy()
shown["amount"] = pd.to_numeric(shown.amount, errors="coerce")
shown.columns = ["Finding", "Agency", "Program", "What was reported", "Amount", "Period", "Recoupment status", "Confirmation"]
display(V.table(shown, "Reported findings tied to a budget program (from the audit register)", money=["Amount"]))
V.childcare_program();
""")
md("""
**Reading it.** Many of the flagged programs have ordinary explanations: federal relief money in FY2021 and FY2022, reserve accounts that are filled and emptied by design, a new law phasing in. The screen does not know which. Reported findings come from the audit register (`reference/audit_findings.csv`) and are tied to a budget program only where the source names one; two are, both for the child care program, taken from press reports because the audit documents are not public.
""")

md("## 8. The path to the target")
code("""
pl2 = pl.assign(kind=pl.step.map(lambda s: "1. GMI's reported rates on forecast spending" if s == 1 else None))
pl2.loc[pl.basis.str.contains("paid by"), "kind"] = "2. Statewide contracts with vendors many agencies use (assumed 2-5%)"
pl2.loc[pl.basis.str.contains("of forecast FY"), "kind"] = "3. Assumed 1% of forecast spending in remaining areas"
g = pl2.groupby("kind", as_index=False).agg(steps=("step", "size"), saving=("saving", "sum"), low=("low", "sum"), high=("high", "sum"))
g.columns = ["Kind of step", "Steps", "Central", "Low", "High"]
display(Markdown(f"The target is **{money(target)} a year**. The plan table stacks GMI's own reported rates first, then the largest leads. "
                 f"Each step names its basis; steps resting on assumed rates say so."))
display(V.table(g, f"The {len(pl)}-step path to {money(target)}, by kind of step", money=["Central", "Low", "High"]))
full = pl[["step", "action", "basis", "saving", "cumulative"]]
full.columns = ["Step", "Action", "Basis", "Saving", "Running total"]
display(HTML(f"<details><summary>All {len(pl)} steps</summary>" + V.table(full, "Every step of the path", money=["Saving", "Running total"]).to_html() + "</details>"))
display(Markdown(f"After {len(pl)} steps the central estimate is {money(pl.cumulative.iloc[-1])}, of which {money(pl.saving.iloc[0])} "
                 f"({pl.saving.iloc[0] / pl.cumulative.iloc[-1]:.0%}) comes from GMI's own reported rates; the rest depends on assumed rates "
                 f"that no recorded outcome has yet tested."))
""")

md("""
## Using this approach elsewhere
The same method needs three things: a public source with row counts to reconcile against, a list of claimed savings, and payment or spending records that name the vendor. The steps are the ones used here: download and reconcile, run stop checks, publish tables, and write every number in the report from those tables. A city, county or school system with those inputs could run the same checks on its own claims. To discuss a pilot, contact Sierra Napier at s.napier430@gmail.com. This is an independent prototype, not an official State product.
""")

md("## 9. Limits")
code("""
yrs = act.fiscal_year.nunique()
mase = P.load("d_challenger_backtest")
display(Markdown(f\"\"\"
- **Short history.** {yrs} years of actual spending per area. Spending series this short are hard to forecast: on the challenger backtest of agency-level series, the mean scaled error (MASE) of both models ranges from {mase.mean_mase.min():.1f} to {mase.mean_mase.max():.1f}, where values above 1 mean larger errors than a naive one-year-ahead forecast made in the training years.
- **Small calibration sample.** The ranges are calibrated on {int(cal.n)} pooled forecasts; coverage by area is uneven (section 5).
- **No hit rate for leads.** No review outcome has been recorded for any lead, so no claim is made about how many become savings.
- **Payments are a partial view.** Purchasing-card spending and savings measured against plans or appropriations do not appear in payments (section 4).
- **Indicative bands.** The LightGBM corridor rests on three backtest origins and the revenue band on few years of history: both are indicative (see the model cards on the site's models page).
\"\"\"))
""")

md("""
## 10. Reproduce and provenance
Everything above can be rerun from the repository with the locked environment:

```bash
uv sync --frozen --extra dev --extra notebook      # the locked environment
python scripts/build_walkthrough.py                # write this walkthrough's cells
python scripts/render_notebook.py                  # execute it and render this page
python -m src.models.forecast_published --check    # rebuild the forecast from the published tables
docker compose run --rm test                       # the test suite in a container
```
""")
code("""
snap = __import__("json").loads((root / "site_data" / "snapshot.json").read_text())
try:
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=root, capture_output=True, text=True).stdout.strip() or "unknown"
except OSError:
    sha = "unknown"
prov = pd.DataFrame([
    ("Pipeline run", info["run_id"]), ("Run started (UTC)", info["started_utc"]), ("Data export", info["export"]),
    ("Snapshot refreshed (UTC)", snap.get("refreshed_utc", "")), ("Published tables", str(info["tables"])), ("Code commit", sha),
    ("Python", platform.python_version()), ("pandas", pd.__version__), ("matplotlib", matplotlib.__version__)], columns=["Item", "Value"])
display(V.table(prov, "Provenance of this page"))
""")

md("""
## Glossary
- **Backtest (rolling origin).** Pretend it is an earlier year, forecast from the data known then, and compare with what happened; repeat for several starting years.
- **Bootstrap range.** Simulate many future paths by resampling past year-to-year changes; the 10th and 90th percentiles of those paths form the raw 80% range.
- **Calibrated range.** The raw range widened by a factor chosen so that, on past forecasts, about 80% of outcomes fall inside (split conformal calibration).
- **Coverage.** The share of past outcomes that fell inside a range. A well-calibrated 80% range has coverage near 80%.
- **Controllable purchases.** Operating spending on goods and services from vendors, which procurement and savings work can influence.
- **Lead.** Spending a detector flags for review. A lead is not a saving.
- **MAPE / MASE.** Mean absolute percentage error, and mean absolute scaled error (error relative to a naive forecast; above 1 is worse than naive).
- **Naive model.** Forecasts that next year equals the last actual year.
- **Wilson interval.** A 95% interval for a proportion that behaves well with small counts, used here for coverage.

## References and guidance followed
Methods
- Hyndman, R. J., & Athanasopoulos, G. (2021). *Forecasting: Principles and Practice* (3rd ed.). OTexts. [otexts.com/fpp3](https://otexts.com/fpp3/); prediction intervals and bootstrapping: [§5.5](https://otexts.com/fpp3/prediction-intervals.html).
- Angelopoulos, A. N., & Bates, S. (2021). A gentle introduction to conformal prediction and distribution-free uncertainty quantification. [arXiv:2107.07511](https://arxiv.org/abs/2107.07511).
- Gneiting, T., & Raftery, A. E. (2007). Strictly proper scoring rules, prediction, and estimation. *JASA*, 102(477), 359-378. [doi:10.1198/016214506000001437](https://doi.org/10.1198/016214506000001437).

Communicating uncertainty and evidence
- van der Bles, A. M., et al. (2019). Communicating uncertainty about facts, numbers and science. *Royal Society Open Science*, 6(5), 181870. [doi:10.1098/rsos.181870](https://doi.org/10.1098/rsos.181870).
- Wilke, C. O. (2019). *Fundamentals of Data Visualization*, ch. 16, Visualizing uncertainty. [clauswilke.com/dataviz](https://clauswilke.com/dataviz/visualizing-uncertainty.html).
- UK Government Analysis Function. [Communicating quality, uncertainty and change](https://analysisfunction.civilservice.gov.uk/policy-store/communicating-quality-uncertainty-and-change/); [Writing about statistics](https://analysisfunction.civilservice.gov.uk/policy-store/writing-about-statistics/); [Data visualisation: charts](https://analysisfunction.civilservice.gov.uk/policy-store/data-visualisation-charts/).
- US GAO (2026). [GAO-26-108615](https://files.gao.gov/reports/GAO-26-108615/index.html), and (2013) [GAO-14-12](https://www.gao.gov/products/gao-14-12), on separating reported from supported savings.

Notebook and accessibility practice
- Rule, A., et al. (2019). Ten simple rules for writing and sharing computational analyses in Jupyter Notebooks. *PLOS Computational Biology*, 15(7), e1007007. [doi:10.1371/journal.pcbi.1007007](https://doi.org/10.1371/journal.pcbi.1007007).
- W3C WAI. [Complex images tutorial](https://www.w3.org/WAI/tutorials/images/complex/) (each chart here has alt text, a caption that states the finding and its data table) and [WCAG 2.2](https://www.w3.org/TR/WCAG22/).
- U.S. Web Design System. [Data visualizations](https://designsystem.digital.gov/components/data-visualizations/).

**Cite this work:** Napier, S. *GMI Savings Tracker v3* (software and data). [github.com/EVO3-Ecosystem/gmi-savings-tracker-v3](https://github.com/EVO3-Ecosystem/gmi-savings-tracker-v3); see `CITATION.cff`.
""")

nb = nbf.v4.new_notebook(cells=cells)
nb.metadata = {"title": "GMI Savings Tracker: a walkthrough of the evidence",
               "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
               "language_info": {"name": "python", "pygments_lexer": "ipython3"}}
nbf.write(nb, ROOT / "notebooks" / "walkthrough.ipynb")
print("wrote", len(cells), "cells")
