# Developer wiki

The dev team's working reference for the GMI Savings Tracker (v3). Everything here is sourced: SODA documentation is distilled from [dev.socrata.com](https://dev.socrata.com/) (retrieved November 19, 2026), and portal facts come from a live scan of the Socrata Discovery (catalog) API the same day.

## Pages

| Page | What it covers |
|---|---|
| [SODA Developers API reference](soda-developers-api.md) | The Socrata Open Data API distilled for this project: endpoint versions 2.0/2.1/3.0, SoQL clauses and functions, paging, app tokens and throttling, system fields, datatypes, output formats, the Producer (publishing) API, the Discovery API, and client libraries |
| [Datamart map, FY2010–FY2027](datamart-map-fy2010-2027.md) | Every Maryland open-data feed that can serve as a datamart for the tracker, with its portal ID, fiscal-year coverage, grain, and status in the pipeline; built from the full portal scan |
| [Gap analysis](gap-analysis.md) | Where the research and the portal scan say the tracker is short: coverage gaps, unextracted sources, unused SODA capabilities, and open process items, each with a priority and a next step |

## House rules

1. **Edit through a pull request**, same as code. The repo's branch ruleset requires the `test` check on `main`.
2. **Numbers come from the pipeline or from a dated scan.** A figure typed by hand carries its source and date in the sentence, matching the convention in `reference/`.
3. **Portal IDs are pinned in `config/datasets.yaml`.** A candidate from a catalog scan is never added to the extract automatically; it goes through the review in the [gap analysis](gap-analysis.md) first.
4. **Fiscal years are Maryland fiscal years** (July 1–June 30), the same convention as every figure in the repo.
5. These pages render on GitHub. Wiring them into the generated Pages site navigation is a tracked follow-up (see the gap analysis, item P2-4).

## Related references in the repo

- [docs/datamarts.md](../datamarts.md) — the FY2009–FY2027 datamart bundle design (branch `feat/fy2009-2027-datamarts`; see the gap analysis on its unmerged state)
- [docs/data-governance.md](../data-governance.md) — generated data governance, schemas and known source issues
- [docs/checks.md](../checks.md) — the stop-check catalog
- [docs/mcp.md](../mcp.md) — the read-only MCP server setup
- [reference/datamart_catalog.csv](../../reference/datamart_catalog.csv) — the machine-readable form of the datamart map
