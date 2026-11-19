# Maryland portal datamarts: FY2009–FY2027

The datamart bundle includes every API row in the requested fiscal-year window across the six state financial feeds and the county school-board disclosure feed linked by the [Maryland Transparency Portal](https://mtp.maryland.gov/#!/dashboard). These are source-grain records, not dashboard aggregates. Maryland does not publish all 19 years in every feed.

## Source coverage

The ranges below came from SODA `count(*)` queries grouped by each source's fiscal-year field on November 19, 2026, rather than from dataset titles. Re-run the pipeline for current values; `published` means rows exist, not that every underlying transaction or institution is represented.

| Datamart | Live years in scope | Gaps and caveats |
|---|---|---|
| [`budget`](https://opendata.maryland.gov/d/yu65-jmmv) | FY2017–FY2027 | No comparable FY2009–FY2016 feed; FY2026 is a working budget and FY2027 is a legislative appropriation, not actuals. |
| [`fund`](https://opendata.maryland.gov/d/gy87-e27x) | FY2017–FY2027 | No FY2009–FY2016 funding-source rows in this feed. |
| [`fte`](https://opendata.maryland.gov/d/x8qy-486w) | FY2017–FY2027 | No FY2009–FY2016 rows in this feed; values are budgeted FTEs, not employee headcounts. |
| [`highered`](https://opendata.maryland.gov/d/4mca-332u) | FY2017–FY2027 | No FY2009–FY2016 rows in this feed; separate from the GMI baseline. |
| [`payments`](https://opendata.maryland.gov/d/7syw-q4cy) | FY2009–FY2027 | FY2027 is partial. FY2008 remains in the native warehouse but is outside the bundle. The source is annual payee aggregates, not payment transactions. |
| [`grants`](https://opendata.maryland.gov/d/absk-avps) | FY2009–FY2025 | No FY2026–FY2027 rows in this feed; the source includes loans starting in FY2010. |
| [`school_spending`](https://opendata.maryland.gov/d/t6vk-rvwe) | FY2010–FY2025 | FY2010–FY2018 cover 2–14 reporting units; FY2025 had 23 versus 24 in FY2024. Those years are flagged partial. No FY2009 or FY2026–FY2027 rows. Never add these county disclosures to State vendor payments. |

Maryland's [archived operating budget documents](https://dbm.maryland.gov/public/pages/statebudget.aspx) and [Fiscal Digests](https://dbm.maryland.gov/budget/Pages/operbudget/Fiscal-Digest.aspx) cover older years but are not equivalent to the current line-item, funding-source, FTE and higher-education feeds. An archival backfill needs its own schema and fiscal-stage mapping, with separate reconciliation against those documents. Do not mix it into the current feeds or substitute approved appropriations for actual spending.

## Extract, query and export

```sh
make all
make datamarts
# Optional: choose a new destination (an existing bundle is never overwritten).
make datamarts DATAMART_FLAGS='--output data/datamarts/fy2009-2027-review'
```

- **Extract**: `data/raw/<run_id>/` holds native Parquet files, `manifest.json`, and `coverage.csv`. Each file is checked against the portal's overall count, year-by-year counts and totals, and update timestamp before it can be reused or built. A scoped FY2009–FY2027 export does not discard native source history.
- **Warehouse**: `datamart.<name>` filters on the source's native fiscal-year field; `datamart.coverage` has one row per configured source and requested year. The `mart` schema and GMI formulas still use their existing sources and definitions. `grants` uses `fiscalyear`, not `fiscal_year`.
- **Bundle**: `data/datamarts/<run_id>/` holds seven Parquet files and the coverage CSV. All fields returned by the source extract are kept, plus `_run_id` for lineage. The scheduled workflow verifies the bundle locally and retains only the coverage manifest as run evidence, not the row-level bundle.
- **Status**: `not_published` means no source rows for that year at extract time, with a blank count and total, not zero. `partial` identifies a known reporting gap or open year. `not_loaded` identifies a source missing from an older build, and `extract_failed` identifies a failed validation. Review the configured partial-year flags when the publishers release new data.

```sql
SELECT dataset, fiscal_year, status, portal_rows, portal_total
FROM datamart.coverage
WHERE status <> 'published'
ORDER BY dataset, fiscal_year;
```

## Developer references

- **Read API**: the [SODA endpoint guide](https://dev.socrata.com/docs/endpoints) distinguishes the working public SODA 2.1 `GET /resource/<id>.json` from the SODA3 query endpoint, which requires user authentication or a valid token. A disabled documentation TryIt widget does not disable the data API.
- **Pagination and rate limits**: the [paging guide](https://dev.socrata.com/docs/paging.html) recommends explicit ordering; the extractor uses `$order=:id`, `$limit`, and `$offset`. The [application-token guide](https://dev.socrata.com/docs/app-tokens.html) explains how an optional `MD_SODA_APP_TOKEN` raises SODA 2.1 request limits without changing data coverage.
- **Discovery and metadata**: use the [catalog API](https://dev.socrata.com/docs/other/discovery) and [metadata API](https://dev.socrata.com/docs/other/metadata) to find candidate inputs and inspect them. Keep the production source IDs pinned in `config/datasets.yaml`; never add a catalog result automatically.
