# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [3.2.0] - 2026-11-16

Added
- Reconciliation with the State's own documents for every year (`src/pipeline/books.py`, `mart.d_book_reconciliation`, `d_site_reconciliation`, `d_book_program_differences`, Data & pipeline tab): FY2017-FY2025 program actuals against DBM's Governor's budget books (9 of 9 years reconcile, 99.3-100% of programs equal to the dollar); the enacted FY2027 budget against the Fiscal Digest by fund (to the dollar); yearly totals against the Open Finance sites (31 of 31 to the cent); an FY2026 working-budget bridge and an FY2027 general fund walk with labelled remainders.
- Stop checks re-test the warehouse against the stored DBM and site figures on every build; thresholds pre-registered in `config/assumptions.yaml` (`books`).

Changed
- License: proprietary, all rights reserved (was MIT). Copies obtained under the earlier license keep those terms.
- Version 3.2.0 in `pyproject.toml` and `CITATION.cff`; README badges, pipeline diagram and next steps updated.

Fixed
- The site copies figure subfolders, so the about page's README figures resolve.

## [3.1.0] - 2026-11-16

Added
- Audit depth (docs/strategy-v3.1.md): fund hierarchy and shifts to the General Fund (`mart.d_fund_hierarchy`, `d_fund_shift`), State budget by Assistance Listing beside USAspending obligations (`d_federal_crosswalk`), payee alias evidence and review queue (`d_vendor_alias`, `d_vendor_alias_review`), audit and recoupment lifecycle register (`reference/audit_findings.csv`, `d_audit_findings`), payment-level schema ready for records requests (`src/pipeline/txn.py`, `core.fact_payment_txn`) and field availability (`d_field_availability`).
- Model registry (`mart.d_model_registry`): every model, its baseline, held-out score and decision, read from its own evaluation each run.
- Drift monitor (`mart.d_drift`): PSI and KS between consecutive fiscal years; one major shift (FY2021-FY2022 agency mix of payments, PSI 0.32).
- Dashboard: detector backtest card (persistence and next-year divergence), fund-shift dumbbell chart, federal cross-check chart, alias review queue, audit lifecycle card, model registry, drift chart, field-availability meter. The page now shows the calibrated forecast ranges.
- README rewritten as a portfolio overview with a methods and validation table; `make readme-shots` captures the new figures.

Changed
- Statewide challenger corridor: the sum of series medians with a band from the statewide miss in the backtest. Summing per-series draws put the median 48-137% above the last actual on the first real run (docs/models/challenger.md).
- First real run of the calibrated ranges: 53 of 63 past outcomes (84.1%, Wilson 73-91%) inside the calibrated area ranges with each outcome year held out; 140 of 140 checks pass.

## Earlier (November 2026 review)

Added
- Calibrated forecast ranges (`p10_cal`, `p90_cal`, `range_source`) beside the raw ones, with coverage measured out of sample in `mart.d_range_coverage`. Raw ranges held 40 of 63 past outcomes; calibrated ranges held 53 of 63 with each outcome year held out.
- Conformalized LightGBM bands, an adoption rule for the first forecast year, and a statewide corridor that is no longer clamped. Their measured results need a pipeline run.
- `python -m src.models.forecast_published --check`: rebuilds the forecast from the published tables and compares it with what was published.
- `notebooks/walkthrough.ipynb` (reads only the published tables, committed executed), `docs/executive-overview.md`, and six figures in `docs/figures/overview/`.
- `uv.lock`, `requirements.lock.txt`, `.python-version`, `Dockerfile`, `compose.yaml`; CI installs from the lockfile and also runs the tests inside the image.
- `src/pipeline/doc_counts.py`: counts typed in the docs are generated from the files they describe.

Changed
- Dashboard: no range is described as holding "8 in 10" outcomes; treemap labels pick dark or light ink by fill; tab bar and filters tightened on small screens; the 404 page links to this repository's site.
- Python 3.12 is required.

- Detector backtest extended: as-of FY2020 to FY2024 (payments to FY2025), follow-up of 1 to 3 years, the bid list as a fifth detector, three descriptive outcomes, lift of flagged against not-flagged units (`mart.d_detector_outcomes`, `mart.d_detector_lift`). Results need a pipeline run.
- `Extract and build` workflow now also runs on the 3rd of each month, uploads the model-evaluation tables, and opens an issue when a scheduled run fails.

Not done yet
- Two clean scheduled runs (the schedule starts once this is on the default branch), table checksums across runs, model-run registry.
- The link from past flags to GMI's 18 reported items.

## [2.0.0] - 2026-11-10

First publication as **GMI Savings Tracker v2**, a standalone repository.
Supersedes the original `EVO3-Ecosystem/gmi-savings-tracker`, whose history is
preserved there.

### Added

- **Pipeline & tests**: pre-recorded SODA fixtures so the extract suite runs
  fully offline (`tests/fixtures/soda/`); end-to-end integration test
  (extract → build → checks → export) on a sample database; contract tests
  generated from `docs/schemas` and the column dictionary.
- **Data sources**: State Plan priorities map (51 agencies, cited to the
  Moore–Miller 2024 State Plan); Office of Legislative Audits repeat-findings
  register (17 agencies, per-report citations); BLS Maryland nonfarm
  employment (2007–2026); BEA Maryland real GDP (1997–2025, chained 2017
  dollars).
- **Models**: LightGBM quantile forecast corridors (P10–P90) adopted on
  1,083 of 2,609 series in rolling validation; general-fund revenue model
  (FY2027 midpoint $29.7B); isolation-forest anomaly review queue (2,459
  flags); K-Means spending-mix clusters, now used as the peer-gap detector's
  benchmark groups; TF-IDF + K-Means grant-text clustering (40 program
  families over 23,084 grants); correlation heatmap figure.
- **Dashboard**: executive forecast-range and review-queue tiles; program
  drill-down on agency pages; review-queue CSV export with persisted review
  statuses; analyst-detail toggle; Agencies scatter and per-position
  histogram; Budget function → agency → program treemap; Opportunities PCA
  map and OLA findings card; freshness indicator in the header.
- **Platform**: DVC with a local-only store; optional `make postgres` loader;
  weekly freshness-alert workflow that opens GitHub issues when the portal
  updates; read-only MCP server over the marts (`mcp_server/`); roadmap
  timeline; README "What it found" section with traced figures.
- **Community**: MIT license, Contributor Covenant 2.1 code of conduct,
  contributing guide, security policy, support guide, governance doc,
  citation file, issue templates, PR template, CODEOWNERS, Dependabot.

### Verification

114 pipeline checks (113 pass, 1 documented warning), 174 unit/integration
tests, 36 dashboard page tests, 5 published-site tests — all green.

[2.0.0]: https://github.com/EVO3-Ecosystem/gmi-savings-tracker-v2/releases/tag/v2.0.0
