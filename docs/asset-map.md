# Asset map

`docs/asset-map.csv` maps each row of the Maryland Spend Lens roadmap (the earlier prototype's "what it does today and what comes next" board) to what v3 has: its status, the dashboard tab, the published tables, the code, the roadmap decision it belongs to, and the portfolio asset that shows it. Rows marked `v3-only` are things v3 adds that the Spend Lens roadmap does not list.

| Column | Meaning |
|---|---|
| `row_id` | `SL01` to `SL16` for Spend Lens rows, `V01` and up for v3-only rows |
| `source`, `source_phase` | where the row comes from (`spend-lens` or `v3-only`) and, for Spend Lens rows, its phase on that board |
| `v3_status` | `done`, `built` (code exists, waiting on a scheduled run), `partial`, or `not_started` |
| `v3_tab` | dashboard tab id: `over`, `exec`, `areas`, `track`, `opp`, `calc`, `fcast`, `vend`, `agency`, `budget`, `data`, or empty |
| `v3_tables` | published tables, separated by `;` (every name must exist in `site_data/parquet`) |
| `v3_code` | repository files, separated by `;` (every path must exist) |
| `roadmap_ref` | the phase, decision or document in `docs/roadmap.md` that owns the row |
| `portfolio_asset` | the card or element on the portfolio page that shows it |
| `action` | what is left to do |
| `verified` | `yes` if checked against the repo, `unverified` if not |

`tests/test_asset_map.py` fails if a tab id, table or file named here does not exist, or if a status is not one of the four above, so the map cannot drift from the repository. Update the CSV when a row's status changes. The profile-page "what's built and what's next" board is meant to be drawn from this file.

The Spend Lens phases and dates are that prototype's own; they are not v3's phases (see `docs/roadmap.md`).
