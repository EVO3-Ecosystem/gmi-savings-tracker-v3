# Gap analysis: research and portal scan vs the repository

Comparing three things as of **November 19, 2026**: the SODA Developers documentation ([distilled here](soda-developers-api.md)), the full Maryland portal scan ([datamart map](datamart-map-fy2010-2027.md)), and the repository at `main` (v3.2.0). Each gap has a priority: **P1** blocks or understates the audit, **P2** is leverage we already pay for but don't use, **P3** is housekeeping.

## P1 — Coverage and source gaps

**P1-1 · No pre-FY2017 budget-side feeds.** Budget, funding source, FTE and higher-ed data start at FY2017; the FY2010–FY2016 third of the requested window exists only in DBM's archived budget books and Fiscal Digests. *Next step:* treat archival backfill as a separate document-extraction schema (the datamarts branch already says this); scope it against `src/pipeline/books.py`, which already parses DBM books for FY2017+.

**P1-2 · Payments are annual payee aggregates.** The payments feed's date field is always January 1; 4 of the 13 fields an audit-grade tracker needs are public (`reference/field_availability.csv`). Duplicate-window, split-purchase and monthly analyses cannot be confirmed. *Next step:* unchanged — the Public Information Act requests in the README's next steps (Comptroller payment-level MSDE records; MSDE audit/recoupment records); the `core.fact_payment_txn` schema is ready to receive them.

**P1-3 · Grants feed ends at FY2025; payments FY2027 is partial.** Known and flagged in the bundle coverage logic (`partial` / `not_published`, blank-not-zero). *Next step:* none until publishers release rows; the monthly extract picks them up automatically.

**P1-4 · The FY2022 payments double listing ($874.5M second block).** Confirmed on both State sites November 10, 2026; reported as a source issue, never a lead. *Next step:* keep the stop check; escalate to the data owner through the portal's contact channel if it survives the December refresh.

## P2 — Sources and capabilities we have but don't use

**P2-1 · The eMaryland Marketplace bids family is not extracted.** Eight per-fiscal-year DGS datasets (FY2014–FY2019 confirmed IDs, two more in the result set) hold source-grain bid records — the same domain as the anomaly model's `d_bid_list` baseline, which today is a small reference file. This is the strongest procurement-savings evidence the portal offers. *Next step:* verify the two remaining IDs with `q=emaryland` on the Discovery API, run the year-by-year portal checks the other feeds get, then pin the family in `config/datasets.yaml` (schemas drift year to year — treat each year as its own dataset with its own manifest) and add a `mart` view feeding the bid-list baseline.

**P2-2 · County school-spending feed is documented but not pinned.** `t6vk-rvwe` appears in the datamart-bundle branch docs but not in `main`'s `config/datasets.yaml`. *Next step:* decide as part of merging the datamart branches (P3-1); if adopted, keep the hard rule that county disclosures are never added to State vendor payments.

**P2-3 · SODA3 migration is still pending.** The extract runs SODA 2.1 without a token; SODA3 (`/api/v3/views/<id>/query.json`, POST-first) requires `MD_SODA_APP_TOKEN` and is the documented future. *Next step:* the roadmap item stands — migrate with 2.1 as fallback; the token already exists as a repo secret and is only usable by Actions and local `.env`.

**P2-4 · The wiki is not wired into the Pages site.** The Pages build (`make site` → `site/`) renders pipeline output only; it has no Markdown docs step, so `docs/wiki/` renders on GitHub but not yet on the Pages site. *Next step:* add a docs/wiki page type to `src/pipeline/site.py` (or link the GitHub-rendered wiki from the dashboard's Data & pipeline tab), then the next Pages deploy carries it.

**P2-5 · System fields unused for change detection.** `:updated_at` incremental pulls are documented but the feeds are periodically full-replaced, which would flood increments — the current full-snapshot validation is correct, but a cheap `:updated_at` max-timestamp probe per dataset could drive the weekly freshness check instead of a row-count-only check. *Next step:* evaluate in `freshness.yml`; two lines of SoQL per feed.

**P2-6 · Discovery API not part of the pipeline.** The portal scan that found the eMM family was manual. *Next step:* a quarterly catalog-diff script (new datasets matching the finance keyword families, counted and listed into a GitHub issue) so new feeds surface without another ad-hoc scan.

## P3 — Process and repository housekeeping

**P3-1 · Two unmerged datamart branches.** `feat/fy2009-2027-datamarts` (adds `docs/datamarts.md`, 7-feed bundle design) and `feat/fy2017-2027-datamarts` diverge from `main` and from each other. *Next step:* review, merge the FY2009–FY2027 design (it is the more complete), close or rebase the other; this PR's wiki pages reference the design doc, which resolves cleanly once merged.

**P3-2 · First scheduled monthly extract has not completed.** The workflow runs on the 3rd; a manual Nov 18 run passed every step. *Next step:* confirm the December 3, 2026 run, then publish the data-refresh PR (`site_data/`, which publishes `mart.d_program_screen`).

**P3-3 · Alert channel for failed checks.** Freshness opens a GitHub issue; a failed-stop-check alert channel (Slack/Teams/email) is unchosen. *Next step:* pick the channel (already listed in `docs/asset-map.csv`, SL07).

## What the research cannot close

The portal scan confirms the shape of the hole rather than filling it: payment and invoice numbers and dates, per-payment fund, and vendor numbers live in FMIS behind MD-VIEW (one search at a time, no download, never scraped). No keyword family on the portal surfaces a transaction-level alternative — the PIA route in P1-2 is the only documented path, and no amount of SODA capability changes that.

## Method note

Scan: Socrata Discovery API, `domains=opendata.maryland.gov`, 1,519 datasets; finance keyword families enumerated exhaustively with `q=` (budget 22, payments 25, emaryland 8, contract 15, revenue 15, tax 53, travel 18, positions 68); the sibling domain `internaldata.maryland.gov` holds 9 public datasets, none financial. Sandbox egress to Socrata is IP-blocked, so the scan ran through the reading tool and per-dataset detail was bounded by response size — the two uncaptured eMM IDs (P2-1) are the only known casualty, and they are recoverable in one query.
