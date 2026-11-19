# Global refresh plan

How every asset in this repository gets refreshed, in what order, and what must be logged each time — including the
downstream consumers (the Pages dashboard and the portfolio site at https://goaiarchitect.com/). Companion to
[`repo-inventory.md`](repo-inventory.md), which numbers every folder and file and carries the same refresh tags.

## 1. The two refresh events

**Total refresh** — new data from the portal. Runs the whole pipeline and regenerates every derived asset:
`make extract && make build` (checks run inside the build), then `make export && make site-snapshot` to refresh the
committed snapshot, then the doc/figure regenerators (`python -m src.models.doc_facts`, `make reconcile figures docs`,
`make overview-figures`, `make notebook`). The monthly *Extract and build* workflow (3rd of each month) does the
portal-to-checks part and uploads the run-evidence artifact; the snapshot commit is a local step.

**Pages update** — any push to `main`. The Pages workflow rebuilds the dashboard from the checked-in `site_data/`
snapshot and deploys it; the Publish-data workflow re-stages Parquet + manifest + dataset card to Hugging Face and
creates the `data-<run_id>` release. A Pages update never recomputes numbers — it republishes the snapshot.

## 2. Refresh tiers (what runs, what it writes, what it logs)

| Tier | Trigger / command | Writes | Logged in |
|---|---|---|---|
| T1 extract | monthly cron, manual `make extract` | `data/raw/` (not committed), `data/runs.csv` | `data/runs.csv`, raw run `manifest.json`, run-evidence artifact |
| T2 build+checks | `make build` | `data/md_transparency.duckdb` (not committed), `data/check_history.csv` | stop-check results (143), run-evidence artifact |
| T3 export | `make export` | `data/export/<run_id>/` CSVs + Parquet + `manifest.csv` | export `manifest.csv` (rows, hashes, changed-since-last) |
| T4 snapshot | `make site-snapshot` | `site_data/` (committed) | `site_data/snapshot.json`, `sources.csv` (`portal_updated`), `pipeline_runs.csv`, `run_checks.csv` |
| T5 docs/figures | `doc_facts`, `make reconcile figures docs overview-figures notebook readme-shots` | README fact block, `docs/models/` fact blocks, `docs/reconciliation/`, `docs/figures/`, `docs/schemas/`, `docs/data-governance.md`, `notebooks/` | `docs/reconciliation/crosschecks_<date>.csv`, `docs/schemas/drift_history.csv`, docs-refresh patch in run evidence |
| T6 Pages | push to `main` → Pages workflow | deployed dashboard | deployment record; `tests/test_site.py` gate |
| T7 data publish | push to `main` → Publish-data workflow | Hugging Face dataset, `data-<run_id>` release | release notes (dataset card), HF commit |
| T8 downstream | manual, after T4/T6 | portfolio site stats, tab snapshots | **this plan's asset log (§4)** |

Order matters: T1→T2→T3→T4→T5→(commit)→T6+T7→T8. `doc_facts` runs **before** pytest in the workflow so the README
facts match the new run's as-of date (that ordering bug is fixed; keep it).

## 3. Asset → pipeline source log

Every committed asset group, its generator, and whether each refresh event touches it. Per-file detail is in
`repo-inventory.md` (section numbers in parentheses).

| Asset group | Inventory § | Source (generator) | Total refresh | Pages update |
|---|---|---|---|---|
| Pipeline code, SQL marts, models, tests | §12–14 | hand | input | input |
| Config (`config/*.yaml`, `metrics.yml`) | §4 | hand | input | input |
| Reference tables (`reference/`) | §9 | hand (audited judgment) | input | input |
| `site_data/` CSVs + Parquet (incl. `partial_year`/FYTD flags) | §11 | `make export` + `make site-snapshot` | **rewritten** | republished as-is |
| README fact block, `docs/models/` fact blocks | §1.14, §5.17 | `doc_facts.py` (auto in workflow) | **rewritten** | no |
| `docs/schemas/`, `docs/data-governance.md` (gen sections) | §5.22, §5.7 | `make docs` | **rewritten** | no |
| `docs/reconciliation/` | §5.19 | `make reconcile` | **rewritten + new dated crosscheck** | no |
| `docs/figures/` (all three levels) | §5.23 | `make figures` / `overview-figures` / `readme-shots` / `diagrams` | **rewritten** | figures copied into the site |
| `notebooks/` | §8 | `make notebook` | **rewritten** | no |
| `docs/parity/` | §5.18 | `make parity` (run when legacy comparison matters) | on demand | no |
| Lockfiles | §1.20–21 | `make lock` | only on dependency changes | input |
| `legacy/` | §6 | frozen | never | never |
| Changelog / roadmap / governance docs | §1, §5 | hand | edit when numbers or decisions change | no |

## 4. Downstream asset log — goaiarchitect.com

The portfolio site quotes and embeds this project's outputs. **Every item below must be re-synced after a total
refresh** (new run id, new as-of date) and checked after a Pages update. Values read live from
`site_data/metrics.json` (written from `config/metrics.yml`) — never retype them.

| # | Portfolio asset | Pipeline source | Refresh with | Status (Nov 19, 2026) |
|---|---|---|---|---|
| D1 | "1.29M rows checked against the portal" | metric `rows_checked_against_portal` (`metrics.json`, README facts) | total refresh | current |
| D2 | "143 of 143 checks passed" | metrics `checks_passed` / `checks_total` (`site_data/run_checks.csv`) | total refresh | current |
| D3 | "6 Maryland open datasets" | `config/datasets.yaml` (six pinned feeds) | changes only when a feed is added | current |
| D4 | "10 tabs" in meta/OG descriptions | dashboard tab count (11 since the Executive walkthrough tab, PR #24) | code change | **stale — says 10, now 11; fix on next portfolio sync** |
| D5 | "62 marts" | `sql/mart/` file count | code change | current |
| D6 | `charts/gmi_*.html` — 10 static tab snapshots (over, areas, track, opp, calc, fcast, vend, agency, budget, data) | the live Pages tabs after T6 | total refresh (data) + Pages update (UI) | **no `gmi_exec.html` yet — add the 11th snapshot** |
| D7 | `assets/og-image.png` social card (quotes the same five numbers) | D1–D3, D5 values | whenever D1–D5 change | re-render on sync |
| D8 | Links to the dashboard and its about/ai/catalog/explorer pages | Pages site URL | only if the URL changes | current |
| D9 | Dashboard embed option (`?embed=1&palette=portfolio`) | `tests/test_site_embed.py` keeps the contract | code change | current |

## 5. Runbooks

**Monthly total refresh** (after the scheduled run, or a manual one):
1. Confirm the Extract-and-build run is green; download the run-evidence artifact.
2. Locally: `make export && make site-snapshot`, then `make reconcile figures docs overview-figures notebook`.
3. `pytest -q` and `make site`; spot-check the FYTD/partial-year labels and the new as-of date.
4. Commit `site_data/`, README, `docs/` and `notebooks/` together — one commit per refresh, message carries the run id
   (e.g. "Data refresh: pipeline run 20261119T115247Z (143 of 143 checks passed)").
5. Push → T6 and T7 fire automatically. Then do the §4 portfolio sync.

**Pages-only update** (copy, code or UI change, no new data): push to `main`; the Pages workflow rebuilds from the
snapshot. No numbers change — nothing in §4 except D6/D8 needs a look.

**Portfolio sync (goaiarchitect.com)**: after any total refresh — update D1, D2, D5 from `site_data/metrics.json`;
re-capture the 11 tab snapshots (D6); re-render the OG image if the numbers moved (D7); verify D3/D4/D8/D9.

## 6. What each refresh must log

- Run id, timestamp, git SHA: `site_data/pipeline_runs.csv`, `snapshot.json` — automatic.
- Checks: `site_data/run_checks.csv` (per check, per run) — automatic; the "143 of 143" claim reads from here.
- Portal freshness per feed: `site_data/sources.csv` (`portal_updated`) — automatic; the weekly freshness workflow
  opens an issue when the portal is newer.
- Reconciliation: dated `docs/reconciliation/crosschecks_<date>.csv` — automatic.
- Docs drift: the workflow's docs-refresh patch (`data/review/docs-refresh.patch` in run evidence) — automatic.
- Downstream syncs: record date + what changed in the portfolio repo's commit (D1–D9 above) — manual step, this plan
  is the checklist. If the sync list grows, promote §4 to a checked CSV like `docs/asset-map.csv`.
