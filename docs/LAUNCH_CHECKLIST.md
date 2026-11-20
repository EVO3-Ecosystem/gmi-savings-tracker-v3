# Green launch checklist

Nothing merges to `main` or goes live until **every box below is checked** on the release branch. Each item
names the folder or file, how to refresh it, and what "green" means. If an item doesn't apply to a release,
mark it `N/A` and say why in the pull request. Don't delete it.

Copy this list into the release pull request and check items off there.

**Fiscal-year calendar for this release** (read from the data by `scripts/fy_audit.py`, never typed by hand):
budget years FY2017–FY2027 (actuals FY2017–FY2025, FY2026 working budget, FY2027 legislative appropriation);
payments FY2008–FY2026 full years, plus FY2027 partial (the year in progress); grants FY2009–FY2025; forecasts
through FY2031. Section 0 below makes every other section agree with this calendar.

---

## 0. Fiscal-year reconciliation (runs first, and again last)

- [ ] **0.1** Fresh pipeline run: `make extract build` with `mode = fresh download`. Every dataset's row count matches the portal (`site_data/sources.csv`, `reconciled = 1`).
- [ ] **0.2** Export and snapshot: `make export site-snapshot`. `site_data/pipeline_runs.csv` shows this run as `passed`, `published = 1`, failed `0`.
- [ ] **0.3** Fiscal-year audit on the data: `python scripts/fy_audit.py`. **0 failed.**
  - [ ] **0.3.1** Budget tables reach the latest budget year (FY2027) and carry the stage for every year.
  - [ ] **0.3.2** Payment tables reach the latest payments year. The partial year is flagged `partial_year = true` in every table that carries it, and no full year is flagged.
  - [ ] **0.3.3** Payments reconcile: `totals_by_fy` = the sum of `f_agency.payments` (within the unmapped share) = the State's vendor-payments site, every year.
  - [ ] **0.3.4** Budget reconciles: `f_function` = `f_agency` = the portal file total in `stage_evidence.csv`, every year.
- [ ] **0.4** Fiscal-year audit on the built site: `make site && python scripts/fy_audit.py --site site`. **0 failed.**
  - [ ] **0.4.1** All 11 tabs: every FY mention falls inside the calendar.
  - [ ] **0.4.2** The partial payments year never appears without a partial label, and never headlines a card.
  - [ ] **0.4.3** "Latest actual" always means FY2025 until the State publishes FY2026 actuals.
  - [ ] **0.4.4** Every stand-alone page (`about.html`, explorer, catalog, models, AI layer) passes the same rules.
- [ ] **0.5** Fiscal-year audit on the docs (run as part of 0.3). README, CHANGELOG and `docs/**/*.md` carry no stale period ("FY2008 to FY2024", a full year called partial, a year outside the calendar).

## 1. `.github/`: automation and repo rules

- [ ] **1.1** `workflows/`: every workflow green on the release branch.
  - [ ] **1.1.1** `ci.yml`: lint, tests and site check pass on the pull request.
  - [ ] **1.1.2** `extract-smoke.yml` (Extract and build): a manual run on the release branch passes all steps.
  - [ ] **1.1.3** `freshness.yml`: the last scheduled run passed. No open freshness alert issue.
  - [ ] **1.1.4** `publish_data.yml`: publishes the same run ID as `site_data/pipeline_runs.csv`.
  - [ ] **1.1.5** `pages.yml`: deploys, and the live site shows the new run ID and "Data as of" date.
  - [ ] **1.1.6** Pinned action versions reviewed. No Node 20-only action without a planned bump.
- [ ] **1.2** `ISSUE_TEMPLATE/` and `pull_request_template.md`: the template includes this checklist link.
- [ ] **1.3** `dependabot.yml`: open Dependabot PRs merged or deferred with a reason.
- [ ] **1.4** `CODEOWNERS` and `rulesets/`: `main` requires CI and one review, and matches `docs/repo-settings.md`.

## 2. `config/`: every number the pipeline assumes

- [ ] **2.1** `assumptions.yaml`: the fiscal-year keys match the calendar.
  - [ ] **2.1.1** `first_actual_fy`, `last_actual_fy`, `horizon_fy` (budget and forecast).
  - [ ] **2.1.2** `current_fy`, `base_fy`, `payments_fy`, `before_fy` and `after_fy`, `matched_fy`, `forecast_fy` (detectors and checks).
  - [ ] **2.1.3** `payment_screen.first_fy` and `last_fy` (full years only. The partial year is never screened).
  - [ ] **2.1.4** When a new actual year is published, every key above is rolled forward in the same commit.
- [ ] **2.2** `datasets.yaml`: dataset IDs, year columns and portal names. The stale portal titles are noted in `reference/source_notes.csv`.
- [ ] **2.3** `dashboard.yaml`: every table the page reads is listed and exported (count matches `site_data/manifest.csv`).
- [ ] **2.4** `briefs.yaml` and `metrics.yml`: metric definitions match `docs/checks.md` and the page's labels.

## 3. `src/`: the pipeline, models and servers

- [ ] **3.1** `src/pipeline/`
  - [ ] **3.1.1** `extract.py` and `build.py`: `partial_year` is set from the data (the latest payments year), never hard-coded.
  - [ ] **3.1.2** `export.py`: partial-year rows are published with their flag, not dropped. The hold applies only where a table has no flag column.
  - [ ] **3.1.3** `checks.py`: 143 of 143 or more pass. Any new check is listed in `docs/checks.md`.
  - [ ] **3.1.4** `site.py` and the `site_*.py` builders: `FY_NOTE` names the current partial year. The banner names the live flagship (v3).
  - [ ] **3.1.5** `figures.py` and `overview_figures.py`: regenerated (see 5.2).
- [ ] **3.2** `src/models/`: `make forecast-check` reproduces the published forecast. The model registry's run ID matches.
- [ ] **3.3** `src/mcp/` and `src/briefs/`: tests pass, and the latest full and partial year come from the data.
- [ ] **3.4** `published.py`: reads the same snapshot the site serves.

## 4. `sql/mart/`: all 62 mart definitions

- [ ] **4.1** Every mart builds in this run (no skipped mart in the build log).
- [ ] **4.2** Every mart that reads payments says how it treats the partial year: excluded (`NOT partial_year`) for screens and detectors, flagged for totals and trends.
- [ ] **4.3** No mart hard-codes a fiscal year. Years come from `{{assumptions}}` keys or the data.

## 5. `docs/`: everything a reader sees outside the dashboard

- [ ] **5.1** Top-level docs reviewed for this release's periods: `executive-overview.md`, `data-sources.md`, `checks.md`, `recommendations.md`, `roadmap.md`, `strategy-v3.1.md`, `data-governance.md`, `mcp.md`, `asset-map.md` and `asset-map.csv`, `briefs.md`, `best-practices.md`, `repo-settings.md`, the portfolio docs.
- [ ] **5.2** `figures/`: regenerated from this run (`make figures overview-figures diagrams readme-shots`). The newest file date is not older than the run.
- [ ] **5.3** `models/`: model notes regenerated, with the backtest years matching `rolling_score_through_fy`.
- [ ] **5.4** `schemas/`: `make docs-strict` passes, and the column catalog count matches the README.
- [ ] **5.5** `parity/`: `make parity` passes, with `summary.csv` from this run.
- [ ] **5.6** `reconciliation/`: the portal and book reconciliations are rerun, with differences explained.
- [ ] **5.7** `research/` and `reviews/`: dated documents keep their own dates and are not rewritten. Just confirm nothing labels them current.

## 6. `site_data/`: the published snapshot (78 CSVs and their parquet copies)

- [ ] **6.1** Every CSV comes from this run. `snapshot.json` `refreshed_utc` equals the run time.
- [ ] **6.2** `parquet/` matches the CSVs (same tables, same row counts).
- [ ] **6.3** `manifest.csv`, `sources.csv`, `run_checks.csv` and `pipeline_runs.csv` all show the same run ID.
- [ ] **6.4** Year coverage per table matches the calendar (covered by 0.3).

## 7. `reference/`: the hand-kept lookup tables

- [ ] **7.1** `budget_stage.csv` and `stage_evidence.csv`: a stage for every budget year, with the evidence URL for any new or changed stage.
- [ ] **7.2** `site_totals.csv`: the State site's yearly totals re-read for every year, partial year included.
- [ ] **7.3** `gmi_reported_savings.csv`, `gmi_public_page_claims.csv` and `claim_sources.csv`: every claim has a source and date, and none is newer than its source.
- [ ] **7.4** Rules and maps (`*_rules.csv`, `*_map.csv`, `*_aliases.csv`, `vendor_*.csv`, `payee_*.csv`): `make gate3` passes. New payees in the partial year are reviewed.
- [ ] **7.5** `column_dictionary.csv`, `field_availability.csv`, `source_notes.csv`: they cover every exported column and dataset.
- [ ] **7.6** `gf_revenue_history.csv` and `ola_findings.csv`: the newest published year is added.

## 8. `legacy/`: the dashboard page and the archived pipeline

- [ ] **8.1** `gst/page/index.html`: the dashboard.
  - [ ] **8.1.1** No hard-coded fiscal year where the data can supply it (latest full payments year, latest actual, latest budget year).
  - [ ] **8.1.2** All 11 tabs open without script errors (covered by 0.4).
  - [ ] **8.1.3** Backup pages (`index_*_backup.html`) aren't deployed.
- [ ] **8.2** `gst/` harness and tests: `pytest tests/test_site*.py` passes.
- [ ] **8.3** `artifact/`: the claude.ai artifact build (`make site-artifact`) matches the Pages build.
- [ ] **8.4** `MANIFEST.csv` and `README.md`: list what is archived and why.

## 9. `tests/`: all suites green

- [ ] **9.1** `make test`: 0 failures, 0 errors. Any skipped test is listed with a reason.
- [ ] **9.2** `fixtures/`: fixtures carry the current calendar, including a partial year.
- [ ] **9.3** `make test-fault`: fault injection passes.

## 10. `scripts/`, `notebooks/`, `mcp_server/`

- [ ] **10.1** `scripts/fy_audit.py`: 0 failed (section 0). `bootstrap_github.sh` still matches the repo settings.
- [ ] **10.2** `notebooks/`: `make notebook notebook-check`. `walkthrough.ipynb` and `walkthrough.html` show this run's numbers and years.
- [ ] **10.3** `mcp_server/`: the server starts, `db/load_postgres.py --dry-run` passes, and its README matches `docs/mcp.md`.

## 11. Root files

- [ ] **11.1** `README.md`: facts regenerated from the data (`test_readme.py` passes). The live link is the v3 site, and the run date and periods are current.
- [ ] **11.2** `CHANGELOG.md`: a dated entry for this release, naming the run ID and the fiscal-year calendar.
- [ ] **11.3** `Makefile`: every target named in this checklist exists and runs.
- [ ] **11.4** `pyproject.toml`, `uv.lock`, `requirements.lock.txt`: `make lock` produces no diff. Dependabot bumps are included.
- [ ] **11.5** `Dockerfile`, `compose.yaml`, `.dockerignore`: `make docker-test` passes.
- [ ] **11.6** `dvc.yaml`, `.dvc/config`, `.dvcignore`: stages match the Makefile targets.
- [ ] **11.7** `.env.example`: every variable the code reads is listed, and no secret value is committed.
- [ ] **11.8** `.gitignore`, `.python-version`: the Python version matches CI.
- [ ] **11.9** `CITATION.cff`: version and date bumped.
- [ ] **11.10** `LICENSE`, `SECURITY.md`, `SUPPORT.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `GOVERNANCE.md`: contacts and links still work.

## 12. Earlier versions and the portfolio

- [ ] **12.1** `gmi-savings-tracker` (v1) and `gmi-savings-tracker-v2`: each is either live with a "superseded by v3" banner, or archived, with its README pointing to v3. Neither serves a 404 that a public page links to.
- [ ] **12.2** The v3 banner names the real flagship.
- [ ] **12.3** `ai-architect-portfolio`: every link to the tracker goes to a live site. Tab count and figures match.

## 13. Launch

- [ ] **13.1** Sections 0–12 all checked, or `N/A` with a reason.
- [ ] **13.2** Section 0 rerun on the merged `main` after the Pages deploy: 0 failed.
- [ ] **13.3** The live site: "Data as of", run ID and "Data checks passed" match `site_data/pipeline_runs.csv`.
