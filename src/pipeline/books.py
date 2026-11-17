"""Reconcile the budget data with DBM's own budget books for every fiscal year (v3.2, data accuracy).

    python -m src.pipeline.books            # download (cached), parse, compare, write the reference files
    python -m src.pipeline.books --check    # compare only; exit 1 unless every year reconciles

Sources (dbm.maryland.gov, all public; cached in data/crosscheck/books/):
  * Governor's budget books, Volumes I-III, FY2019-FY2027. Each prints, per program, Actual (two years back),
    Appropriation (prior year) and Allowance (budget year), with the funds that pay for it.
  * FY2027 Fiscal Digest (the budget as enacted): Exhibit B, appropriations by program and fund; Exhibit E, the
    FY2026 deficiency appropriations as enacted.
  * FY2027 Supplemental Budgets No. 1 and No. 2: their summary statements.

The identity tested for every actual year, FY2017-FY2025:
    book Total Expenditure - Reimbursable Funds - Non-Budgeted Funds = operating budget (yu65-jmmv) + public higher
    education (4mca-332u)
Reimbursable funds (money one agency pays another) and non-budgeted funds (MDTA, MES, the Stadium Authority, State
Retirement investments) are in the books but are not appropriated in the State budget, and the open data leaves them
out. FY2027 (legislative appropriation) is compared by fund with the Fiscal Digest's Exhibit B. FY2026 is the working
appropriation, which no DBM document prints until the FY2028 books: it is bridged (FY2027 book appropriation column +
enacted deficiencies) and the remainder is labelled as budget amendments, never passed.

Outputs (checked in, so every build re-tests the warehouse against them, src/pipeline/checks.py):
  reference/book_reconciliation.csv          one row per fiscal year and basis: the book's figures with their source
  reference/book_program_differences.csv     every program that differs, with the reason
"""
import argparse
import datetime as dt
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "crosscheck" / "books"
DB = ROOT / "data" / "md_transparency.duckdb"
B = "https://dbm.maryland.gov/budget/Documents/operbudget"
TOLERANCE_SHARE = 0.0001  # pre-registered (Nov 16, 2026): a statewide total reconciles within 0.01% ...
MIN_EXACT = 0.99          # ... with at least 99% of the programs in both equal to the dollar


def volumes(year):
    """URLs of the Governor's budget book volumes for a budget year."""
    if year == 2019:
        return [f"{B}/2019/Proposed/Volume{v}.pdf" for v in (1, 2, 3)]
    n = (1, 2, 3) if year <= 2021 else (1, 2)
    return [f"{B}/{year}/proposed/FY{year}-Volume{v}.pdf" for v in n]


DIGEST = {2027: "https://dbm.maryland.gov/budget/FY2027FiscalDigest/FY2027-Fiscal%20Digest-Entire-Document.pdf"}
# The Legislature's general fund actions, as the conference committee report states them (rounded to $0.1 million):
# https://mgaleg.maryland.gov/Pubs/BudgetFiscal/2026rs-budget-docs-operating-cc-report.pdf, page 1.
LEGISLATIVE_GF = {2027: {"url": "https://mgaleg.maryland.gov/Pubs/BudgetFiscal/2026rs-budget-docs-operating-cc-report.pdf",
                         "reductions": -803.1e6, "additions": 263.8e6}}
SUPP_GF = re.compile(r"(\d{4}) Fiscal Year\s+" + r"\s+".join([r"(\(?-?[\d,]+\)?|-)"] * 6))
SUPPLEMENTALS = {2027: [f"{B}/2027/proposed/FY2027-Supplemental-Budget-No1.pdf", f"{B}/2027/proposed/FY2027-Supplemental-Budget-No2.pdf"]}

PROG = re.compile(r"^([A-Z]\d{2}[A-Z]\d{2}\.\d{2})\s+(\S.*)$")
AMT = r"(\(?-?[\d,]+\)?|-)"
TOTAL = re.compile(rf"^Total Expenditure\s+{AMT}\s+{AMT}\s+{AMT}$")
FUND = re.compile(rf"^(.+?) Expenditure\s+{AMT}\s+{AMT}\s+{AMT}$")
EXCLUDED = ("Reimbursable Fund", "Non-Budgeted Fund")


def amount(s):
    if s in ("-", ""):
        return 0.0
    neg = s.startswith("(") or s.startswith("-")
    x = float(s.strip("()-").replace(",", ""))
    return -x if neg else x


def _get(url, path):
    if path.exists() and path.stat().st_size > 0:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "gmi-savings-tracker crosscheck"})
    with urllib.request.urlopen(req, timeout=600) as r:
        path.write_bytes(r.read())
    return path


def _name(url, year):
    stem = url.rsplit("/", 1)[1].replace("%20", "-")
    return f"FY{year}-{stem}" if not stem.startswith(f"FY{year}") else stem


def text(url, year, layout=False):
    """Download (cached) and extract a PDF's text with pdftotext."""
    pdf = _get(url, CACHE / _name(url, year))
    out = pdf.with_suffix(".layout.txt" if layout else ".txt")
    if not out.exists() or out.stat().st_size == 0:
        subprocess.run(["pdftotext", "-layout" if layout else "-raw", str(pdf), str(out)], check=True, capture_output=True)
    return out.read_text(errors="ignore")


def parse_book(raw):
    """program -> {"name", "total": (actual, appropriation, allowance), fund label: (..)} from each program's first
    appropriation statement (later sections such as deficiencies have one column and are skipped)."""
    out, cur, name, done = {}, None, None, set()
    for line in raw.splitlines():
        line = line.strip()
        m = PROG.match(line)
        if m:
            cur, name = m.group(1), m.group(2)
            continue
        if cur is None or cur in done:
            continue
        t = TOTAL.match(line)
        if t:
            d = out.setdefault(cur, {"name": name})
            if "total" in d:
                done.add(cur)
                cur = None
                continue
            d["total"] = tuple(amount(t.group(i)) for i in (1, 2, 3))
            continue
        f = FUND.match(line)
        if f and cur in out and "total" in out[cur] and not f.group(1).startswith("Total"):
            out[cur].setdefault(f.group(1), tuple(amount(f.group(i)) for i in (2, 3, 4)))
    return {k: d for k, d in out.items() if "total" in d}


def comparable(d, col):
    """Book total expenditure less reimbursable and non-budgeted funds, for column col (0 actual, 1 approp, 2 allowance)."""
    return d["total"][col] - sum(d.get(lab, (0.0, 0.0, 0.0))[col] for lab in EXCLUDED)


def excluded(d, col, label):
    return d.get(label, (0.0, 0.0, 0.0))[col]


def book(year):
    """All programs of a budget year's books (every volume), and the URLs read."""
    progs, urls = {}, volumes(year)
    for u in urls:  # layout text: the raw text splits some program headers from their codes (FY2019: 486 programs raw, 762 layout)
        for k, d in parse_book(text(u, year, layout=True)).items():
            progs.setdefault(k, d)
    return progs, urls


DIGEST_ROW = re.compile(r"^([A-Z]\d{2}[A-Z]\d{2})(\d{2})\s+\d{7,8}\s+.+?\s{2,}" + r"\s+".join([AMT] * 5) + r"\s*$", re.M)
DIGEST_GRAND = re.compile(r"Grand Total\s+" + r"\s+".join([AMT] * 5))
DEFICIENCY_TOTAL = re.compile(r"Total Deficiencies\s+" + r"\s+".join([AMT] * 4))


def digest(year):
    """Fiscal Digest: programs -> (general, special, federal, total, reimbursable); Exhibit B grand totals; enacted deficiencies."""
    t = text(DIGEST[year], year, layout=True)
    progs = {}
    for m in DIGEST_ROW.finditer(t):
        progs.setdefault(f"{m.group(1)}.{m.group(2)}", tuple(amount(m.group(i)) for i in range(3, 8)))
    g = DIGEST_GRAND.search(t)
    d = DEFICIENCY_TOTAL.search(t)
    return progs, tuple(amount(g.group(i)) for i in range(1, 6)) if g else None, tuple(amount(d.group(i)) for i in range(1, 5)) if d else None


SUPP = re.compile(r"(\d{4}) Fiscal Year\s+" + r"\s+".join([AMT] * 6))


def supplemental(url, year):
    """(appropriation by fiscal year, reduction by fiscal year): total funds from the summary statement."""
    t = text(url, year, layout=True)
    s = t[t.rfind("SUPPLEMENTAL APPROPRIATIONS"):]
    add, cut = {}, {}
    part = s.split("Reduction in Appropriation")
    for blk, out in ((part[0], add), (part[1] if len(part) > 1 else "", cut)):
        for m in SUPP.finditer(blk):
            out[int(m.group(1))] = amount(m.group(7))
    return add, cut


def general_supplemental(url, year):
    """General funds added less general funds reduced, by fiscal year, from a supplemental budget's summary statement."""
    t = text(url, year, layout=True)
    s = t[t.rfind("SUPPLEMENTAL APPROPRIATIONS"):]
    out = {}
    for blk in s.split("Reduction in Appropriation")[:2]:
        for m in SUPP_GF.finditer(blk):
            out[int(m.group(1))] = out.get(int(m.group(1)), 0.0) + amount(m.group(2))
    return out


# ------------------------------------------------------------------------------------------------ the data side
def data_programs(con, fy):
    return {k: (a, p, x) for k, a, p, x in con.execute(
        """SELECT agency_code || unit_code || '.' || program_code, any_value(agency_name), any_value(program_name), sum(budget)
           FROM core.fact_budget_all_funds WHERE fiscal_year = ? GROUP BY 1""", [fy]).fetchall()}


def data_funds(con, fy):
    f = dict(con.execute("SELECT fund_type, sum(budget) FROM core.fact_budget_all_funds WHERE fiscal_year = ? GROUP BY 1", [fy]).fetchall())
    gen, spe = f.get("General Funds", 0.0), f.get("Special Funds", 0.0)
    hed = f.get("Current Unrestricted Funds", 0.0) + f.get("Current Restricted Funds", 0.0)
    fed = sum(v for k, v in f.items() if k not in ("General Funds", "Special Funds", "Current Unrestricted Funds", "Current Restricted Funds"))
    return {"General": gen, "Special": spe, "Federal": fed, "Higher education own funds": hed, "Total": sum(f.values())}


def reason(in_book, in_data, diff):
    if not in_book:
        return "In the open data, not printed as a program in the book"
    if not in_data:
        return "Printed in the book, not in the open data"
    if abs(diff) < 100:
        return "Rounding (under $100)"
    return "Amount differs"


def reconcile(con, checked_on=None):
    checked_on = checked_on or dt.date.today().isoformat()
    stage = dict(con.execute("SELECT fiscal_year, stage FROM ref.dim_stage").fetchall())
    rows, diffs = [], []
    actual_years = sorted(y for y, s in stage.items() if s == "Actual" and y + 2 <= 2027)
    for fy in actual_years:
        progs, urls = book(fy + 2)
        data = data_programs(con, fy)
        both = [k for k in progs if k in data]
        exact = sum(abs(comparable(progs[k], 0) - data[k][2]) <= 0.5 for k in both)
        for k in sorted(set(progs) | set(data)):
            b = comparable(progs[k], 0) if k in progs else 0.0
            x = data[k][2] if k in data else 0.0
            if abs(b - x) > 0.5 or (k in data and k not in progs and abs(x) > 0.5):
                diffs.append({"fiscal_year": fy, "program": k, "agency": data[k][0] if k in data else "",
                              "program_name": data[k][1] if k in data else progs[k]["name"], "book": round(b, 2), "data": round(x, 2),
                              "difference": round(x - b, 2), "reason": reason(k in progs, k in data, x - b),
                              "source": f"FY{fy + 2} Governor's budget books"})
        rows.append({"fiscal_year": fy, "stage": stage[fy], "basis": "All funds, operating + higher education",
                     "source_document": f"FY{fy + 2} Governor's budget books (Actual column)", "url": " ".join(urls),
                     "book_total_expenditure": round(sum(d["total"][0] for d in progs.values()), 2),
                     "book_reimbursable": round(sum(excluded(d, 0, "Reimbursable Fund") for d in progs.values()), 2),
                     "book_non_budgeted": round(sum(excluded(d, 0, "Non-Budgeted Fund") for d in progs.values()), 2),
                     "book_comparable": round(sum(comparable(d, 0) for d in progs.values()), 2), "bridge_items": 0.0,
                     "programs_in_both": len(both), "programs_exact": exact, "kind": "reconcile", "checked_on": checked_on})
    # FY2027: the enacted budget, by fund, from the Fiscal Digest's Exhibit B
    for fy in sorted(DIGEST):
        progs, grand, deficiencies = digest(fy)
        data = data_funds(con, fy)
        dp = {k: v for k, v in con.execute(
            """SELECT agency_code || unit_code || '.' || program_code, sum(budget) FILTER (WHERE fund_type NOT IN ('Current Unrestricted Funds', 'Current Restricted Funds'))
               FROM core.fact_budget_all_funds WHERE fiscal_year = ? GROUP BY 1""", [fy]).fetchall() if v}
        both = [k for k in progs if k in dp]
        exact = sum(abs(progs[k][3] - dp[k]) <= 0.5 for k in both)
        for k in sorted(set(progs) | set(dp)):
            b, x = (progs[k][3] if k in progs else 0.0), dp.get(k, 0.0)
            if abs(b - x) > 0.5:
                diffs.append({"fiscal_year": fy, "program": k, "agency": "", "program_name": "", "book": b, "data": x, "difference": x - b,
                              "reason": reason(k in progs, k in dp, x - b), "source": f"FY{fy} Fiscal Digest, Exhibit B"})
        for i, fund in enumerate(("General", "Special", "Federal")):
            rows.append({"fiscal_year": fy, "stage": stage.get(fy), "basis": f"{fund} funds",
                         "source_document": f"FY{fy} Fiscal Digest, Exhibit B (as enacted)", "url": DIGEST[fy],
                         "book_total_expenditure": grand[i] if grand else None, "book_reimbursable": 0.0, "book_non_budgeted": 0.0,
                         "book_comparable": grand[i] if grand else None, "bridge_items": 0.0, "programs_in_both": len(both),
                         "programs_exact": exact, "kind": "reconcile", "checked_on": checked_on})
        # FY2026: the working appropriation, bridged
        prior = fy - 1
        nxt, urls = book(fy)
        approp = sum(comparable(d, 1) for d in nxt.values())
        supp = [supplemental(u, fy) for u in SUPPLEMENTALS.get(fy, [])]
        supp_prior = sum(a.get(prior, 0.0) + c.get(prior, 0.0) for a, c in supp)
        defic = deficiencies[3] if deficiencies else 0.0
        rows.append({"fiscal_year": prior, "stage": stage.get(prior), "basis": "All funds, operating + higher education",
                     "source_document": f"FY{fy} budget books (FY{prior} Appropriation column) + FY{prior} deficiencies as enacted (FY{fy} Fiscal Digest, Exhibit E)",
                     "url": " ".join(urls + [DIGEST[fy]]), "book_total_expenditure": round(sum(d["total"][1] for d in nxt.values()), 2),
                     "book_reimbursable": round(sum(excluded(d, 1, "Reimbursable Fund") for d in nxt.values()), 2),
                     "book_non_budgeted": round(sum(excluded(d, 1, "Non-Budgeted Fund") for d in nxt.values()), 2),
                     "book_comparable": round(approp, 2), "bridge_items": round(defic, 2), "programs_in_both": None, "programs_exact": None,
                     "kind": "bridge", "checked_on": checked_on})
        # FY2027 walk from the allowance: allowance + supplementals -> enacted (the remainder is the Legislature's net action)
        allow = sum(comparable(d, 2) for d in nxt.values())
        supp_fy = sum(a.get(fy, 0.0) + c.get(fy, 0.0) for a, c in supp)
        rows.append({"fiscal_year": fy, "stage": "Governor's allowance + supplementals", "basis": "All funds, operating + higher education",
                     "source_document": f"FY{fy} budget books (Allowance column) + Supplemental Budgets No. 1 and 2",
                     "url": " ".join(urls + SUPPLEMENTALS.get(fy, [])), "book_total_expenditure": round(sum(d["total"][2] for d in nxt.values()), 2),
                     "book_reimbursable": round(sum(excluded(d, 2, "Reimbursable Fund") for d in nxt.values()), 2),
                     "book_non_budgeted": round(sum(excluded(d, 2, "Non-Budgeted Fund") for d in nxt.values()), 2),
                     "book_comparable": round(allow, 2), "bridge_items": round(supp_fy, 2), "programs_in_both": None, "programs_exact": None,
                     "kind": "walk", "checked_on": checked_on})
        _ = supp_prior  # FY2026 items in the supplementals are inside the enacted deficiencies (Exhibit E)
        if fy in LEGISLATIVE_GF:
            gf_allow = sum(d.get("Net General Fund", (0.0, 0.0, 0.0))[2] for d in nxt.values())
            gf_supp = sum(general_supplemental(u, fy).get(fy, 0.0) for u in SUPPLEMENTALS.get(fy, []))
            leg = LEGISLATIVE_GF[fy]
            rows.append({"fiscal_year": fy, "stage": "Allowance + supplementals + legislative actions", "basis": "General funds",
                         "source_document": f"FY{fy} budget books (Allowance), Supplemental Budgets No. 1 and 2, and the conference committee report "
                                            f"(general fund reductions ${-leg['reductions'] / 1e6:,.1f}M, additions ${leg['additions'] / 1e6:,.1f}M, rounded to $0.1M)",
                         "url": " ".join(urls + SUPPLEMENTALS.get(fy, []) + [leg["url"]]), "book_total_expenditure": round(gf_allow, 2),
                         "book_reimbursable": 0.0, "book_non_budgeted": 0.0, "book_comparable": round(gf_allow, 2),
                         "bridge_items": round(gf_supp + leg["reductions"] + leg["additions"], 2), "programs_in_both": None, "programs_exact": None,
                         "kind": "walk", "checked_on": checked_on})
    return pd.DataFrame(rows), pd.DataFrame(diffs)


SITES = {"budget": ("operatingbudget.maryland.gov", "https://operatingbudget.maryland.gov/api/opex/totals.json?year={y}", range(2017, 2028)),
         "payments": ("vendorpayments.maryland.gov", "https://vendorpayments.maryland.gov/api/opex/totals.json?year={y}", range(2008, 2028))}


def site_totals(checked_on=None):
    """Every fiscal year's total from the State's own Open Finance sites (budget and payments), with the URL read."""
    import json
    checked_on = checked_on or dt.date.today().isoformat()
    rows = []
    for name, (host, url, years) in SITES.items():
        for y in years:
            u = url.format(y=y)
            for attempt in range(5):  # self-healing: the sites reset connections now and then
                try:
                    req = urllib.request.Request(u, headers={"User-Agent": "gmi-savings-tracker crosscheck"})
                    with urllib.request.urlopen(req, timeout=60) as r:
                        total = float(json.loads(r.read())[0]["amount"])
                    break
                except Exception:  # noqa: BLE001 - retried, then raised
                    if attempt == 4:
                        raise
                    time.sleep(2 ** attempt)
            rows.append({"dataset": name, "fiscal_year": y, "site_total": total, "host": host, "url": u, "checked_on": checked_on})
    return pd.DataFrame(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="compare only; write nothing")
    a = ap.parse_args(argv)
    if not shutil.which("pdftotext"):
        print("books: pdftotext (poppler) is required", file=sys.stderr)
        return 2
    con = duckdb.connect(str(DB), read_only=True)
    rec, diffs = reconcile(con)
    print(rec[["fiscal_year", "stage", "basis", "book_comparable", "bridge_items", "programs_in_both", "programs_exact", "kind"]].to_string(index=False))
    if not a.check:
        rec.to_csv(ROOT / "reference" / "book_reconciliation.csv", index=False, lineterminator="\n")
        sites = site_totals()
        sites.to_csv(ROOT / "reference" / "site_totals.csv", index=False, lineterminator="\n")
        print(f"books: wrote reference/site_totals.csv ({len(sites)} years)")
        diffs.to_csv(ROOT / "reference" / "book_program_differences.csv", index=False, lineterminator="\n")
        print(f"books: wrote reference/book_reconciliation.csv ({len(rec)} rows) and reference/book_program_differences.csv ({len(diffs)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
