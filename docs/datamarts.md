# Maryland portal datamarts: FY2017–FY2027

The datamart bundle includes every API row in the requested fiscal-year window across the six state financial feeds and the county school-board disclosure feed linked by the [Maryland Transparency Portal](https://mtp.maryland.gov/#!/dashboard). These are source-grain records, not dashboard aggregates. Maryland does not publish all 11 years in every feed.

## Source coverage

The ranges below came from SODA `count(*)` queries grouped by each source's fiscal-year field on November 19, 2026, rather than from dataset titles. Re-run the pipeline for current values; `published` means rows exist, not that every underlying transaction or institution is represented.

| Datamart | Live years in scope | Gaps and caveats |
|---|---|---|
| [`budget`](https://opendata.maryland.gov/d/yu65-jmmv) | FY2017–FY2027 | FY2026 is a working budget and FY2027 is a legislative appropriation, not actuals. |
| [`fund`](https://opendata.maryland.gov/d/gy87-e27x) | FY2017–FY2027 | Budget by funding source, not payments. |
| [`fte`](https://opendata.maryland.gov/d/x8qy-486w) | FY2017–FY2027 | Budgeted FTEs, not employee headcounts. |
| [`highered`](https://opendata.maryland.gov/d/4mca-332u) | FY2017–FY2027 | Separate from the GMI baseline. |
| [`payments`](https://opendata.maryland.gov/d/7syw-q4cy) | FY2017–FY2027 | FY2027 is partial. The source is annual payee aggregates, not payment transactions. |
| [`grants`](https://opendata.maryland.gov/d/absk-avps) | FY2017–FY2025 | No FY2026–FY2027 rows in this feed. |
| [`school_spending`](https://opendata.maryland.gov/d/t6vk-rvwe) | FY2017–FY2025 | FY2017 (4 reporting units), FY2018 (14) and FY2025 (23 versus 24 in FY2024) are partial. No FY2026–FY2027 rows. Never add these county disclosures to State vendor payments. |

## Extract, query and export

```sh
make datamarts
# Optional: choose a new destination and pull just one feed.
make datamarts DATAMART_FLAGS='--dataset grants --output data/datamarts/grants-review'
# Optional: reuse an existing, up-to-date analytics build without contacting SODA.
make datamarts DATAMART_FLAGS='--from-warehouse'
```

- **Direct pull**: `make datamarts` sends the FY2017–FY2027 filter to SODA for the count, yearly totals and every page, so previous fiscal years are not downloaded. It skips enrichment, model training and the dashboard build. Every file is verified against the filtered portal counts, totals and source revision before the bundle is made available.
- **Full analytics pipeline**: `make all` retains its native history to keep legacy analyses and reconciliations reproducible. `data/raw/<run_id>/` holds native Parquet files, `manifest.json`, and `coverage.csv`. The new FY2017–FY2027 scope applies to the datamart views and direct bundle, not to those legacy inputs.
- **Warehouse**: `datamart.<name>` filters on the source's native fiscal-year field; `datamart.coverage` has one row per configured source and requested year. The `mart` schema and GMI formulas still use their existing sources and definitions. `grants` uses `fiscalyear`, not `fiscal_year`.
- **Bundle**: `data/datamarts/<run_id>/` holds seven Parquet files and a coverage CSV by default. Direct pulls include `manifest.json`; exports from the warehouse preserve each row's `_run_id` instead. The scheduled workflow verifies a warehouse export locally and retains only coverage and run metadata as evidence, not the row-level bundle.
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
