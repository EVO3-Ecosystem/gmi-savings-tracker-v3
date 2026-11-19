# Dimensional alignment review: Agency, Unit, Program, Subprogram, Fund, Expenditure Type, Fiscal Year

Review of the [datamart map](datamart-map-fy2010-2027.md) against financial-dashboard best practice (November 19, 2026). The test: can every feed be cut by the same conformed dimensions, at a declared grain, without mixing budget stages or fiscal years? Column names below are the feeds' actual SODA fields.

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

## 2. Gaps against best practice

**G1 · Grain asymmetry between plan and actual (highest impact).** Best practice declares a grain per fact table and forbids drilling a dashboard below the coarsest joined fact. Public data supports budget-vs-actual variance **at agency × FY only**; the dashboard must cap payments/grants drill-downs there and label program-level views as budget-side-only. The repo mostly does this (payments map to agencies through `reference/payment_agency_rules.csv`); the gap is that the *declared grain per mart* is implicit in SQL files rather than stated in one place. *Fix:* add a `grain` column to the catalog page/`reference/datamart_catalog.csv` and test it.

**G2 · Conformed dimensions are implicit, not materialized.** Best practice is named dimension marts — `dim_agency`, `dim_program`, `dim_subprogram`, `dim_unit`, `dim_fund`, `dim_expenditure_type`, `dim_fiscal_year` — that every fact joins to. The repo has the substance (agency master with rename handling, `vendor_families`, `budget_stage.csv`, the fund hierarchy work in v3.1) but spread across reference files and mart SQL. *Fix:* materialize the seven dims as mart tables with a documented key each; point `catalog.html` at them.

**G3 · Code stability across years (SCD).** Maryland's category→program→subprogram→unit codes can be re-purposed between budget years. A dashboard joining on code alone will silently misattribute history. *Fix:* dimension keys composite with fiscal year, or SCD2 on the dims with `valid_from_fy`/`valid_to_fy`; add a stop check for a code whose name changes year over year without a rename record.

**G4 · Text-keyed agencies on the money-out feeds.** Payments `agency_name`, grants `grantor`, school board names and eMM departments are free text. The repo already governs this the right way (reviewed alias CSVs: `payment_agency_rules`, `grantor_agency_aliases`, `mfr_agency_map`) — the gap is the eMM family has no alias table yet, and every new text-keyed feed needs one before extraction. *Fix:* alias-table-first rule in the wiki; eMM alias seed when the family is pinned.

**G5 · Expenditure type on the spending side.** Cannot be closed from public data for payments/grants (PIA route). Partially addressable: NIGP class/item from the eMM family gives a commodity cut for procured spending FY2014+; the budget-side object hierarchy gives *intent*. *Fix:* extract the eMM family (gap-analysis P2-1) and model NIGP as `dim_commodity`, clearly separated from `dim_expenditure_type`.

**G6 · Fiscal-year typing and stage discipline.** School feed stores FY as text; budget-family stage labels on the portal are stale and the repo correctly sources stages from DBM's books. Best practice: a `dim_fiscal_year` carrying stage (actual/working/allowance/appropriation) and status (closed/partial), with a hard rule that one chart shows one stage. *Fix:* cast-on-extract for the school feed (when adopted) and fold stage/status into `dim_fiscal_year`.

**G7 · Fiscal period is present but unusable.** Payments carries `fiscal_period`, but the date is always January 1 (annual aggregates), so monthly/period views would be fiction. The repo correctly suppresses timing analyses. *Fix:* none — keep the stop-check-backed rule that no monthly visualization ships until payment-level records arrive.

## 3. Already aligned (keep doing)

- **Control totals and reconciliation to independent sources** — DBM books, Fiscal Digest, Open Finance sites to the cent, re-tested every build. This is the practice most public-sector dashboards skip, and it is the repo's strongest suit.
- **Certified metrics layer** — the metric registry (`src/models/metrics.py`) is the "one definition, everywhere" pattern.
- **Column dictionary at 100% coverage** and review-gated reference CSVs — the governance pattern alias tables in G4 depend on.
- **Stage separation** — FY2026 working and FY2027 appropriation are never presented as actuals.
- **Aggregate-not-transaction labeling** — payments/grants are always described as yearly totals per payee.

## 4. Bottom line for the FY2010–FY2027 mapping

The mapping is dimensionally sound: the six pinned feeds plus the school feed cover every dimension the public data can carry, and the eMM family is the correct next addition because it is the only feed that adds a new dimension (commodity) rather than more of the same rows. The FY2010–FY2016 hole and the program/unit/fund/expenditure-type holes on the money-out side are source limitations, not mapping errors — the right response is the archival-books schema (P1-1) and the PIA schema (P1-2), both already scoped.
