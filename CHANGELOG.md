# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## Unreleased (November 2026 review)

Added
- Calibrated forecast ranges (`p10_cal`, `p90_cal`, `range_source`) beside the raw ones, with coverage measured out of sample in `mart.d_range_coverage`. Raw ranges held 40 of 63 past outcomes; calibrated ranges held 53 of 63 with each outcome year held out.
- Conformalized LightGBM bands, an adoption rule for the first forecast year, and a statewide corridor that is no longer clamped. Their measured results need a pipeline run.
- `python -m src.models.forecast_published --check`: rebuilds the forecast from the published tables and compares it with what was published.
- `notebooks/walkthrough.ipynb` (reads only the published tables, committed executed), `docs/executive-overview.md`, and six figures in `docs/figures/overview/`.
- `uv.lock`, `requirements.lock.txt`, `.python-version`, `Dockerfile`, `compose.yaml`; CI installs from the lockfile and also runs the tests inside the image.
- `src/pipeline/doc_counts.py`: counts typed in the docs are generated from the files they describe.
- Statewide program screen (`src/models/program_screen.py`, `mart.d_program_screen`): every program of every agency screened for fast growth and large yearly swings, with audit findings beside it. `reference/audit_findings_override.csv` records reported findings with a program, an amount and a recoupment status; `docs/research/childcare-overpayments.md` is the first case.
- Dashboard, Budget tab: "Programs that grew fast and swung sharply", computed in the page from the program table with the same rule and settings as the Python module (a test holds the two equal), plus a table of every screened program. Agency pages list reported findings with their recoupment status.

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
