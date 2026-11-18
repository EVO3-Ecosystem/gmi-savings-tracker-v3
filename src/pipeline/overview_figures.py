"""Figures drawn from the published tables only (site_data/), for the walkthrough notebook and the executive overview.

    python -m src.pipeline.overview_figures        # writes docs/figures/overview/*.png

Each function returns a matplotlib Figure; `main` saves them all. The forecast figures rebuild the forecast and its
range calibration from the published inputs (src/models/forecast_published.py), so nothing here needs the warehouse.
Chart conventions: bars start at zero, one y axis, units on the axis, budget years drawn differently from actuals,
ranges drawn as bands with full-colour edges and their meaning in the caption, colour-blind-safe pairs (blue / orange), marks at 3:1
contrast or more against the background (WCAG 1.4.11), no pie charts, no mathtext (a "$" is a dollar sign).
"""
from pathlib import Path

import matplotlib
import matplotlib.patches
import matplotlib.pyplot as plt
import numpy as np

from .. import published as P
from ..models import calibration as C
from ..models import forecast_published as FP
from ..models import program_screen as PS

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "figures" / "overview"
BLUE, ORANGE, GREEN, INK, MUTED, GRID, SURF = "#2a78d6", "#eb6834", "#148a60", "#0b0b0b", "#52514e", "#e6e5e0", "#fcfcfb"
STYLE = {"figure.facecolor": SURF, "axes.facecolor": SURF, "axes.edgecolor": GRID, "axes.labelcolor": MUTED, "xtick.color": MUTED,
         "ytick.color": MUTED, "axes.grid": True, "grid.color": GRID, "grid.linewidth": .8, "axes.axisbelow": True, "font.size": 10,
         "axes.titlesize": 10, "axes.titleweight": "bold", "axes.titlecolor": INK, "axes.spines.top": False, "axes.spines.right": False,
         "text.parse_math": False}  # "$45M to $148M" must not be read as mathtext
_cache = {}


def _trim(x, d):
    t = f"{x:,.{d}f}"
    return t.rstrip("0").rstrip(".") if "." in t else t


def money(v, _=None):
    """$4.1B, $148M, $45.4M, $739K: one decimal below $100M, so $11.5M is not shown as $12M."""
    if v < 0:
        return "-" + money(-v)
    a = abs(v)
    return ("$0" if v == 0 else f"${_trim(v / 1e9, 1)}B" if a >= 1e9 else f"${_trim(v / 1e6, 0 if a >= 1e8 else 1)}M" if a >= 1e6
            else f"${_trim(v / 1e3, 0)}K")


def rebuilt():
    """The forecast tables rebuilt from the published inputs (cached for the session)."""
    if "t" not in _cache:
        _cache["t"] = FP.rebuild()
    return _cache["t"]


def _finish(fig, title, note):
    run = P.run_info()
    fig.tight_layout(rect=(0, .06, 1, .92))
    fig.suptitle(title, x=.01, y=.985, ha="left", fontsize=12.5, fontweight="bold", color=INK)
    fig.text(.01, .008, f"{note} Source: Maryland Open Data Portal via the published tables, run {run['run_id']}.", ha="left", va="bottom",
             fontsize=8, color=MUTED, wrap=True)
    return fig


def coverage_summary():
    """Raw and calibrated coverage of the area forecast ranges, all areas pooled, as a small DataFrame."""
    c = rebuilt()["d_range_coverage"]
    c = c[(c.source == "bootstrap") & (c.area == C.ALL) & (c.horizon == 0)]
    return c[["scope", "calibrated", "n", "hits", "coverage", "cov_lo", "cov_hi", "factor"]].reset_index(drop=True)


def forecast_fan():
    """Each focus area: actuals, the State's plan, the median forecast, the raw range and the calibrated range."""
    f = rebuilt()["f_forecast"]
    areas = sorted(f.area.unique())
    with plt.rc_context(STYLE):
        fig, axs = plt.subplots(2, 4, figsize=(15, 6.6))
        for ax, area in zip(axs.ravel(), areas):
            g = f[f.area == area]
            a, fc = g[g.kind == "Actual"], g[g.kind == "Forecast"]
            ax.fill_between(fc.fiscal_year, fc.p10_cal, fc.p90_cal, color=BLUE, alpha=.15, lw=0, label="Calibrated range")
            ax.fill_between(fc.fiscal_year, fc.p10, fc.p90, color=BLUE, alpha=.30, lw=0, label="Raw range")
            for lo, hi, ls in ((fc.p10_cal, fc.p90_cal, ":"), (fc.p10, fc.p90, "-")):  # band edges at full colour: 3:1 contrast (WCAG 1.4.11)
                ax.plot(fc.fiscal_year, lo, color=BLUE, lw=.8, ls=ls)
                ax.plot(fc.fiscal_year, hi, color=BLUE, lw=.8, ls=ls)
            ax.plot(a.fiscal_year, a.value, color=INK, lw=1.8, marker="o", ms=3, label="Actual")
            ax.plot(fc.fiscal_year, fc.p50, color=BLUE, lw=1.6, ls="--", label="Median forecast")
            pl = fc.dropna(subset=["plan"])
            ax.plot(pl.fiscal_year, pl.plan, ls="", marker="o", mfc="none", mec=ORANGE, mew=1.5, label="State's plan (budget, not an outcome)")
            ax.set_title(area, loc="left")
            ax.set_ylim(bottom=0)
            ax.yaxis.set_major_formatter(money)
            ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True, nbins=5))
            ax.set_xlabel("Fiscal year")
        for ax in axs.ravel()[len(areas):]:
            ax.axis("off")
        h, lab = axs.ravel()[0].get_legend_handles_labels()
        axs.ravel()[-1].legend(h, lab, loc="center", frameon=False, fontsize=9)
        axs[1, 0].set_ylabel("Spending, nominal dollars")
        axs[0, 0].set_ylabel("Spending, nominal dollars")
        cov = coverage_summary().set_index(["scope", "calibrated"])
        r, k = cov.loc[("in_sample", 0)], cov.loc[("out_of_sample", 1)]
        return _finish(fig, f"The raw 80% range held only {r.coverage:.0%} of past outcomes; the wider calibrated range held {k.coverage:.0%}",
                       f"Raw range held {int(r.hits)} of {int(r.n)} past outcomes ({r.coverage:.1%}); the calibrated range held "
                       f"{int(k.hits)} of {int(k.n)} ({k.coverage:.1%}) with each outcome year held out. Nominal 80%. Fiscal years end June 30.")


def range_coverage():
    """How the ranges performed: share of past outcomes inside the range, by area, raw against calibrated."""
    c = rebuilt()["d_range_coverage"]
    c = c[(c.source == "bootstrap") & (c.horizon == 0) & (c.scope == "out_of_sample")]
    order = [a for a in sorted(c.area.unique()) if a != C.ALL] + [C.ALL]
    with plt.rc_context(STYLE):
        fig, ax = plt.subplots(figsize=(10, 4.8))
        for off, cal, col, lab in ((.17, 0, ORANGE, "Raw range"), (-.17, 1, BLUE, "Calibrated range")):
            d = c[c.calibrated == cal].set_index("area").loc[order]
            y = np.arange(len(order)) + off
            ax.errorbar(d.coverage, y, xerr=[d.coverage - d.cov_lo, d.cov_hi - d.coverage], fmt="o", color=col, ms=6, lw=1.4, capsize=3, label=lab)
            for yy, (_, r) in zip(y, d.iterrows()):
                ax.text(1.03, yy, f"{int(r.hits)} of {int(r.n)}", va="center", fontsize=8.5, color=col)
        ax.axvline(.8, color=INK, lw=1, ls=":")
        ax.text(.8, len(order) - .4, " nominal 80%", fontsize=8.5, color=INK, va="bottom")
        ax.set_yticks(np.arange(len(order)), order)
        ax.invert_yaxis()
        ax.set_xlim(0, 1.16)
        ax.set_xticks(np.arange(0, 1.01, .2), [f"{v:.0%}" for v in np.arange(0, 1.01, .2)])
        ax.set_xlabel("Share of past outcomes inside the range (bars: 95% Wilson interval)")
        ax.legend(frameon=False, loc="lower left")
        allc = c[(c.area == C.ALL) & (c.calibrated == 1)].iloc[0]
        worst = c[(c.area != C.ALL) & (c.calibrated == 1)].sort_values("coverage").iloc[0]
        return _finish(fig, f"Calibrated ranges cover {allc.coverage:.0%} overall, but {worst.area} stays low ({int(worst.hits)} of {int(worst.n)})",
                       "Rolling backtest, origins FY2021 to FY2024, horizons 1 to 3; each outcome year held out when fitting the widening. "
                       "Nine forecasts per area: the intervals are wide. Raw counts differ from the published 40 of 63 because each area's model "
                       "is re-chosen without the held-out year.")


def spending_base():
    """Controllable purchases by fiscal year, actuals against the State's plan years."""
    s = P.load("f_scope")
    s = s[s.scope == "Controllable purchases"].groupby(["fiscal_year", "stage"], as_index=False).budget.sum()
    with plt.rc_context(STYLE):
        fig, ax = plt.subplots(figsize=(10, 4.4))
        act = s.stage == "Actual"
        ax.bar(s[act].fiscal_year, s[act].budget, color=BLUE, width=.7, label="Actual")
        ax.bar(s[~act].fiscal_year, s[~act].budget, color=SURF, edgecolor=BLUE, hatch="///", width=.7, label="Budget (plan, not an outcome)")
        for _, r in s.iterrows():
            ax.text(r.fiscal_year, r.budget, money(r.budget), ha="center", va="bottom", fontsize=8.5, color=MUTED)
        ax.yaxis.set_major_formatter(money)
        ax.set_ylabel("Controllable purchases, nominal dollars")
        ax.set_xlabel("Fiscal year (ends June 30)")
        ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
        ax.legend(frameon=False, loc="upper left")
        a, b = s[act].iloc[0], s[act].iloc[-1]
        plan = s[~act].iloc[-1]
        return _finish(fig, f"Controllable purchases rose from {money(a.budget)} in FY{int(a.fiscal_year)} to {money(b.budget)} in FY{int(b.fiscal_year)}; "
                            f"the FY{int(plan.fiscal_year)} plan is {money(plan.budget)}", "Hatched bars are budgets, not spending.")


STATUS_ORDER = ["Seen", "Partly seen", "Not seen yet", "Payments fell", "Payments did not fall", "Projected only"]
STATUS_GROUP = {"Seen": "GMI gave a dollar figure", "Partly seen": "GMI gave a dollar figure", "Not seen yet": "GMI gave a dollar figure",
                "Payments fell": "No dollar figure given", "Payments did not fall": "No dollar figure given", "Projected only": "Projection only"}


def savings_table():
    """Reported savings items grouped by status, in reading order, with the reported dollars (None where GMI gave no figure)."""
    d = P.load("d_savings_status")
    g = d.groupby("status").agg(items=("check_id", "size"), reported=("reported", lambda x: x.sum(min_count=1)))
    g = g.reindex([x for x in STATUS_ORDER if x in g.index] + [x for x in g.index if x not in STATUS_ORDER])
    g.insert(0, "group", [STATUS_GROUP.get(x, "") for x in g.index])
    return g


def savings_status():
    """GMI's reported savings items by what the State's own payments show."""
    d = P.load("d_savings_status")
    g = savings_table().iloc[::-1]
    fig_items = g[g.group == "GMI gave a dollar figure"]
    seen = int(fig_items.loc[fig_items.index == "Seen", "items"].sum())
    styles = {"GMI gave a dollar figure": dict(color=BLUE), "No dollar figure given": dict(color=SURF, edgecolor=BLUE, hatch="///"),
              "Projection only": dict(color=SURF, edgecolor=MUTED, hatch="..")}
    with plt.rc_context(STYLE):
        fig, ax = plt.subplots(figsize=(10, 3.2 + .35 * len(g)))
        done = set()
        for i, (_status, r) in enumerate(g.iterrows()):
            ax.barh(i, r["items"], height=.6, label=None if r.group in done else r.group, **styles.get(r.group, dict(color=BLUE)))
            done.add(r.group)
            rep = r.reported
            ax.text(r["items"], i, f"  {r['items']} items" + (f", {money(rep)} reported" if rep == rep and rep else ", no dollar figure reported"),
                    va="center", fontsize=9, color=MUTED)
        ax.set_yticks(range(len(g)), g.index)
        ax.set_xlim(0, g["items"].max() * 1.6)
        ax.set_xlabel("Reported savings items")
        ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
        h, lab = ax.get_legend_handles_labels()
        ax.legend(h[::-1], lab[::-1], frameon=False, loc="lower right", fontsize=9)
        return _finish(fig, f"{seen} of the {int(fig_items['items'].sum())} reported savings with a dollar figure show up in the State's payments",
                       f"{len(d)} items from GMI's report. A payment pattern is evidence, not proof: correlation, not cause.")


def opportunities():
    """Leads by detector: the low-to-high screening range. Leads, not savings; the ranges are not additive."""
    d = P.load("d_opps").groupby("detector").agg(leads=("opp_id", "size"), low=("low", "sum"), high=("high", "sum")).sort_values("high")
    with plt.rc_context(STYLE):
        fig, ax = plt.subplots(figsize=(10, 3.4 + .3 * len(d)))
        y = np.arange(len(d))
        ax.barh(y, d.high - d.low, left=d.low, color=ORANGE, alpha=.55, height=.5)
        ax.plot(d.low, y, "|", color=ORANGE, ms=14, mew=2)
        ax.plot(d.high, y, "|", color=ORANGE, ms=14, mew=2)
        for i, r in enumerate(d.itertuples()):
            ax.text(r.high, i, f"  {r.leads} leads, {money(r.low)} to {money(r.high)}", va="center", fontsize=9, color=MUTED)
        ax.set_yticks(y, d.index)
        ax.set_xlim(0, d.high.max() * 1.55)
        ax.xaxis.set_major_formatter(money)
        ax.set_xlabel("Screening range per detector (assumed rates applied to flagged spending)")
        return _finish(fig, f"{int(d.leads.sum())} leads to review across {len(d)} detectors: screening ranges, not savings",
                       "Ranges use screening percentages from config/assumptions.yaml, are not forecasts and are not additive across detectors.")


def checks():
    """Data checks of the last published run, by pipeline stage."""
    d = P.load("run_checks").groupby(["stage", "status"]).size().unstack(fill_value=0)
    d = d.loc[d.sum(axis=1).sort_values().index].rename(index=lambda x: STAGE.get(x, x))
    with plt.rc_context(STYLE):
        fig, ax = plt.subplots(figsize=(10, 3 + .3 * len(d)))
        left = np.zeros(len(d))
        for status, col in (("pass", GREEN), ("warn", ORANGE), ("fail", INK)):
            if status in d:
                ax.barh(d.index, d[status], left=left, color=col, height=.6, label=status)
                left += d[status].to_numpy()
        for i, n in enumerate(left):
            ax.text(n, i, f" {int(n)}", va="center", fontsize=9, color=MUTED)
        ax.set_xlabel("Checks")
        ax.legend(frameon=False, loc="lower right")
        run = P.run_info()
        return _finish(fig, f"{run['checks']} data checks on the last published run: {run['passed']} passed, {run['warnings']} warned, {run['failed']} failed",
                       "A failed stop check keeps the last good database and blocks the export.")


STAGE = {"raw": "Raw downloads", "ref": "Reference tables", "core": "Cleaned tables", "mart": "Published tables"}


def table(df, caption, money=(), pct=(), ints=(), dec=(), signed=(), index=False, na="not stated"):
    """A pandas Styler for the walkthrough: a caption, readable numbers ($4.1B, -$5.5M, 63.5%, 1,234), a word for missing values."""
    fmt = {**{c: money_fmt for c in money}, **{c: "{:.1%}".format for c in pct}, **{c: "{:,.0f}".format for c in ints},
           **{c: "{:,.2f}".format for c in dec}, **{c: signed_money for c in signed}}
    st = df.style.format(fmt, na_rep=na).set_caption(caption)
    st = st.set_table_attributes('class="dataframe"')
    return st if index else st.hide(axis="index")


def claims_view():
    """Published reported figures (d_reported_claims) and the January report lined up with the Governor's page, item by item."""
    from src.models import claims
    c = P.load("d_reported_claims")
    return c, claims.compare(c)


def money_fmt(v):
    return money(v)


def signed_money(v):
    return "+" + money(v) if v > 0 else money_fmt(v)


def figure_data(name):
    """The numbers behind each figure, with readable column names: the text alternative shown under the chart."""
    if name == "checks":
        d = P.load("run_checks").groupby(["stage", "status"]).size().unstack(fill_value=0).rename(index=lambda x: STAGE.get(x, x)).reset_index()
        return table(d.rename(columns={"stage": "Pipeline stage"}), "Data checks by stage and status", ints=[c for c in d.columns if c != "stage"])
    if name == "spending_base":
        s = P.load("f_scope")
        s = s[s.scope == "Controllable purchases"].groupby(["fiscal_year", "stage"], as_index=False).budget.sum()
        s.columns = ["Fiscal year", "Stage", "Controllable purchases"]
        return table(s, "Controllable purchases by fiscal year", money=["Controllable purchases"])
    if name == "savings_status":
        g = savings_table().reset_index()
        g.columns = ["Status", "Kind of item", "Items", "Reported saving"]
        return table(g, "Reported savings items by status", money=["Reported saving"])
    if name == "forecast_fan":
        f = rebuilt()["f_forecast"]
        f = f[["area", "fiscal_year", "kind", "value", "p10", "p50", "p90", "p10_cal", "p90_cal", "plan"]]
        f.columns = ["Area", "Fiscal year", "Kind", "Actual", "Raw low (p10)", "Median", "Raw high (p90)", "Calibrated low", "Calibrated high",
                     "State's plan"]
        return table(f, "Actuals, forecasts and ranges by focus area", money=list(f.columns[3:]), na="")
    if name == "range_coverage":
        c = rebuilt()["d_range_coverage"]
        c = c[(c.source == "bootstrap") & (c.horizon == 0) & (c.scope == "out_of_sample")]
        c = c[["area", "calibrated", "hits", "n", "coverage", "cov_lo", "cov_hi"]].copy()
        c["calibrated"] = c.calibrated.map({0: "Raw", 1: "Calibrated"})
        c.columns = ["Area", "Range", "Outcomes inside", "Forecasts", "Coverage", "95% interval low", "95% interval high"]
        return table(c, "Share of past outcomes inside the range, each outcome year held out", pct=["Coverage", "95% interval low", "95% interval high"])
    if name == "opportunities":
        d = P.load("d_opps").groupby("detector", as_index=False).agg(leads=("opp_id", "size"), low=("low", "sum"), high=("high", "sum"))
        d.columns = ["Detector", "Leads", "Screening low", "Screening high"]
        return table(d, "Leads and screening ranges by detector (not additive)", money=["Screening low", "Screening high"])
    raise KeyError(name)


def show(name, caption=""):
    """Display one figure in the notebook as an accessible <figure>: the PNG with alt text, a caption that states the finding,
    and the numbers behind it in a collapsed table (W3C WAI complex-images pattern). The PNG is also kept for plain viewers."""
    import base64
    import html
    import io

    from IPython.display import display
    fig = FIGURES[name]()
    title = fig._suptitle.get_text() if fig._suptitle else name
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    b64 = base64.b64encode(buf.getvalue()).decode()
    alt = f"Chart: {title}. A description and the data behind the chart follow it."
    data = figure_data(name).to_html()
    body = (f'<figure class="chart" id="fig-{name}"><img alt="{html.escape(alt)}" src="data:image/png;base64,{b64}">'
            f'<figcaption><strong>{html.escape(title)}.</strong> {html.escape(caption)}</figcaption>'
            f'<details><summary>Data behind this chart</summary><div class="tbl">{data}</div></details></figure>')
    display({"text/html": body, "image/png": b64, "text/plain": f"<figure: {title}>"}, raw=True, metadata={"image/png": {"alt": alt}})


def childcare_program():
    """Child care program spending at the State Department of Education, by fiscal year (a reported finding the tracker did not find)."""
    p = P.load("f_program")
    p = p[(p.agency_code == "R00") & p.program_name.str.contains("Child Care", case=False)].groupby(["fiscal_year", "stage"], as_index=False).budget.sum()
    with plt.rc_context(STYLE):
        fig, ax = plt.subplots(figsize=(10, 4.6))
        act = p.stage == "Actual"
        ax.axvspan(2022.5, 2025.5, color=ORANGE, alpha=.10, lw=0)
        ax.text(2024, p.budget.max() * 1.13, "period of the reported internal audits", ha="center", fontsize=8.5, color=ORANGE)
        ax.bar(p[act].fiscal_year, p[act].budget, color=BLUE, width=.7, label="Actual")
        ax.bar(p[~act].fiscal_year, p[~act].budget, color=SURF, edgecolor=BLUE, hatch="///", width=.7, label="Budget (plan, not an outcome)")
        for _, r in p.iterrows():
            ax.text(r.fiscal_year, r.budget, money(r.budget), ha="center", va="bottom", fontsize=8.5, color=MUTED)
        ax.set_ylim(0, p.budget.max() * 1.22)
        ax.yaxis.set_major_formatter(money)
        ax.set_ylabel("Program spending, nominal dollars")
        ax.set_xlabel("Fiscal year (ends June 30)")
        ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
        ax.legend(frameon=False, loc="upper left")
        a = p[act].set_index("fiscal_year").budget
        return _finish(fig, f"Child care program spending rose from {money(a.iloc[0])} in FY{int(a.index[0])} to {money(a.iloc[-1])} in FY{int(a.index[-1])}",
                       "State Department of Education, Aid To Education, program 59 (named Child Care Subsidy, Scholarship, then Assistance Grants). "
                       "The tracker confirms the program's size; it cannot see provider-level overpayments.")


def program_screen_table():
    """The statewide program screen computed from the published program table and the reference files."""
    names = P.load("d_agency").set_index("agency_code").agency.to_dict()
    return PS.screen(P.load("f_program"), *PS.reference(), agencies=names)


def program_screen():
    """The largest programs that both grew fast and swung sharply, every agency screened the same way."""
    cfg = PS.assumptions()
    d = program_screen_table()
    top = d[d.signals == 2].head(cfg["top_n"]).iloc[::-1]
    with plt.rc_context(STYLE):
        fig, ax = plt.subplots(figsize=(11, 3 + .36 * len(top)))
        y = np.arange(len(top))
        audited = top.ola_findings.notna()
        ax.barh(y, top.spend_last, color=[BLUE if a else MUTED for a in audited], height=.62)
        for i, r in enumerate(top.itertuples()):
            note = f"  {money(r.spend_last)}, {r.growth_multiple:.1f}x since FY{r.first_fy}, largest swing {r.largest_swing:+.0%} (FY{r.swing_fy})"
            if r.reported_findings:
                note += f"; reported finding {money(r.reported_amount)}"
            ax.text(r.spend_last, i, note, va="center", fontsize=8.5, color=ORANGE if r.reported_findings else MUTED)
        ax.set_yticks(y, [f"{r.agency_code}  {str(r.program_name)[:46]}" for r in top.itertuples()], fontsize=8.5)
        ax.set_xlim(0, top.spend_last.max() * 1.9)
        ax.xaxis.set_major_formatter(money)
        ax.set_xlabel(f"Actual spending in FY{cfg['last_actual_fy']}, nominal dollars")
        handles = [matplotlib.patches.Patch(color=BLUE, label="Agency has an audit report on file"),
                   matplotlib.patches.Patch(color=MUTED, label="No audit report on file")]
        ax.legend(handles=handles, frameon=False, loc="lower right", fontsize=8.5)
        return _finish(fig, f"{int((d.signals == 2).sum())} of {len(d)} programs both grew {cfg['fast_growth_multiple']:.0f}x or more and swung "
                            f"{cfg['large_swing']:.0%} or more in a year: the {len(top)} largest",
                       f"Every program of every agency with {cfg['min_years']}+ actual years and {money(cfg['min_spend'])}+ in FY{cfg['last_actual_fy']}. "
                       "An order in which to ask questions, not a finding: programs grow and swing for ordinary reasons.")


FIGURES = {"forecast_fan": forecast_fan, "range_coverage": range_coverage, "spending_base": spending_base, "savings_status": savings_status,
           "opportunities": opportunities, "checks": checks, "childcare_program": childcare_program, "program_screen": program_screen}


def main():
    plt.switch_backend("Agg")
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in FIGURES.items():
        fig = fn()
        fig.savefig(OUT / f"{name}.png", dpi=150, bbox_inches="tight")
        plt.close(fig)
        print("wrote", (OUT / f"{name}.png").relative_to(ROOT))


if __name__ == "__main__":
    main()
