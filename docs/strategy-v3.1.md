# v3.1 strategy: audit-grade data

Four improvements asked for on Nov 14, 2026, built on what the State's open data actually holds, with records requests for the rest. All financial figures are by Maryland fiscal year (July 1–June 30).

| # | Improvement | What the open data supports | Built | Needs a records request |
|---|---|---|---|---|
| 1 | Transaction-level attributes | Nothing below agency x payee x ZIP x year; the date is always January 1 | Fixed schema `core.fact_payment_txn` (`src/pipeline/txn.py`), loads `data/txn/*.csv`; field availability table (`mart.d_field_availability`) | Payment and invoice numbers and dates, fund per payment, line descriptions (Comptroller FMIS; MSDE CCATS) |
| 2 | Fund source and appropriation hierarchy | Fund type and fund source per program (gy87-e27x); federal fund source codes are Assistance Listing numbers | `mart.d_fund_hierarchy`, `d_fund_shift` (shift to the General Fund), `d_federal_crosswalk` (State budget beside USAspending obligations) | Reimbursable funds; fund on each payment |
| 3 | Vendor entity resolution | Payee name as entered and ZIP | `mart.d_vendor_alias` (evidence), `d_vendor_alias_review` (ZIPs disagree; possible missed merges) | Vendor number and tax ID (FMIS vendor file) |
| 4 | Audit and recoupment tracking | OLA reports (findings, repeats); press and agency statements | `reference/audit_findings.csv` → `mart.d_audit_findings`: identified, recouped, waiver and who decided, legal opinion, fund source, confirmation level, source and as-of date | Internal audits, recoupment and waiver records, Attorney General correspondence (MSDE) |

## Guardrails

- Seed the audit register only from public documents; every row has an https source and an as-of date; a blank is unknown, never zero; amounts that may overlap are never added.
- MD-VIEW is used for hand spot checks only, never scraped.
- Leads are never savings. The alias queue changes no mapping by itself; a reviewed decision goes into `reference/vendor_families.csv`.
- State FY and federal FY are set side by side and never added or netted.

## Test case: MSDE Child Care Scholarship

General Fund share of Child Care Assistance Grants: 23% (FY2023), 67% (FY2024), 79% (FY2025, DLS ~78%), as federal relief ended. Reported by FOX45 and republished by WCBM on Oct 28, 2026: $66.5M in suspected overpayments (2023–2025, internal audits not public) and $10.7M in agency-error overpayments to 2,227 providers that MSDE decided not to recoup; a State senator asked the Attorney General's Office whether recovery can be waived. Whether the money was federal CCDF or General Fund is not public, and payment-level records would answer it.

Thresholds: `config/assumptions.yaml` (`fund_hierarchy`, `vendor_alias`). Checks: `phase5_audit_depth` in `src/pipeline/checks.py`.
