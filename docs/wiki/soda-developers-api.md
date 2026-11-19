# SODA Developers API reference

Distilled from [dev.socrata.com](https://dev.socrata.com/) on November 19, 2026, for the GMI Savings Tracker dev team. Socrata was acquired by Tyler Technologies in 2018 and is now Tyler's Data and Insights division; the platform is the same software, with "Data & Insights" branding in places. The developer site is mid-upgrade to SODA3 — its inline TryIt widgets are disabled, which affects only the documentation widgets, **not** the data API.

## 1. Platform orientation

- Every Socrata dataset has a built-in API. Find the endpoint on the dataset page under **Export → API**, or via the **API** button on a DataLens view.
- Dataset identifiers are eight alphanumeric characters split by a dash (for this project: `yu65-jmmv`, `7syw-q4cy`, and the others pinned in `config/datasets.yaml`).
- The same catalog that powers the Open Data Network is available programmatically through the **Discovery API** (section 8) — that is what the FY2010–FY2027 [datamart map](datamart-map-fy2010-2027.md) was built from.

## 2. Endpoint versions

| Version | Endpoint shape | Status for this project |
|---|---|---|
| 3.0 (latest) | `/api/v3/views/<id>/query.json` and `/api/v3/views/<id>/export.csv` | Released in 2025. **Requires** user authentication or a valid app token. `POST` preferred (longer queries, clearer options). Split into `/query` (machine-tunable: `query`, `page`, `timeout`, `includeSystem`, `includeSynthetic`, `orderingSpecifier`) and `/export` (human formats, `serializationOptions`). Migration target; see the roadmap's "Move the extract to SODA3" item |
| 2.1 | `/resource/<id>.json` | **What the extract uses today** through `sodapy`; works without a token. Released April 2015, designated 2.1 in November 2015. Tyler says it remains fully supported |
| 2.0 | `/resource/<id>.json` | Legacy (2011). Detect it via the `X-SODA2-Legacy-Types: true` response header. Fewer SoQL functions; only the `Location` geospatial type; case-insensitive text |

Version differences that matter when querying:

- 2.1 added the geospatial types `Point`, `Line`, `Polygon` (replacing `Location`), GeoJSON output, and SQL-closer semantics — **text comparisons are case-sensitive in 2.1**, case-insensitive in 2.0.
- New SoQL functions and datatypes arrive non-breaking; old queries keep working.

## 3. SoQL queries

SoQL borrows SQL's shape but runs entirely through request parameters (2.x) or the `query` option (3.0). There is no `FROM` — the view is the data source.

```sql
SELECT `agency_name`, sum(`amount`) AS `total`
WHERE `fiscal_year` = 2025
GROUP BY `agency_name`
HAVING `total` > 1000000
ORDER BY `total` DESC
```

Clauses: `SELECT` (with `AS` renaming; backtick column names), `WHERE` (`AND`, `OR`, `NOT`, `IS NULL`, `IS NOT NULL`, parentheses), `GROUP BY` + `HAVING`, `ORDER BY` (`ASC`/`DESC`), `LIMIT`/`OFFSET` (prefer the 3.0 `page` parameter). Comments work (`--`, `//`, `/* */`) but are not guaranteed preserved.

### Function and keyword listing (2.1 and 3.0 unless noted)

Aggregates: `avg`, `count`, `sum`, `min`, `max`, `stddev_pop`, `stddev_samp`, `extent`, `convex_hull` — plus `regr_intercept`, `regr_r2`, `regr_slope` for linear fits. (`avg`, `count`, `date_trunc_*` and `within_*` also exist in 2.0.)

Date: `date_extract_y/m/d/hh/mm/ss`, `date_extract_dow`, `date_extract_woy`, `date_trunc_y/ym/ymd`.

Text: `upper`, `lower`, `unaccent`, `starts_with`, `like`, `not like`, `in`, `not in`, `between`, `not between`, `case`, `greatest`, `least`.

Geospatial: `within_box`, `within_circle`, `within_polygon`, `intersects`, `distance_in_meters`, `num_points`, `simplify`, `simplify_preserve_topology`.

Full-text: the `$q` parameter searches across all text fields (2.x). Reserved SoQL keywords used as identifiers need escaping.

## 4. Paging

- Pages are capped at **50,000 records**; use `$limit` and `$offset` (2.x) or `page: {pageNumber, pageSize}` (3.0).
- Always page with an explicit, stable order. The extractor uses `$order=:id` — the internal row identifier is unique and immutable, which makes offset paging safe against mid-download inserts.
- This repo sets `page_size: 20000` in `config/datasets.yaml`: 50,000-row pages were observed to drop mid-download without an app token.

## 5. Application tokens and throttling

- Without a token, requests share a per-IP pool and are throttled; the response on throttle is **HTTP 429**.
- With a token, usage is attributed to the application; Socrata states it does not currently throttle tokened requests unless abusive. (The older "1,000 requests per rolling hour" language has been relaxed, but design as if limits exist — the "don't be a jerk" rule is literal.)
- Pass the token as the `X-App-Token` HTTP header (preferred; all versions) or `$$app_token` (2.x). Always over HTTPS: a leaked token lets someone else spend your quota.
- In this repo the token is the `MD_SODA_APP_TOKEN` secret (optional for SODA 2.1, **required for SODA3**). It is a repository/Actions secret — GitHub never returns secret values through the API, so only CI workflows and local `.env` files can use it. A rejected token is dropped with a warning; the datasets themselves are public.

## 6. System fields and change detection

| Field | Meaning |
|---|---|
| `:id` | Internal row identifier (the extractor's paging key) |
| `:created_at` | When the record was created (fixed timestamp) |
| `:updated_at` | When the record was last modified |

- 2.1: select them explicitly (`$select=:id, :updated_at, *` or `:*, *`). 2.0: add `$$exclude_system_fields=false`.
- `:updated_at` supports incremental pulls (`$where=:updated_at > '...'`), **with one trap**: when a publisher does a full replace, every row's `:updated_at` moves, so a change pull returns the whole dataset. Maryland's financial feeds are periodically refreshed wholesale, which is why the extract validates full snapshots instead of trusting increments.

## 7. Datatypes and output formats

Core datatypes: Text, Number, Money, Percent, Calendar date, Floating timestamp, Checkbox, URL, Email, Phone, Location (2.0), Point/Line/Polygon/Multi* (2.1+), Document/Photo (blobs), JSON.

| Format | Extension | Mime | Versions |
|---|---|---|---|
| JSON | `.json` | `application/json` | 2.0, 2.1, 3.0 |
| CSV | `.csv` | `text/csv` | 2.0, 2.1, 3.0 |
| GeoJSON | `.geojson` | `application/vnd.geo+json` | 2.1, 3.0 |
| XML | `.xml` | `text/xml` | 2.0, 3.0 |
| RDF-XML | `.rdf` | `application/rdf+xml` | 2.0 only |

Formats are chosen by extension or `Accept` header. The extract reads JSON into Parquet; the reconciliation downloads use CSV endpoints.

## 8. Discovery (catalog) API

`https://api.us.socrata.com/api/catalog/v1` — the global catalog across every Socrata customer. Parameters used for the portal scan:

- `domains=opendata.maryland.gov` — scope to the State's portal (`internaldata.maryland.gov` is a separate domain)
- `only=datasets` — exclude lenses, maps and filters
- `q=<terms>` — full-text over names, descriptions, tags and columns
- `limit`/`offset` — page through results (`resultSetSize` reports the total)

Each result carries the resource ID, name, description, column names/types, `domain_category`, `domain_tags`, and `domain_metadata` — including `Time-Period_Time-Period-of-Content`, which is where fiscal-year coverage is declared. **Scan discipline:** catalog results are candidates, never inputs; production IDs stay pinned in `config/datasets.yaml`.

Dataset metadata for one known ID: `/api/views/<id>.json` on the portal domain.

## 9. Publishing (Producer) side

Not used by this read-only project, but the docs cover it and the division of labor matters when talking to data owners:

- **SODA Producer API**: bulk replace (`PUT`), bulk upsert (`POST`), and single-row add/update/delete. Write requests require HTTPS, HTTP Basic or OAuth 2.0, and an app token. Row identifiers (publisher-specified or internal) drive upsert behavior.
- **Non-API publishing paths** the State actually uses: the web UI, Socrata Gateway (on-prem agent to source systems), DataSync (Java, intelligent updates), and Safe FME. This is why publisher-side refresh cadence is outside our control and why the pipeline validates against the portal on every run.
- Asset-level metadata and the data catalog are separately manageable through the metadata APIs; the Discovery API above is the read side.

## 10. Libraries and SDKs

Official: Java, JavaScript, PHP, PowerShell, Ruby, Scala, Swift, Android, iOS, the DataSync SDK (Java), and a Python SDK for the Dataset Management API. Community: **sodapy (Python — what `src/pipeline/extract.py` uses)**, RSocrata (R), .NET, Julia, go-soda (Go), Elixir, PhpSoda, ember-socrata.

## 11. Notes specific to this repo

- The extract uses SODA 2.1 `GET /resource/<id>.json` via sodapy with `$order=:id`, `$limit=20000`, six retries with exponential backoff, and two heal attempts on count mismatch (`config/datasets.yaml`).
- The SODA3 migration is a roadmap item: switch to `/api/v3/views/<id>/query.json` with `MD_SODA_APP_TOKEN`, keeping 2.1 as fallback. SODA3's `POST` + `page` model maps cleanly onto the current pager.
- The developer portal itself is open source and CC BY-NC-SA 3.0 licensed by Tyler Technologies; this page is a distilled reference, not a copy.
