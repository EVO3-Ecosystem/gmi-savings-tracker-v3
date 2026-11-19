# Datamart map, FY2010–FY2027

Built from a full scan of the Socrata Discovery (catalog) API on **November 19, 2026**: 1,519 datasets on `opendata.maryland.gov` plus 9 public datasets on the separate `internaldata.maryland.gov` domain. The scan enumerated every finance-relevant keyword family exhaustively and counted the rest; keyword-match counts (`q=`): budget 22, payments 25, emaryland 8, contract 15, revenue 15, tax 53, travel 18, positions 68 (mostly non-financial noise). Fiscal-year coverage below comes from each dataset's declared `Time-Period-of-Content`, its title, and — for the six pinned feeds — the pipeline's own year-by-year portal checks. This page extends the bundle design in [docs/datamarts.md](../datamarts.md) (branch `feat/fy2009-2027-datamarts`).

Machine-readable form: [`reference/datamart_catalog.csv`](../../reference/datamart_catalog.csv).

## 1. Core financial datamarts

The feeds the tracker is built on (six pinned in `config/datasets.yaml`) plus the county school-board feed carried in the datamart-bundle branch.

| Datamart | Portal ID | Live years | Grain | Update | In extract config |
|---|---|---|---|---|---|
| Operating budget | [`yu65-jmmv`](https://opendata.maryland.gov/d/yu65-jmmv) | FY2017–FY2027 | Program × object × fund, by budget stage | Annually | Yes (`budget`) |
| Funding source | [`gy87-e27x`](https://opendata.maryland.gov/d/gy87-e27x) | FY2017–FY2027 | Program × fund source | Annually | Yes (`fund`) |
| Payments | [`7syw-q4cy`](https://opendata.maryland.gov/d/7syw-q4cy) | FY2008–FY2027 (FY2027 partial) | **Annual totals per payee**, not transactions | Monthly | Yes (`payments`) |
| Grants and loans | [`absk-avps`](https://opendata.maryland.gov/d/absk-avps) | FY2009–FY2025 | Annual totals per recipient | Annually | Yes (`grants`) |
| Budgeted FTEs | [`x8qy-486w`](https://opendata.maryland.gov/d/x8qy-486w) | FY2017–FY2027 | Agency × program, budgeted FTEs (fractional) | Annually | Yes (`fte`) |
| Higher ed (CUR/CR) | [`4mca-332u`](https://opendata.maryland.gov/d/4mca-332u) | FY2017–FY2027 | Program × object, current restricted/current funds | Annually | Yes (`highered`) |
| County school spending | [`t6vk-rvwe`](https://opendata.maryland.gov/d/t6vk-rvwe) | FY2010–FY2025 (see flags) | Annual payee ≥ $25k per school board | Annually | **No** — in the datamart branch only |

School-spending coverage flags (from the publisher): FY2019 is the first year all counties report; Montgomery and Howard reach FY2010, Baltimore County and Prince George's FY2012; FY2010–FY2018 cover 2–14 reporting units; FY2025 had 23 of 24. **Never add these county disclosures to State vendor payments.**

## 2. Procurement bids: the eMaryland Marketplace family

The largest finding of the scan. The portal holds the Department of General Services' eMaryland Marketplace (eMM) bid data as **one static dataset per fiscal year** — 8 datasets in the catalog. Bid-level records: bid number, NIGP class/item codes, purchase method, bid type, buyer, organization, blanket dates, attachments, quantities.

| Fiscal year | Portal ID | Verified in scan |
|---|---|---|
| FY2014 | [`itax-4ccz`](https://opendata.maryland.gov/d/itax-4ccz) | Yes |
| FY2015 | [`3hzs-sazv`](https://opendata.maryland.gov/d/3hzs-sazv) | Yes |
| FY2016 | [`7ang-84wj`](https://opendata.maryland.gov/d/7ang-84wj) | Yes |
| FY2017 | [`qkjf-rv4t`](https://opendata.maryland.gov/d/qkjf-rv4t) | Yes |
| FY2018 | [`pgna-cxjh`](https://opendata.maryland.gov/d/pgna-cxjh) | Yes |
| FY2019 | [`ttg5-zfzj`](https://opendata.maryland.gov/d/ttg5-zfzj) | Yes |
| 2 more in the result set | — | IDs not captured before the API response truncated; pin by `q=emaryland` before configuring |

Relevance: GMI's savings claim includes statewide-contract consolidation, and the anomaly model already uses a **bid list** baseline (`d_bid_list`). Today that list is a small reference file; the eMM family is the full source-grain feed behind it. Schemas drift slightly year to year (column order, `Text` vs `Number` typing on dates), so each year needs the same per-file manifest treatment as the current feeds. eMM was succeeded by eMaryland Marketplace Advantage (eMMA); no eMMA award-level dataset appears on the portal — that absence is itself a gap-analysis item.

## 3. FY2010–FY2027 coverage matrix

● published · ◐ partial or flagged · — no rows in scope

| Datamart | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 | 21 | 22 | 23 | 24 | 25 | 26 | 27 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| budget | — | — | — | — | — | — | — | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● |
| fund | — | — | — | — | — | — | — | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● |
| fte | — | — | — | — | — | — | — | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● |
| highered | — | — | — | — | — | — | — | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● |
| payments | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ◐ |
| grants | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | — | — |
| school_spending | ◐ | ◐ | ◐ | ◐ | ◐ | ◐ | ◐ | ◐ | ◐ | ● | ● | ● | ● | ● | ● | ● | — | — |
| emm_bids (family) | — | — | — | — | ● | ● | ● | ● | ● | ● | ● | — | — | — | — | — | — | — |

Budget-stage caveat: FY2026 is a working budget and FY2027 a legislative appropriation in the budget-family feeds; neither is actuals. The stage labels come from DBM's budget books via `reference/budget_stage.csv`, not the portal's stale descriptions.

## 4. Candidate and context datasets

Finance-adjacent feeds surfaced by the scan. None is a drop-in savings datamart; each is listed with its plausible use.

| Dataset | Portal ID | Coverage | Plausible use |
|---|---|---|---|
| DHCD performance metrics | `tay4-rqsd` | FY2011–FY2025 | Context: loan-program output beside grants |
| MDAg manure transport financials | `3472-a3iv` | FY2005–FY2016 | Cost-share payments, static |
| Historic clean energy grant awards | `4jem-ugpy` | to 2015 | Grant history, static |
| MTA operating cost per revenue mile | `tmp8-b5cn` | FY2011–FY2015 | Unit-cost benchmark pattern |
| County school spending | `t6vk-rvwe` | FY2010–FY2025 | Local education spend (see flags) |
| Managing for Results family (e.g. DJS `xtmn-cgpa`) | various | FY2011+ | Performance measures; repo already reads MFR plans from DBM instead |
| Jobs by industry / jurisdictions (MDP) | `szeq-nd9z`, `sjzx-yjzi` | 2010–2020, 1970–2050 | Macro context only; BEA products discontinued |
| Choose Maryland compare-states | `tjqn-cex9`, `t833-r94z` | varies | Cross-state context, not State operations |
| Unemployment insurance metrics | `3x6e-7i3k` | 2008–2013 | Static history |
| Annual vehicle miles of travel | `exua-btti` | 1980–present | Context |

The `internaldata.maryland.gov` domain shows 9 public datasets (COVID-era operations). The payments dataset's description says per-fiscal-year mirrors live there, but they are not public in the catalog — treat them as inaccessible and keep the single combined feed as the source of truth.

## 5. What FY2010–FY2016 cannot come from the portal

For the budget, funding-source, FTE and higher-education feeds there is **no comparable pre-FY2017 API feed**. DBM's archived budget documents and Fiscal Digests cover those years in print form; an archival backfill needs its own schema and stage mapping, reconciled against those documents — never mixed into the current feeds, and never substituting approved appropriations for actual spending. This is the single largest structural hole in the FY2010–FY2027 window and it is a document-extraction project, not an API project.
