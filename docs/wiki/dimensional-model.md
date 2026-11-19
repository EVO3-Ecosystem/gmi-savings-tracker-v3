# Dimensional alignment review: Agency, Unit, Program, Subprogram, Fund, Expenditure Type, Fiscal Year

Review of the [datamart map](datamart-map-fy2010-2027.md) against financial-dashboard best practice (November 19, 2026), placed explicitly on the repo's medallion layers. The test: can every feed be cut by the same conformed dimensions, at a declared grain, without mixing budget stages or fiscal years — and does each piece of logic live in the right layer? Column names below are the feeds' actual SODA fields.

## 0. Medallion layer mapping

The repo's DuckDB layers already implement the Bronze/Silver/Gold pattern. This review assigns every recommendation to a layer, and the rule is strict: **no dimensional modeling in Bronze.**

| Medallion | Repo layer | Responsibility | What lives here |
|---|---|---|---|
| **Bronze** | `raw` (+ `data/raw/<run_id>/` Parquet) | Source fidelity and auditability: payloads as published, plus ingestion metadata only | One Parquet per dataset per run, `manifest.json`, `_run_id` lineage, portal row-count/total/timestamp validation. **No** business grain, surrogate keys, SCD logic, or renames — replay must always reproduce source truth. SODA system fields (`:id`, `:updated_at`) are kept here as change-tracking fields for later history reconstruction |
| **Silver** | `ref` + `core` | Deduplication, typing, conformance: the cleaned single version of each feed and the reviewed rules that shape it | FY text→integer casts (school feed), alias conformance (`payment_agency_rules`, `grantor_agency_aliases`, `mfr_agency_map`), agency-rename resolution, stage assignment from `reference/budget_stage.csv`, SCD2 conformance of dimension history (`valid_from_fy`/`valid_to_fy`), code-stability checks |
| **Gold** | `mart` (+ published `site_data/`) | Read-optimized dimensional models for the dashboard, MCP server and briefs | The seven conformed dims (`dim_agency`, `dim_program`, `dim_subprogram`, `dim_unit`, `dim_fund`, `dim_expenditure_type`, `dim_commodity`, `dim_fiscal_year` with stage/status) and declared-grain facts (`fact_budget`, fact views over payments/grants/FTE). Every dashboard table and the metric registry read only from here |
| ops | `ops` | Pipeline evidence | Checks, runs, lineage — not a data layer |

Two edge cases from the medallion guidance apply directly:

- **Upstream modeled inputs:** the State's feeds arrive as published tabular models (the budget feed is already shaped like a fact with dimension columns). They still land in Bronze as raw inputs under the ingestion contract (manifest, portal checks) — their shape is a property of the source, never a license to skip Silver conformance.
- **eMM bids family:** each per-FY dataset is a separate raw input with its own manifest (schemas drift year to year); per-year files in Bronze, one conformed bids table in Silver, a `dim_commodity` (NIGP) + bids fact in Gold.

## 1. Dimension coverage scorecard

✓ present · ◐ partial or derived · — absent

| Dimension | budget `yu65-jmmv` | fund `gy87-e27x` | fte `x8qy-486w` | highered `4mca-332u` | payments `7syw-q4cy` | grants `absk-avps` | school `t6vk-rvwe` | eMM bids |
|---|---|---|---|---|---|---|---|---|
| **Agency** | ✓ `agency_code` + name | ✓ code + name | ✓ code + name | ✓ code + name | ◐ `agency_name` text only | ◐ `grantor` text only | ◐ county board text | ◐ `department`/`organization` text |
| **Program** | ✓ `program_code` + name | ✓ code + name | ✓ code + name | ✓ code + name | — | — | — | — |
| **Subprogram** | ✓ `subprogram_code` + name | — | — | ✓ code + name | — | — | — | — |
| **Unit** | ✓ `unit_code` + name | ✓ code + name | ✓ code + name | ✓ code + name | — | — | — | ◐ org/location fields |
| **Fund** | ✓ `fund_type_name` | ✓✓ `fund_type_name` + `fund_source_code` | — | ✓ CUR/CR funds | — | — | — | — |
| **Expenditure type** | ✓✓ `object_code` + `comptroller_subobject` + `agency_subobject` | — | — | ✓✓ same object hierarchy | — | — | — | ◐ NIGP class/item commodity codes |
| **Fiscal year** | ✓ + stage (`type`) | ✓ + stage | ✓ + stage | ✓ + stage | ✓ + `fiscal_period` | ✓ + `fiscalperiod` | ◐ FY stored as text | ✓ per-FY datasets |

Two structural facts drive everything else:

1. **The budget family carries the full chart of accounts; the money-out feeds carry only agency.** Payments and grants can answer *who was paid, by which agency, in which FY* — never *which program, unit, fund, or expenditure type*. That is a property of the public feeds, not of the pipeline (payment-level FMIS fields are the PIA item in the README).
2. **Expenditure type exists only where money is planned, not where it is spent.** The object → Comptroller subobject → agency subobject hierarchy is the statewide expenditure classification, and it lives in the budget feeds alone. The eMM bids' NIGP commodity codes are the only spending-side classification available, FY2014 forward, procurement-only.

## 2. Gaps against best practice (each assigned to its layer)

**G1 · Grain asymmetry between plan and actual (highest impact) — Gold contract.** Best practice declares a grain per fact table and forbids drilling a dashboard below the coarsest joined fact. Public data supports budget-vs-actual variance **at agency × FY only**; the dashboard must cap payments/grants drill-downs there and label program-level views as budget-side-only. The repo mostly does this; the gap is that declared grain is implicit in SQL files rather than stated in one place. *Fix (Gold):* add a `grain` column to the catalog/`reference/datamart_catalog.csv` and test it in the build.

**G2 · Conformed dimensions are implicit, not materialized — Gold build, Silver conformance.** Named dimension marts — `dim_agency`, `dim_program`, `dim_subprogram`, `dim_unit`, `dim_fund`, `dim_expenditure_type`, `dim_fiscal_year` — that every Gold fact joins to. The repo has the substance spread across reference files and mart SQL. *Fix:* dimension history is conformed in Silver (dedup, rename resolution, SCD2 windows); the denormalized read-optimized dims are materialized in Gold; `catalog.html` points at them.

**G3 · Code stability across years (SCD) — Silver.** Maryland's category→program→subprogram→unit codes can be re-purposed between budget years; joining on code alone silently misattributes history. *Fix (Silver):* dimension keys composite with fiscal year, or SCD2 with `valid_from_fy`/`valid_to_fy`; add a stop check for a code whose name changes year over year without a rename record. Bronze keeps the raw rows untouched so any SCD decision can be replayed.

**G4 · Text-keyed agencies on the money-out feeds — Silver.** Payments `agency_name`, grants `grantor`, school board names and eMM departments are free text. The repo governs this correctly through reviewed alias CSVs; the eMM family has no alias table yet. *Fix:* alias-table-first rule (an alias seed lands in `reference/` and is applied in Silver **before** the feed may reach Gold); eMM alias seed when the family is pinned.

**G5 · Expenditure type on the spending side — Gold model, Silver conformance.** Cannot be closed from public data for payments/grants (PIA route). Partially addressable: NIGP class/item from eMM gives a commodity cut for procured spending FY2014+. *Fix:* extract eMM (gap-analysis P2-1); conform NIGP codes in Silver; model `dim_commodity` in Gold, clearly separated from `dim_expenditure_type`.

**G6 · Fiscal-year typing and stage discipline — Silver typing, Gold dimension.** School feed stores FY as text; portal stage labels are stale and stages correctly come from DBM's books. *Fix:* cast-on-conform in Silver for the school feed (when adopted); `dim_fiscal_year` in Gold carries stage (actual/working/allowance/appropriation) and status (closed/partial), with the hard rule that one chart shows one stage.

**G7 · Fiscal period is present but unusable — nowhere, by design.** Payments carries `fiscal_period`, but the date is always January 1 (annual aggregates), so monthly views would be fiction. *Fix:* none — keep the stop-check-backed rule that no monthly visualization ships until payment-level records arrive. Bronze preserves `fiscal_period` as a source field regardless.

## 3. Already aligned (keep doing)

- **Bronze purity** — raw Parquet snapshots with manifests and portal validation; replay-safe, no business logic at ingest.
- **Control totals and reconciliation to independent sources** — DBM books, Fiscal Digest, Open Finance sites to the cent, re-tested every build. The practice most public-sector dashboards skip, and the repo's strongest suit.
- **Certified metrics layer** — the metric registry (`src/models/metrics.py`) reads Gold only: one definition, everywhere.
- **Column dictionary at 100% coverage** and review-gated reference CSVs — the governance pattern the Silver alias tables depend on.
- **Stage separation** — FY2026 working and FY2027 appropriation are never presented as actuals.
- **Aggregate-not-transaction labeling** — payments/grants are always described as yearly totals per payee.

## 4. Bottom line for the FY2010–FY2027 mapping

The mapping is dimensionally sound: the six pinned feeds plus the school feed cover every dimension the public data can carry, and the eMM family is the correct next addition because it is the only feed that adds a new dimension (commodity) rather than more of the same rows. The FY2010–FY2016 hole and the program/unit/fund/expenditure-type holes on the money-out side are source limitations, not mapping errors — the right response is the archival-books schema (P1-1) and the PIA schema (P1-2), both already scoped. Every fix above lands in Silver or Gold; Bronze stays raw.
