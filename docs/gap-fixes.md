# Gap fixes — November 19, 2026

Every known gap, its fix, and where it stands. Rule for the open year: **FY2027 payments (partial year) are published everywhere,
tagged FYTD (fiscal year to date), and never compared with a completed year** — this is a live tracking tool, so
nothing is held back; a partial year is labeled, not dropped.

## 1. FY2027 payments (partial year) were hidden (fixed in this PR)

| # | Gap | Where it was | Fix | Files |
|---|---|---|---|---|
| F1 | The export **dropped** FY2027 rows from the vendor, payee-type and vendor-year tables | `src/pipeline/export.py` (`PARTIAL` dict, `hold = True`) | Every payment table now publishes the open year with `partial_year = true`; `_yoy` columns are emptied on partial rows only | `src/pipeline/export.py` |
| F2 | The export **emptied** FY2027 (partial year) `payee_spend` (areas) and `payments` (agencies) | same | Same flag-and-publish treatment; values are kept | `src/pipeline/export.py` |
| F3 | The dashboard defaulted payments views to FY2026 with no FY2027 treatment | `legacy/gst/page/index.html` | FYTD surfacing everywhere payments appear: the Overview payments tile, the vendor ledger note, the budget-vs-payments note all show "FY2027 FYTD: $18.1B (fiscal year to date)"; charts still compare completed years only | `legacy/gst/page/index.html` |
| F4 | `payments_latest_fy_usd` silently returned the **partial** year as "latest" | `config/metrics.yml` | Metric now reads the latest **completed** year; new metric `payments_fytd_usd` publishes the FYTD figure explicitly, labeled partial | `config/metrics.yml`, `sql/mart/10_totals_by_fy.sql` |
| F5 | Savings checks would have compared FY2026 full-year against FY2027 partial once the year rolled | `src/models/savings.py`, `config/assumptions.yaml` | Checks run only on the two completed years (`before_fy`/`after_fy`); `tracking_fy: 2027` adds `fytd_paid` to `d_savings_status` — shown, never verdicted | `src/models/savings.py`, `config/assumptions.yaml` |
| F6 | Savings tracker table had no live FY2027 view | `legacy/gst/page/index.html` | New "FY2027 FYTD" column (computed per check from `f_savings_check`, respects the agency filter); FY2026 reported savings stay measured on completed years, FY2027 projections stay separate | `legacy/gst/page/index.html` |
| F7 | "GMI's $50M FY2026 target" wording | Overview lede | The target is yearly; the page now says FY2027 and the tracker lede explains FY2026-reported vs FY2027-tracking | `legacy/gst/page/index.html` |
| F8 | `d_vendor_moves` columns were hardcoded `fy2024/fy2025/fy2026` | `src/models/savings.py` | Column names follow `vendor_moves.years` in config (completed years only); the page table derives its year columns and headers from the data | `src/models/savings.py`, `legacy/gst/page/index.html` |

Verification: 481 tests pass (savings, metrics, site, marts, catalog, recommendations, opportunities, notebook); the site
builds from the checked-in snapshot; the new mart SQL was executed against a mock warehouse; the FYTD page logic was
smoke-tested. The checked-in `site_data/` already carries FY2027 rows in `f_savings_check` and `totals_by_fy`, so the
Savings tracker FYTD column and the Overview FYTD note work today; the vendor/area/agency tables fill in on the next
pipeline run (scheduled December 3, or manual: Actions → Extract and build, then `make export && make site-snapshot`).

## 2. Rollover debt — config-pinned, revisit when FY2027 completes (June 30, 2027)

| # | Gap | Why it is safe today | What to do at rollover |
|---|---|---|---|
| R1 | `d_bid_list`, `d_vendors`, `d_vendor_names` year columns are literally named `fy2025`/`fy2026` | `opportunities.payments_fy` is pinned to the last completed year (2026) and documented as such | Move `payments_fy`, `matched_fy`, `names_fy`, `before_fy`/`after_fy`, `tracking_fy`, `vendor_moves.years` forward **together**, rename the output columns to the new years, and update `checks.py` (d_bid_list/d_vendor_names column references) and the bid-list tiles in one PR |
| R2 | Bid-list tiles and notes say "FY2026" in prose | Same pin as R1 | Reword with the new completed year (or make them read the year from the data) |
| R3 | `counted_status: [Saved in FY2026, Under way]` names FY2026 | The January 2026 report's own wording | Re-derive from the next GMI report's statuses |

## 3. Source-side gaps (cannot be fixed in this repo; handling is documented)

| # | Gap | Standing handling |
|---|---|---|
| S1 | FY2010–FY2016 payments history is not on the portal (archival hole) | Documented in the datamart map (wiki, PR #31); charts start where the data starts and say so |
| S2 | Payments and grants are annual aggregates — no monthly or invoice timing | Repo rule: no timing analysis; FYTD is always labeled, never annualized |
| S3 | FY2022 double-published payments (MDTA/MES, $874.5M) | Detected and published as a source issue (`d_source_issues`); excluded from detectors; fix belongs to the portal |
| S4 | County school spending is a different fund stream | Never added to State vendor payments (repo rule); candidate dataset stays unpinned |

## 4. Open roadmap gaps (from the wiki gap analysis, PR #31)

| # | Gap | Status |
|---|---|---|
| O1 | eMM bid-family datasets (8 DGS per-FY feeds) not extracted | Next extraction task. All 8 IDs confirmed on the portal (Nov 20, 2026): FY2012 d7pu-ebad, FY2013 n4xa-2zgn, FY2014 itax-4ccz, FY2015 3hzs-sazv, FY2016 7ang-84wj, FY2017 qkjf-rv4t, FY2018 pgna-cxjh, FY2019 ttg5-zfzj, plus the eMM Grouping view 3tu2-tyav. The portal has no FY2020 eMM bid feed; the wiki's FY2020 entry is wrong (bids moved to eMMA) |
| O2 | Wiki not yet wired into the Pages nav | Pending PR #31 merge |
| O3 | SODA 3.0 migration | Not started; 2.1 serves all pinned feeds tokenless |
| O4 | Catalog-diff automation (new/retired datasets each run) | Proposed; freshness workflow covers update dates only |
| O5 | Unmerged datamart branches (PR #30, `feat/fy2009-2027-datamarts`) | Review/merge/close decision pending |
| O6 | Dimensional-model gaps G1–G7 (grain asymmetry, conformed dims, SCD2, agency aliases, spending-side expenditure type, FY typing, `fiscal_period`) | Tracked in the wiki's dimensional review; layering rule: no dimensional modeling in Bronze, conformance in Silver, star schemas in Gold |
