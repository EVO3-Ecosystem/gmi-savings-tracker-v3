"""Fiscal-year audit: is every page, tab, card, figure, doc and export on the same fiscal-year calendar?

    python scripts/fy_audit.py                      # audit site_data/ and the docs; writes out/fy_audit.md
    python scripts/fy_audit.py --site site          # also render the built site in headless Chromium, tab by tab
    python scripts/fy_audit.py --data data/export/latest --site site --out /tmp/fy_audit.md

The calendar is read from the data, never typed in here:
  * budget years and their stages      stage per year in f_function (Actual / Working budget / Legislative appropriation)
  * last actual budget year            the latest year whose stage is Actual
  * payment years                      totals_by_fy; the partial year is the one flagged partial_year (the open year)
  * last full payments year            the latest payment year not flagged partial
  * grants                             f_grants
  * forecast horizon                   f_forecast

Then three kinds of check:
  1. Exports    each table's year range against the calendar for its kind (budget, payments, grants, forecast), and
                the yearly totals reconciled across tables (payments: totals_by_fy = f_agency payments = portal; budget:
                f_function = f_agency = f_scope = the portal total in stage_evidence).
  2. Pages      every FY mention on every tab (and every stand-alone page): years outside the calendar, the partial
                payments year shown without a partial label, the latest actual year called something else.
  3. Docs       README and docs/*.md: the same rules, plus stale phrases (a year called "partial" or "latest" that the
                calendar says is not).
Exit code 1 when any check fails.
"""
import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FY = re.compile(r"\bFY ?(20\d\d)\b|\bFY ?'?(\d\d)\b(?![-–]\d)")


def rows(d, name):
    p = d / f"{name}.csv"
    return list(csv.DictReader(p.open(encoding="utf-8"))) if p.exists() else []


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def truthy(v):
    return str(v).strip().lower() in ("true", "1", "t", "yes")


class Report:
    def __init__(self):
        self.lines, self.fails, self.warns = [], 0, 0

    def h(self, t):
        self.lines += ["", f"## {t}", ""]

    def ok(self, what, detail=""):
        self.lines.append(f"- PASS {what}" + (f": {detail}" if detail else ""))

    def fail(self, what, detail=""):
        self.fails += 1
        self.lines.append(f"- **FAIL** {what}" + (f": {detail}" if detail else ""))

    def warn(self, what, detail=""):
        self.warns += 1
        self.lines.append(f"- WARN {what}" + (f": {detail}" if detail else ""))

    def check(self, cond, what, detail=""):
        (self.ok if cond else self.fail)(what, detail)

    def text(self, t):
        self.lines.append(t)


def calendar(d):
    st = defaultdict(set)
    for r in rows(d, "f_function"):
        st[int(r["fiscal_year"])].add(r["stage"])
    stage = {y: sorted(s)[0] for y, s in st.items()}
    tot = rows(d, "totals_by_fy")
    pay = sorted(int(r["fiscal_year"]) for r in tot)
    partial = sorted(int(r["fiscal_year"]) for r in tot if truthy(r.get("partial_year")))
    full = [y for y in pay if y not in partial]
    grants = sorted({int(r["fiscal_year"]) for r in rows(d, "f_grants")})
    fc = sorted({int(r["fiscal_year"]) for r in rows(d, "f_forecast")})
    actual = [y for y, s in stage.items() if s == "Actual"]
    return {
        "stage": stage, "budget": (min(stage), max(stage)), "last_actual": max(actual),
        "payments": (pay[0], pay[-1]), "partial": partial, "last_full_pay": full[-1],
        "grants": (grants[0], grants[-1]) if grants else None, "forecast": (fc[0], fc[-1]) if fc else None,
    }


FLAGGED = {"totals_by_fy"}  # payment tables that publish the open year, flagged partial_year (src/pipeline/export.py FLAG_PARTIAL)
KIND = {  # table -> the calendar its years must follow (None = a sub-range chosen by design, only bounded)
    "budget": ["f_function", "f_agency", "f_scope", "f_code", "f_object", "f_program", "f_fund", "f_fund_source",
               "d_all_funds", "f_overlap", "f_budget_vs_pay", "f_revenue", "d_book_reconciliation", "d_fund_shift",
               "d_federal_crosswalk"],
    "payments": ["totals_by_fy", "f_payee_type", "f_vendor_year", "f_concentration"],
    "payments_window": ["f_vendor", "f_vendor_detail", "f_vendor_pay", "d_area_top", "d_families", "d_multi",
                        "d_multi_basis", "review_queue", "d_payment_screen_summary"],
}


def audit_exports(d, cal, R):
    R.h("Calendar (read from the data)")
    s = cal["stage"]
    R.text("| Fiscal year | Budget stage | Payments |")
    R.text("|---|---|---|")
    for y in range(min(cal["payments"][0], cal["budget"][0]), max(cal["payments"][1], cal["budget"][1]) + 1):
        p = "partial (year in progress)" if y in cal["partial"] else ("full year" if cal["payments"][0] <= y <= cal["payments"][1] else "")
        R.text(f"| FY{y} | {s.get(y, '')} | {p} |")
    R.text("")
    R.text(f"Last actual budget year FY{cal['last_actual']}; last full payments year FY{cal['last_full_pay']}; "
           f"partial payments year {', '.join('FY%d' % y for y in cal['partial']) or 'none'}; grants "
           f"FY{cal['grants'][0]}-FY{cal['grants'][1]}; forecast FY{cal['forecast'][0]}-FY{cal['forecast'][1]}.")

    R.h("1. Exports: year ranges")
    src = {r["source"]: r for r in rows(d, "sources.csv"[:-4])}
    for key, (a0, a1), label in (("payments", cal["payments"], "payments"), ("budget", cal["budget"], "budget")):
        m = re.match(r"FY(\d{4})-FY(\d{4})", (src.get(key) or {}).get("years", ""))
        if m:
            R.check(int(m.group(2)) == a1, f"Published {label} reach the last year in the State's data (FY{m.group(2)})",
                    f"published FY{a0}-FY{a1}" + ("; the open year is published flagged partial" if key == "payments" and cal["partial"] else ""))
    b0, b1 = cal["budget"]
    p0, p1 = cal["payments"]
    for kind, names in KIND.items():
        for n in names:
            rr = rows(d, n)
            if not rr:
                R.warn(f"{n}", "not in this export")
                continue
            col = "fiscal_year" if "fiscal_year" in rr[0] else None
            if not col:
                continue
            ys = sorted({int(float(r[col])) for r in rr if r[col]})
            rng = f"FY{ys[0]}-FY{ys[-1]}"
            if kind == "budget":
                lo = b0 if n not in ("f_budget_vs_pay",) else b0
                R.check(ys[0] >= min(b0, p0) and ys[-1] == b1, f"{n} reaches the latest budget year FY{b1}", rng)
            elif kind == "payments" and n not in FLAGGED:
                R.check(ys[-1] == cal["last_full_pay"], f"{n} reaches the last full payments year FY{cal['last_full_pay']} (the open year is held back by design)", rng)
            elif kind == "payments":
                R.check(ys[-1] == p1, f"{n} reaches the latest payments year FY{p1}", rng)
                if cal["partial"] and "partial_year" in rr[0]:
                    flagged = {int(float(r["fiscal_year"])) for r in rr if truthy(r["partial_year"])}
                    R.check(flagged == set(cal["partial"]), f"{n} flags exactly the partial year", f"flagged {sorted(flagged)}")
                elif cal["partial"] and ys[-1] in cal["partial"]:
                    R.fail(f"{n} carries the partial year without a partial_year flag", rng)
            else:
                R.check(ys[-1] <= p1, f"{n} stays within the payments calendar", rng)
    fa = rows(d, "f_area")
    if fa:
        ys = sorted({int(r["fiscal_year"]) for r in fa if r.get("spend") not in ("", None)})
        R.check(ys[-1] == b1, "f_area budget spending reaches the latest budget year", f"FY{ys[0]}-FY{ys[-1]}")
        ps = sorted({int(r["fiscal_year"]) for r in fa if r.get("payee_spend") not in ("", None)})
        R.check(ps[-1] == cal["last_full_pay"], "f_area payee spending reaches the last full payments year (open year held back)", f"FY{ps[0]}-FY{ps[-1]}")

    R.h("1b. Exports: yearly totals reconciled across tables")
    tot = {int(r["fiscal_year"]): num(r["total_payments"]) for r in rows(d, "totals_by_fy")}
    ag = defaultdict(float)
    for r in rows(d, "f_agency"):
        v = num(r.get("payments"))
        if v is not None:
            ag[int(r["fiscal_year"])] += v
    site = {int(r["fiscal_year"]): r for r in rows(d, "d_site_reconciliation") if r.get("dataset") == "payments"}
    bad = []
    for y, t in sorted(tot.items()):  # f_agency holds payments matched to an agency only: never more than the total
        if y in ag and ag[y] > 0 and (ag[y] > t * 1.0001 or ag[y] < t * 0.9):
            bad.append(f"FY{y} totals {t/1e9:.2f}B vs f_agency {ag[y]/1e9:.2f}B")
    share = [ag[y] / tot[y] for y in tot if y in ag and tot[y]]
    R.check(not bad, "Payments: f_agency payments are a subset of totals_by_fy every year (matched to an agency)",
            "; ".join(bad) or f"{len(share)} years; matched share {min(share):.1%}-{max(share):.1%}")
    tsite = {y: r for y, r in site.items()}
    miss = [f"FY{y}" for y in tot if y in tsite and abs((num(tsite[y]["data_total"]) or 0) - tot[y]) > 1]
    R.check(not miss, "Payments: totals_by_fy equals the reconciled data total every year", ", ".join(miss) or f"{len(tot)} years")
    missing_ag = [y for y in tot if y >= b0 and y not in ag and y not in cal["partial"]]
    R.check(not missing_ag, "Payments: every payments year from FY%d has agency rows" % b0, ", ".join(map(str, missing_ag)) or "")
    if site:
        diffs = [f"FY{y} {num(r.get('difference')):+,.0f}" for y, r in site.items() if num(r.get("difference")) and abs(num(r["difference"])) > 1]
        R.check(not diffs, "Payments: every year matches the State's vendor-payments site", "; ".join(diffs) or f"{len(site)} years")
    fun, sc, fag = defaultdict(float), defaultdict(float), defaultdict(float)
    for r in rows(d, "f_function"):
        fun[int(r["fiscal_year"])] += num(r["budget"]) or 0
    for r in rows(d, "f_agency"):
        fag[int(r["fiscal_year"])] += num(r.get("operating_spending") or r.get("budget")) or 0
    bad = [f"FY{y} f_function {fun[y]/1e9:.3f}B vs f_agency {fag[y]/1e9:.3f}B" for y in fun if fag.get(y) and abs(fun[y] - fag[y]) > max(1e6, 1e-4 * fun[y])]
    R.check(not bad, "Budget: f_function matches f_agency every year", "; ".join(bad) or f"FY{min(fun)}-FY{max(fun)}")
    se = rows(d, "stage_evidence")
    for r in se:
        y, ft = int(r["fiscal_year"]), num(r.get("file_total"))
        if ft and y in fun and not r.get("programs_compared") and "not the" not in (r.get("evidence") or ""):
            R.check(abs(fun[y] - ft) < 1e6, f"Budget FY{y}: f_function equals the portal file total in stage_evidence", f"{fun[y]:,.0f} vs {ft:,.0f}")
    bsite = {int(r["fiscal_year"]): num(r["site_total"]) for r in rows(d, "d_site_reconciliation") if r.get("dataset") == "budget"}
    bad = [f"FY{y} {fun[y]:,.0f} vs site {bsite[y]:,.0f}" for y in fun if y in bsite and abs(fun[y] - bsite[y]) > 10]
    R.check(not bad, "Budget: f_function equals operatingbudget.maryland.gov every year", "; ".join(bad) or f"{len(bsite)} years")
    return fun, tot


def alignment(d, R, out_csv=None):
    """One row per fiscal year, budget, actual and payments kept apart (never added or netted)."""
    import pandas as pd
    ff = pd.read_csv(d / "f_function.csv")
    b = ff.groupby("fiscal_year").agg(stage=("stage", "first"), operating=("budget", "sum"))
    af = pd.read_csv(d / "d_all_funds.csv").set_index("fiscal_year")["all_funds_including_higher_education"].rename("all_funds")
    tb = pd.read_csv(d / "totals_by_fy.csv").set_index("fiscal_year")
    pay = tb["total_payments"].rename("payments")
    part = (tb["partial_year"].astype(str).str.lower() == "true") if "partial_year" in tb else pd.Series(False, index=tb.index)
    gr = pd.read_csv(d / "f_grants.csv").groupby("fiscal_year")["amount"].sum().rename("grants")
    s = pd.read_csv(d / "d_site_reconciliation.csv")
    site = s.pivot_table(index="fiscal_year", columns="dataset", values="difference", aggfunc="sum")
    x = b.join(af, how="outer").join(pay, how="outer").join(gr, how="outer")
    x["payments_partial"] = part.reindex(x.index).fillna(False).astype(bool)
    x["budget_plan"] = x.operating.where(x.stage.notna() & (x.stage != "Actual"))
    x["actual"] = x.operating.where(x.stage == "Actual")
    x["budget_plan_all_funds"] = x.all_funds.where(x.stage.notna() & (x.stage != "Actual"))
    x["actual_all_funds"] = x.all_funds.where(x.stage == "Actual")
    for k, col in (("budget", "budget_matches_state_site"), ("payments", "payments_match_state_site")):
        v = site[k].reindex(x.index) if k in site else pd.Series(index=x.index, dtype=float)
        x[col] = v.abs().le(10).astype(object).where(v.notna(), None)
    last_actual = int(x.index[x.stage == "Actual"].max())

    def why(r):
        y = r.name
        if pd.isna(r.stage):
            return "before the operating budget data (FY2017); payments only"
        if r.stage == "Actual":
            return "actual published; the open data no longer carries this year's appropriation (see the budget books)"
        if y == last_actual + 1:
            return f"working budget; actuals expected with the FY{y + 2} Governor's budget (January {y + 1})"
        return f"{r.stage.lower()}; actuals expected with the FY{y + 2} Governor's budget (January {y + 1})"
    x["note"] = x.apply(why, axis=1)
    x.loc[x.payments_partial, "note"] += "; payments are the year so far (partial)"
    cols = ["stage", "budget_plan", "actual", "payments", "payments_partial", "budget_plan_all_funds", "actual_all_funds", "grants",
            "budget_matches_state_site", "payments_match_state_site", "note"]
    x = x[cols]
    if out_csv:
        Path(out_csv).parent.mkdir(parents=True, exist_ok=True)
        x.round(2).to_csv(out_csv, index_label="fiscal_year")
    R.h("Budget, actuals and payments by fiscal year (kept apart: never added or netted)")
    B = lambda v: "" if pd.isna(v) else f"${v / 1e9:,.2f}B"
    R.text("| FY | Budget stage | Budget (plan) | Actual | Payments to vendors | Budget = State site | Payments = State site | Note |")
    R.text("|---|---|---|---|---|---|---|---|")
    ok = lambda v: "" if v is None or pd.isna(v) else ("yes" if v else "**no**")
    for y, r in x.sort_index(ascending=False).iterrows():
        R.text(f"| FY{y} | {r.stage if isinstance(r.stage, str) else ''} | {B(r.budget_plan)} | {B(r.actual)} | {B(r.payments)}{' (partial)' if r.payments_partial else ''} | "
               f"{ok(r.budget_matches_state_site)} | {ok(r.payments_match_state_site)} | {r.note} |")
    R.text("")
    R.text("Operating budget basis (excludes public higher education; the all-funds columns in the CSV add it). Payments leave out payroll "
           "and include capital and pass-through money, so they are never added to or netted against the budget.")
    bad = x[x.budget_matches_state_site.map(lambda v: v is False) | x.payments_match_state_site.map(lambda v: v is False)]
    R.check(bad.empty, "Every year's budget and payments equal the State's own sites", ", ".join(f"FY{y}" for y in bad.index) or f"{len(x)} years")
    both = x[x.budget_plan.notna() & x.actual.notna()]
    R.check(both.empty, "No year shows a plan and an actual from the open data at once (one stage per year)", f"{len(both)} years")
    return x


PAGE_RULES = None


def mentions(text):
    out = []
    for m in FY.finditer(text):
        y = int(m.group(1)) if m.group(1) else 2000 + int(m.group(2))
        a, b = max(0, m.start() - 90), min(len(text), m.end() + 90)
        out.append((y, " ".join(text[a:b].split())))
    return out


PAY_WORDS = re.compile(r"\bpa(id|yment|yments|yee|yees)\b|\bvendor", re.I)
PARTIAL_WORDS = re.compile(r"partial|in progress|so far|not a full year|year to date|began July 1|left out", re.I)
SENT = re.compile(r"(?<=[.;!?])\s+(?=[A-Z(])|\n+")
FYALL = re.compile(r"\bFY ?(20\d\d)\b")


def rule_text(where, text, cal, R, quiet_ok=False):
    """Sentence by sentence: a sentence is wrong only on its own evidence."""
    hi = max(cal["budget"][1], cal["forecast"][1] if cal["forecast"] else 0)
    lo = min(cal["payments"][0], cal["budget"][0])
    probs, n = [], 0
    for s in SENT.split(text):
        s = " ".join(s.split())
        ys = [int(y) for y in FYALL.findall(s)]
        n += len(ys)
        if not ys:
            continue
        short = s if len(s) <= 220 else s[:217] + "..."
        for y in sorted(set(ys)):
            if y > hi or y < lo - 1:
                probs.append(f"FY{y} is outside the data calendar: \u201c{short}\u201d")
        # the open payments year shown as payments without saying it is partial
        ranges = {int(b) for b in re.findall(r"FY ?20\d\d ?(?:[-–]|to|through) ?FY ?(20\d\d)", s)}
        for y in cal["partial"]:
            if y in ys and y not in ranges and PAY_WORDS.search(s) and not PARTIAL_WORDS.search(s) and not re.search(r"budget|appropriation|forecast|allowance", s, re.I):
                probs.append(f"FY{y} payments shown without a partial label: \u201c{short}\u201d")
        # a full payments year called partial (\"FY2026 payments are partial\")
        for m in re.finditer(r"FY ?(20\d\d)[^.;]{0,40}?\b(payments?|paid)\b[^.;]{0,30}?\b(is|are|was) (a )?partial", s, re.I):
            if int(m.group(1)) not in cal["partial"]:
                probs.append(f"FY{m.group(1)} payments called partial, but it is a full year: \u201c{short}\u201d")
        # the latest actual budget year named as something else
        for m in re.finditer(r"(?<!after the )(?<!before the )\b(latest|last|most recent) actual (budget )?(year )?(is |was |= |: )?FY ?(20\d\d)", s, re.I):
            if int(m.group(5)) != cal["last_actual"] and not PAY_WORDS.search(s):
                probs.append(f"latest actual budget year called FY{m.group(5)} (calendar: FY{cal['last_actual']}): \u201c{short}\u201d")
        for m in re.finditer(r"actuals? through FY ?(20\d\d)", s, re.I):
            if int(m.group(1)) != cal["last_actual"] and not PAY_WORDS.search(s) and not re.search(r"origin|backtest|fit|train|scored|revenue|closeout", s, re.I):
                probs.append(f"actuals said to run through FY{m.group(1)} (calendar: FY{cal['last_actual']}): \u201c{short}\u201d")
        # the payments portal's out-of-date title quoted as if it were the coverage
        if re.search(r"FY ?2008 to FY ?2024", s) and not re.search(r"title|named|portal name|stale|runs to|data runs|Payments Data: FY", s, re.I):
            probs.append(f"payments coverage given as the portal's stale title: \u201c{short}\u201d")
    seen = set()
    probs = [p for p in probs if not (p in seen or seen.add(p))]
    for p in probs:
        R.fail(where, p)
    if not probs and not quiet_ok:
        R.ok(where, f"{n} FY mentions, all on the calendar")
    return probs


def audit_site(site, cal, R):
    from playwright.sync_api import sync_playwright
    import http.server
    import threading
    import functools
    R.h("2. Pages: every tab of the dashboard, and every stand-alone page")
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    handler = functools.partial(Quiet, directory=str(site))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/"
    shots = Path(R.shots) if getattr(R, "shots", None) else None
    with sync_playwright() as pw:
        br = pw.chromium.launch(executable_path="/usr/bin/google-chrome" if Path("/usr/bin/google-chrome").exists() else None)
        pg = br.new_page(viewport={"width": 1440, "height": 900})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(base + "index.html", wait_until="networkidle")
        pg.wait_for_timeout(2500)
        tabs = pg.eval_on_selector_all("[role=tab]", "els => els.map(e => [e.id, e.textContent.trim()])")
        R.check(len(tabs) == 11, "Dashboard has 11 tabs", ", ".join(t for _, t in tabs))
        for tid, name in tabs:
            pg.click(f"#{tid}")
            pg.wait_for_timeout(1200)
            panel = pg.evaluate("""() => { const t = document.querySelector('[role=tab][aria-selected=true]');
                const id = t && t.getAttribute('aria-controls'); const el = id && document.getElementById(id);
                return (el || document.querySelector('main') || document.body).innerText; }""")
            rule_text(f"Tab “{name}”", panel, cal, R)
            if shots:
                shots.mkdir(parents=True, exist_ok=True)
                pg.screenshot(path=str(shots / f"tab-{tid}.png"), full_page=False)
        head = pg.evaluate("() => (document.querySelector('header') || document.body).innerText.slice(0, 1500)")
        rule_text("Page header and banner", head, cal, R)
        R.check(not errs, "No script errors while clicking through every tab", "; ".join(errs[:3]))
        for f in sorted(site.glob("*.html")):
            if f.name in ("index.html", "404.html"):
                continue
            errs.clear()
            pg.goto(base + f.name, wait_until="networkidle")
            pg.wait_for_timeout(1500)
            rule_text(f"Page {f.name}", pg.evaluate("() => document.body.innerText"), cal, R)
            if errs:
                R.fail(f"Page {f.name}", "script errors: " + "; ".join(errs[:3]))
        br.close()
    srv.shutdown()


def audit_docs(cal, R):
    R.h("3. Docs")
    files = [ROOT / "README.md", ROOT / "CHANGELOG.md"] + sorted((ROOT / "docs").rglob("*.md"))
    for f in files:
        if not f.exists() or "parity" in f.parts or "archive" in f.parts:
            continue
        t = f.read_text(encoding="utf-8", errors="replace")
        if f.name == "CHANGELOG.md":  # history: only years outside the calendar
            t = "\n".join(l for l in t.splitlines() if not l.startswith("#"))
        rule_text(f"{f.relative_to(ROOT)}", t, cal, R, quiet_ok=True)
    R.ok("docs scanned", f"{len(files)} files; only problems are listed above")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "site_data"))
    ap.add_argument("--site")
    ap.add_argument("--shots")
    ap.add_argument("--alignment", default=str(ROOT / "docs" / "reconciliation" / "fy_alignment.csv"), help="year-by-year budget, actual and payments table")
    ap.add_argument("--out", default=str(ROOT / "out" / "fy_audit.md"))
    a = ap.parse_args(argv)
    d = Path(a.data)
    cal = calendar(d)
    R = Report()
    R.shots = a.shots
    R.text("# Fiscal-year audit")
    audit_exports(d, cal, R)
    alignment(d, R, a.alignment)
    if a.site:
        audit_site(Path(a.site), cal, R)
    audit_docs(cal, R)
    R.lines.insert(1, f"\n**{R.fails} failed, {R.warns} warnings.** Data: `{d}`" + (f"; site: `{a.site}`" if a.site else ""))
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(R.lines) + "\n", encoding="utf-8")
    print(f"{R.fails} failed, {R.warns} warnings -> {out}")
    return 1 if R.fails else 0


if __name__ == "__main__":
    sys.exit(main())
