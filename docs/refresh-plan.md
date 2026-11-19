# Global refresh plan — total refresh, Pages and goaiarchitect.com

Companion to the [repository inventory](repo-inventory.md): inventory numbers below (`§4.1`, `§10`, …) point at its
sections. A **total refresh** regenerates every pipeline-produced asset from the sources, rebuilds the Pages site,
and pushes the downstream updates to **goaiarchitect.com**. Nothing is refreshed by editing outputs by hand: each
asset has exactly one producer, logged in the inventory's *Source* label.

As of **November 19, 2026**. Commands assume the repo root, Python 3.12 (`uv sync` or `pip install -e ".[dev]"`),
and optionally `MD_SODA_APP_TOKEN` in the environment (optional since decision D5 was revised; used only in Actions,
never committed).

## Stage map

| Stage | Name | Command | Regenerates (inventory §) | Gate |
|---|---|---|---|---|
| R1 | Extract | `make extract` | untracked `data/raw/`, `data/runs.csv` | row counts = portal `count(*)`; freshness on `rowsUpdatedAt` |
| R2 | Build + checks | `make build` | untracked `data/md_transparency.duckdb`, `data/check_history.csv` | 143 stop checks; a failure keeps the last good database |
| R2a | Test gate | `make test` | — (verifies §13 against the build) | pytest green |
| R3 | Reconcile + parity | `make reconcile && make parity && make fy-audit` | §4.3 parity tables, §4.4 reconciliation tables | `--strict`: no unexplained difference |
| R4 | Export | `make export` | untracked `data/export/<run_id>/` (CSV + Parquet + manifest) | gate.py refuses on failed checks or a stale DB |
| R5 | Publish snapshot | `make site-snapshot` | **§10 `site_data/`** (81 CSVs + Parquet mirrors + manifest) | diff reviewed in the refresh PR |
| R6 | Derived docs + figures | see R6 below | §4.1 figures, §4.2 model-card facts, §4.6.1 review sheet, §4.7 schemas, §4.15 data-governance.md, §7 notebooks, §14.1/§14.6 README & CHANGELOG numbers | `make docs-strict` on drift |
| R7 | Site + Pages | `make site`, then PR to main | untracked `site/`; §2.3.4 `pages.yml` deploys | `pytest -q tests/test_site.py` |
| R8 | Data release (per release) | Actions → §2.3.5 `publish_data.yml` | Hugging Face dataset + GitHub Release `data-<run_id>` | `publish.py --dry-run` validation |

R1–R2 also run unattended on the 3rd of each month via §2.3.2 (`extract-smoke.yml`); that workflow stops before R5 —
**publishing new data to `site_data/` is still a manual PR** (roadmap SL06). A total refresh is that PR, run by hand.

## R1 — Extract (§3.4 `config/datasets.yaml` → raw)

```bash
make extract            # SODA pulls of the six pinned feeds + context sources; raw Parquet per run
```

- Sources: the six pinned feeds in §3.4 (budget `yu65-jmmv`, funding source `gy87-e27x`, spending `7syw-q4cy`,
  grants `absk-avps`, payments `x8qy-486w`, higher-ed `4mca-332u`; the FY2010–FY2027 datamart map of PR #31's wiki
  lists the candidates beyond these six).
- Self-heals: a row-count mismatch against the portal re-downloads (up to twice) before failing.
- Output is git-ignored and DVC-tracked (§1); it never appears in a PR.

## R2 — Build + checks (§8 reference, §11.1 mart SQL → warehouse)

```bash
make build              # DuckDB layers raw/ref/core/mart/ops + 143 stop checks
make test               # full pytest gate (§13)
```

- Medallion mapping: raw = Bronze (raw fidelity — no dimensional modeling), ref + core = Silver (dedup, typing,
  conformance from the §8 reference tables), mart = Gold (the 62 marts of §11.1 plus helpers).
- FY2027 payments are partial (began July 1, 2026) and stay flagged `partial_year` end to end — never presented
  as a full year (repo rule; the in-flight `fix/fy-alignment-fy2027-partial` branch extends the flag to the
  per-year payment tables).

## R3 — Reconcile + parity (evidence against the State's own copies)

```bash
make reconcile          # API extract vs the portal's own downloads -> §4.4 docs/reconciliation/
make parity             # every mart vs the frozen legacy outputs (§5) -> §4.3 docs/parity/
make fy-audit           # fiscal-year wording audit -> §4.4.6 docs/reconciliation/fy_audit.md
```

A difference is acceptable only once §4.3 `explanations.csv` explains it by hand.

## R4 — Export (warehouse → dashboard tables)

```bash
make export             # data/export/<run_id>/ CSVs + Parquet + manifest.csv
```

- Table list: §3.3 `config/dashboard.yaml` (75 datasets) plus the decision-register extras in `export.py`
  (`ola_findings`, `d_reported_claims`, detector backtests, …).
- The partial-year rule lives here: `totals_by_fy` publishes FY2027 flagged partial; the per-year payment tables
  publish it with the same flag once the page treats partial years (in-flight fix).

## R5 — Publish the snapshot (what Pages builds from)

```bash
make site-snapshot      # copy data/export/latest into the checked-in site_data/ (§10)
```

This is the only step that changes tracked data files. Review the diff like data: row counts, the manifest's
`changed` flags, and that FY2027 rows carry `partial_year = true`.

## R6 — Derived docs and figures

```bash
make figures            # §4.1 analysis PNGs (rows_by_year, reconciliation, budget_by_stage, vendor_*, check_history)
make overview-figures   # §4.1.1 overview PNGs
make notebook           # §7.2 walkthrough.ipynb + §7.1 walkthrough.html (also refreshes §4.1.1)
make docs               # §4.15 data-governance.md sections, §4.7 schemas, §4.6.1 review sheet, §4.2 model-card facts
python -m src.pipeline.doc_counts   # computed numbers in §14.6 README.md, §14.1 CHANGELOG.md and docs/*.md
make docs-strict        # fails on schema drift or undocumented columns
make diagrams           # §4.1 + §4.1.2 Mermaid -> PNG (needs mmdc)
```

## R7 — Site + Pages

```bash
make site               # build site/ from site_data/ (index, ai.html, catalog.html, explorer.html, models.html,
                        # walkthrough.html, exec_walkthrough.csv, figures/, 404, robots)
pytest -q tests/test_site.py
make readme-shots       # §4.1.2 README gallery screenshots from the built site
```

Commit the R5–R7 results on a branch and open the **refresh PR**. On merge to main, §2.3.4 `pages.yml` rebuilds
`site/` from `site_data/` and deploys **evo3-ecosystem.github.io/gmi-savings-tracker-v3** — the dashboard that
goaiarchitect.com links and embeds. Pages needs no data access: it builds entirely from the checked-in snapshot.

## R8 — Data release (with each versioned release)

Actions → **Publish data** (§2.3.5): validates and uploads the Parquet marts to the Hugging Face dataset
`thedatavigilante/maryland-gmi-spending` and attaches them to a GitHub Release `data-<run_id>`.
Bump §15.6 `CITATION.cff` and §14.1 `CHANGELOG.md` in the same release PR.

## Downstream — goaiarchitect.com refresh checklist

The portfolio site draws from this repo. On every total refresh, update each of these — each mapped to its
pipeline source so nothing is retyped by hand:

| goaiarchitect.com asset | Fed by (inventory §) | Pipeline source |
|---|---|---|
| "What's built and what's next" board / project cards | §4.9 `docs/asset-map.csv` (`portfolio_asset`, `v3_status` columns) | manual CSV, existence-checked by `tests/test_asset_map.py` — update statuses in the refresh PR, then re-render the board |
| Metric tiles (checks passed, tables published, rows, FY range) | §10 `site_data/run_checks.csv`, `manifest.csv`, `totals_by_fy.csv` | R4/R5 — the same numbers `doc_counts.py` writes into §14.6 |
| GMI Savings Tracker card screenshots | §4.1.2 `docs/figures/readme/*.png` | R7 `make readme-shots` |
| Live dashboard link/embed | `evo3-ecosystem.github.io/gmi-savings-tracker-v3` | R7 Pages deploy — verify the deploy finished before announcing |
| Walkthrough / notebook link | §7.1 `notebooks/walkthrough.html` (served at `/walkthrough.html`) | R6 `make notebook` |
| Data download card | Hugging Face `thedatavigilante/maryland-gmi-spending` | R8 |
| Executive overview text | §4.17 `docs/executive-overview.md`, §7 walkthrough key findings | manual; numbers verified by R6 `doc_counts.py` |

Rule: every figure quoted on goaiarchitect.com must match the published snapshot of the same run id
(`src/published.py` reads §10; `P.run_info()` gives the run id and check counts to cite).

## Manual-review list (not auto-regenerated — read on every total refresh)

- §3.1 `config/assumptions.yaml` — savings years and target (FY2027 retarget in flight on `fix/fy-alignment-fy2027-partial`)
- §8 `reference/` — the claims registers (`gmi_reported_savings.csv`, `gmi_public_page_claims.csv`,
  `claim_sources.csv`): add new GMI claims **with source and date**; never overwrite history
- §4.9 `docs/asset-map.csv` — bump `v3_status` / `action` as rows move
- §4.23 `docs/roadmap.md` — date the status lines
- §14 root documents, §2.3 workflows, §11.1 mart SQL, §12 source — normal code review

## Known gaps logged at this refresh

1. **Orphan figure** — §4.1 `docs/figures/dashboard_overview.png` has no producer in the repo; regenerate it from
   the R7 screenshots or retire it. `correlation_heatmap.png` is produced by `make figures` but not committed —
   commit it or drop the save.
2. **Monthly automation stops at R2** — publishing the monthly run to §10 is still a manual PR (roadmap SL06);
   the December 3, 2026 scheduled run is the first test.
3. **Wiki pending** — PR #31 (`docs/wiki/`) inserts as inventory §4.8 when merged (the file items after it
   renumber). R6's `doc_counts.py` already covers `docs/wiki/*.md`.
4. **FY2027 partial-year treatment** — export and dashboard fixes are in flight; until merged, the per-year
   payment tables hold FY2027 back by design (see R4).
