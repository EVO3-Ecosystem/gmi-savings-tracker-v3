"""Every reported savings figure carries its source and date, the two sources are never mixed, and the figures match the quotes."""
import pandas as pd
import pytest

from src.models import claims as C


@pytest.fixture(scope="module")
def df():
    return C.build()


def test_every_figure_names_a_known_source_with_a_date(df):
    src = C.sources()
    assert set(df.source_id) <= set(src.index)
    assert df.source_title.notna().all() and (df.url.str.startswith("https://")).all()
    # each source has a document date or an as-of date, or says 'undated'; every source has the date it was retrieved
    assert ((df.source_date != "") | (df.as_of != "")).all() and (df.retrieved != "").all()
    assert df.claim_id.is_unique


def test_every_figure_has_the_words_it_came_from(df):
    page = df[df.source_id == "GOVPAGE_2026_06"]
    assert (page.quote.str.len() > 15).all()
    # the amount appears in the quote, as dollars or as 'N million' (a figure is never typed without its words)
    for r in page.itertuples():
        m = r.amount_low / 1e6
        forms = {f"${m:g} million", f"${m:g}M", f"${r.amount_low:,.0f}", f"${r.amount_low / 1e3:g},000"}
        if r.claim_id.endswith(("G04",)):  # $600,000 + $200,000
            forms |= {"$600,000"}
        assert any(f in r.quote for f in forms), (r.claim_id, r.quote)


def test_page_items_map_to_real_january_items(df):
    jan = set(df[df.source_id != "GOVPAGE_2026_06"].saving_id)
    for ids in df[(df.source_id == "GOVPAGE_2026_06") & (df.saving_id != "")].saving_id:
        assert set(ids.split(";")) <= jan, ids


def test_the_two_headline_totals_are_kept_apart(df):
    page_total = df[df.claim_id == "GOVPAGE_2026_06-G00"].amount_low.iloc[0]
    jan_saved = df[(df.source_id == "JCR_2026_01") & df.basis.str.contains("Saved in FY2026")].amount_low.sum()
    assert page_total == 50_000_000
    assert jan_saved == pytest.approx(29_000_000, abs=1_000_000)  # the January report's own $29M
    # no row mixes the two: every figure has exactly one source
    assert df.groupby("claim_id").source_id.nunique().eq(1).all()


def test_compare_lines_up_the_laptop_items_and_flags_differences(df):
    c = C.compare(df).set_index("saving_id")
    assert c.loc["S13;S14", "january_low"] == 3_000_000 == c.loc["S13;S14", "page_amount"]
    assert c.loc["S11", "page_amount"] > c.loc["S11", "january_high"]
    assert pd.isna(c.loc["S02", "january_low"]) and c.loc["S02", "page_amount"] == 12_900_000


def test_the_table_is_published():
    from src import published as P
    assert P.has("d_reported_claims") and len(P.load("d_reported_claims")) == len(C.build())
