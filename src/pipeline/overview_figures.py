"""Figures drawn from the published tables only (site_data/), for the walkthrough notebook and the executive overview.

    python -m src.pipeline.overview_figures        # writes docs/figures/overview/*.png

Each function returns a matplotlib Figure; `main` saves them all. The forecast figures rebuild the forecast and its
range calibration from the published inputs (src/models/forecast_published.py), so nothing here needs the warehouse.
Chart conventions: bars start at zero, one y axis, units on the axis, budget years drawn differently from actuals,
ranges drawn as bands with their meaning in the caption, colour-blind-safe pairs (blue / orange), no pie charts.
"""
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

from .. import published as P
from ..models import calibration as C
from ..models import forecast_published as FP

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "figures" / "overview"
BLUE, ORANGE, GREEN, INK, MUTED, GRID, SURF = "#2a78d6", "#eb6834", "#1baf7a", "#0b0b0b", "#52514e", "#e6e5e0", "#fcfcfb"
STYLE = {"figure.facecolor": SURF, "axes.facecolor": SURF, "axes.edgecolor": GRID, "axes.labelcolor": MUTED, "xtick.color": MUTED,
         "ytick.color": MUTED, "axes.grid": True, "grid.color": GRID, "grid.linewidth": .8, "axes.axisbelow": True, "font.size": 10,
         "axes.titlesize": 10, "axes.titleweight": "bold", "axes.titlecolor": INK, "axes.spines.top": False, "axes.spines.right": False}
_cache = {}


def money(v, _=None):
    a = abs(v)
    return "$0" if v == 0 else f"${v / 1e9:,.1f}B" if a >= 1e9 else f"${v / 1e6:,.0f}M" if a >= 1e6 else f"${v / 1e3:,.0f}K"


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
            ax.plot(a.fiscal_year, a.value, color=INK, lw=1.8, marker="o", ms=3, label="Actual")
            ax.plot(fc.fiscal_year, fc.p50, color=BLUE, lw=1.6, ls="--", label="Median forecast")
            pl = fc.dropna(subset=["plan"])
            ax.plot(pl.fiscal_year, pl.plan, ls="", marker="o", mfc="none", mec=ORANGE, mew=1.5, label="State's plan (budget, not an outcome)")
            ax.set_title(area, loc="left")
            ax.set_ylim(bottom=0)
            ax.yaxis.set_major_formatter(money)
            ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True, nbins=5))
        for ax in axs.ravel()[len(areas):]:
            ax.axis("off")
        h, lab = axs.ravel()[0].get_legend_handles_labels()
        axs.ravel()[-1].legend(h, lab, loc="center", frameon=False, fontsize=9)
        axs[1, 0].set_ylabel("Spending, nominal dollars")
        axs[0, 0].set_ylabel("Spending, nominal dollars")
        cov = coverage_summary().set_index(["scope", "calibrated"])
        r, k = cov.loc[("in_sample", 0)], cov.loc[("out_of_sample", 1)]
        return _finish(fig, "Spending forecasts by focus area, with raw and calibrated ranges",
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
        return _finish(fig, "How the forecast ranges performed on past years",
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
        return _finish(fig, "The spending base: controllable purchases in the operating budget", "Hatched bars are budgets, not spending.")


def savings_status():
    """GMI's reported savings items by what the State's own payments show."""
    d = P.load("d_savings_status")
    g = d.groupby("status").agg(items=("check_id", "size"), reported=("reported", "sum")).sort_values("items")
    with plt.rc_context(STYLE):
        fig, ax = plt.subplots(figsize=(10, 3.2 + .35 * len(g)))
        ax.barh(g.index, g["items"], color=BLUE, height=.6)
        for i, (n, rep) in enumerate(zip(g["items"], g.reported)):
            ax.text(n, i, f"  {n} items" + (f", {money(rep)} reported" if rep else ", no dollar figure reported"), va="center", fontsize=9, color=MUTED)
        ax.set_xlim(0, g["items"].max() * 1.6)
        ax.set_xlabel("Reported savings items")
        ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
        return _finish(fig, "Reported savings checked against the State's payments",
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
        return _finish(fig, "Opportunity leads by detector: leads to review, not savings",
                       "Ranges use screening percentages from config/assumptions.yaml, are not forecasts and are not additive across detectors.")


def checks():
    """Data checks of the last published run, by pipeline stage."""
    d = P.load("run_checks").groupby(["stage", "status"]).size().unstack(fill_value=0)
    d = d.loc[d.sum(axis=1).sort_values().index]
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


FIGURES = {"forecast_fan": forecast_fan, "range_coverage": range_coverage, "spending_base": spending_base, "savings_status": savings_status,
           "opportunities": opportunities, "checks": checks}


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
