"""Every reported savings figure, one row per figure, tagged with the source it came from and that source's date.

GMI's savings are reported in more than one place, and the places do not agree (the January 2026 Joint Chairmen's
Report gives $29M saved in FY2026 against a $50M target; the Governor's Government Modernization Initiative page says GMI
has "implemented actions to save $50 million as of June 2026"). So the tracker never keeps a bare number: each figure
carries its source, its date (or 'undated' with the date it was retrieved), what the source says it counts (`basis`) and the exact words.

Inputs (all under reference/):
  gmi_reported_savings.csv    the January 2026 report's items (and one DGS item), the basis of d_savings
  gmi_public_page_claims.csv  the figures on the Governor's page, each with a verbatim quote
  claim_sources.csv           the sources: title, publisher, URL, document date, as-of date, retrieval date

Builds mart.d_reported_claims (src/models/savings.py writes it). `compare` lines up the two sources item by item.
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / "reference"
COLUMNS = ["claim_id", "source_id", "source_title", "source_date", "as_of", "retrieved", "saving_id", "item", "amount_low", "amount_high", "basis",
           "mapping", "quote", "page", "url"]
JCR_SOURCE = {"DBM, Government Modernization Initiative Final Report (Joint Chairmen's Report p. 77), Jan 26, 2026": "JCR_2026_01",
              "DGS, Government Modernization: right-sizing State facilities": "DGS_FACILITIES"}


def sources(ref=None):
    return pd.read_csv((ref or REF) / "claim_sources.csv", keep_default_na=False).set_index("source_id")


def build(ref=None):
    """All reported figures, long format: one row per figure per source."""
    ref = ref or REF
    src = sources(ref)
    rep = pd.read_csv(ref / "gmi_reported_savings.csv", keep_default_na=False)
    page = pd.read_csv(ref / "gmi_public_page_claims.csv", keep_default_na=False)
    rows = []
    for r in rep.to_dict("records"):
        sid = JCR_SOURCE[r["source"]]
        rows.append({"claim_id": f"{sid}-{r['saving_id']}", "source_id": sid, "saving_id": r["saving_id"], "item": r["item"],
                     "amount_low": r["reported_low"], "amount_high": r["reported_high"], "basis": f"{r['type']}; {r['status']}",
                     "mapping": "", "quote": r["source_quote"], "page": r["source_page"]})
    for r in page.to_dict("records"):
        rows.append({"claim_id": f"GOVPAGE_2026_06-{r['claim_id']}", "source_id": "GOVPAGE_2026_06", "saving_id": r["saving_id"], "item": r["item"],
                     "amount_low": r["amount_low"], "amount_high": r["amount_high"], "basis": r["basis"], "mapping": r["mapping"],
                     "quote": r["quote"], "page": ""})
    df = pd.DataFrame(rows)
    for col in ("amount_low", "amount_high"):
        df[col] = pd.to_numeric(df[col].replace("", None), errors="coerce")
    df["source_title"] = df.source_id.map(src.title)
    df["source_date"] = df.source_id.map(src.document_date)
    df["as_of"] = df.source_id.map(src.as_of)
    df["retrieved"] = df.source_id.map(src.retrieved)
    df["url"] = df.source_id.map(src.url)
    return df[COLUMNS]


def compare(claims):
    """One row per January-report item that the Governor's page also describes (mapping 'same item' or 'likely ...').

    The page's figure is summed over the page claims mapped to that item; a page claim that names two items
    (saving_id 'S13;S14') is shown against the sum of the January figures of both. Unmatched items are left out here."""
    jan = claims[claims.source_id.isin(["JCR_2026_01", "DGS_FACILITIES"])].set_index("saving_id")
    page = claims[(claims.source_id == "GOVPAGE_2026_06") & (claims.saving_id != "")]
    out = []
    for ids, g in page.groupby("saving_id", sort=False):
        keys = ids.split(";")
        lo = jan.loc[keys, "amount_low"].sum(min_count=1)
        hi = jan.loc[keys, "amount_high"].sum(min_count=1)
        out.append({"saving_id": ids, "item": g.item.iloc[0], "january_low": lo, "january_high": hi,
                    "january_basis": "; ".join(jan.loc[keys, "basis"]), "page_amount": g.amount_low.sum(), "page_basis": "; ".join(g.basis),
                    "mapping": "; ".join(sorted(set(g.mapping)))})
    return pd.DataFrame(out)
