# Fiscal-year audit

**0 failed, 0 warnings.** Data: `site_data`

## Calendar (read from the data)

| Fiscal year | Budget stage | Payments |
|---|---|---|
| FY2008 |  | full year |
| FY2009 |  | full year |
| FY2010 |  | full year |
| FY2011 |  | full year |
| FY2012 |  | full year |
| FY2013 |  | full year |
| FY2014 |  | full year |
| FY2015 |  | full year |
| FY2016 |  | full year |
| FY2017 | Actual | full year |
| FY2018 | Actual | full year |
| FY2019 | Actual | full year |
| FY2020 | Actual | full year |
| FY2021 | Actual | full year |
| FY2022 | Actual | full year |
| FY2023 | Actual | full year |
| FY2024 | Actual | full year |
| FY2025 | Actual | full year |
| FY2026 | Working budget | full year |
| FY2027 | Legislative appropriation | partial (year in progress) |

Last actual budget year FY2025; last full payments year FY2026; partial payments year FY2027; grants FY2009-FY2025; forecast FY2017-FY2031.

## 1. Exports: year ranges

- PASS Published payments reach the last year in the State's data (FY2027): published FY2008-FY2027; the open year is published flagged partial
- PASS Published budget reach the last year in the State's data (FY2027): published FY2017-FY2027
- PASS f_function reaches the latest budget year FY2027: FY2017-FY2027
- PASS f_agency reaches the latest budget year FY2027: FY2017-FY2027
- PASS f_scope reaches the latest budget year FY2027: FY2017-FY2027
- PASS f_code reaches the latest budget year FY2027: FY2017-FY2027
- PASS f_object reaches the latest budget year FY2027: FY2017-FY2027
- PASS f_program reaches the latest budget year FY2027: FY2017-FY2027
- PASS f_fund reaches the latest budget year FY2027: FY2017-FY2027
- PASS f_fund_source reaches the latest budget year FY2027: FY2017-FY2027
- PASS d_all_funds reaches the latest budget year FY2027: FY2017-FY2027
- PASS f_overlap reaches the latest budget year FY2027: FY2017-FY2027
- PASS f_budget_vs_pay reaches the latest budget year FY2027: FY2017-FY2027
- PASS f_revenue reaches the latest budget year FY2027: FY2017-FY2027
- PASS d_book_reconciliation reaches the latest budget year FY2027: FY2017-FY2027
- PASS d_fund_shift reaches the latest budget year FY2027: FY2017-FY2027
- PASS d_federal_crosswalk reaches the latest budget year FY2027: FY2017-FY2027
- PASS totals_by_fy reaches the latest payments year FY2027: FY2008-FY2027
- PASS totals_by_fy flags exactly the partial year: flagged [2027]
- PASS f_payee_type reaches the last full payments year FY2026 (the open year is held back by design): FY2008-FY2026
- PASS f_vendor_year reaches the last full payments year FY2026 (the open year is held back by design): FY2008-FY2026
- PASS f_concentration reaches the last full payments year FY2026 (the open year is held back by design): FY2008-FY2026
- PASS f_vendor stays within the payments calendar: FY2022-FY2026
- PASS f_vendor_detail stays within the payments calendar: FY2022-FY2026
- PASS f_vendor_pay stays within the payments calendar: FY2022-FY2026
- PASS d_area_top stays within the payments calendar: FY2022-FY2026
- PASS d_families stays within the payments calendar: FY2022-FY2026
- PASS d_multi stays within the payments calendar: FY2022-FY2026
- PASS d_multi_basis stays within the payments calendar: FY2022-FY2026
- PASS review_queue stays within the payments calendar: FY2011-FY2026
- PASS d_payment_screen_summary stays within the payments calendar: FY2022-FY2026
- PASS f_area budget spending reaches the latest budget year: FY2017-FY2027
- PASS f_area payee spending reaches the last full payments year (open year held back): FY2008-FY2026

## 1b. Exports: yearly totals reconciled across tables

- PASS Payments: f_agency payments are a subset of totals_by_fy every year (matched to an agency): 10 years; matched share 92.7%-96.9%
- PASS Payments: totals_by_fy equals the reconciled data total every year: 20 years
- PASS Payments: every payments year from FY2017 has agency rows
- PASS Payments: every year matches the State's vendor-payments site: 20 years
- PASS Budget: f_function matches f_agency every year: FY2017-FY2027
- PASS Budget FY2027: f_function equals the portal file total in stage_evidence: 65,184,504,124 vs 65,184,504,124
- PASS Budget: f_function equals operatingbudget.maryland.gov every year: 11 years

## Budget, actuals and payments by fiscal year (kept apart: never added or netted)

| FY | Budget stage | Budget (plan) | Actual | Payments to vendors | Budget = State site | Payments = State site | Note |
|---|---|---|---|---|---|---|---|
| FY2027 | Legislative appropriation | $65.18B |  | $18.07B (partial) | yes | yes | legislative appropriation; actuals expected with the FY2029 Governor's budget (January 2028); payments are the year so far (partial) |
| FY2026 | Working budget | $64.83B |  | $45.54B | yes | yes | working budget; actuals expected with the FY2028 Governor's budget (January 2027) |
| FY2025 | Actual |  | $60.54B | $43.70B | yes | yes | actual published; the open data no longer carries this year's appropriation (see the budget books) |
| FY2024 | Actual |  | $59.15B | $40.39B | yes | yes | actual published; the open data no longer carries this year's appropriation (see the budget books) |
| FY2023 | Actual |  | $59.14B | $39.28B | yes | yes | actual published; the open data no longer carries this year's appropriation (see the budget books) |
| FY2022 | Actual |  | $55.92B | $36.66B | yes | yes | actual published; the open data no longer carries this year's appropriation (see the budget books) |
| FY2021 | Actual |  | $49.29B | $34.67B | yes | yes | actual published; the open data no longer carries this year's appropriation (see the budget books) |
| FY2020 | Actual |  | $42.95B | $32.93B | yes | yes | actual published; the open data no longer carries this year's appropriation (see the budget books) |
| FY2019 | Actual |  | $39.18B | $30.32B | yes | yes | actual published; the open data no longer carries this year's appropriation (see the budget books) |
| FY2018 | Actual |  | $37.92B | $29.60B | yes | yes | actual published; the open data no longer carries this year's appropriation (see the budget books) |
| FY2017 | Actual |  | $37.72B | $29.31B | yes | yes | actual published; the open data no longer carries this year's appropriation (see the budget books) |
| FY2016 |  |  |  | $27.36B |  | yes | before the operating budget data (FY2017); payments only |
| FY2015 |  |  |  | $27.19B |  | yes | before the operating budget data (FY2017); payments only |
| FY2014 |  |  |  | $25.28B |  | yes | before the operating budget data (FY2017); payments only |
| FY2013 |  |  |  | $23.51B |  | yes | before the operating budget data (FY2017); payments only |
| FY2012 |  |  |  | $23.16B |  | yes | before the operating budget data (FY2017); payments only |
| FY2011 |  |  |  | $22.93B |  | yes | before the operating budget data (FY2017); payments only |
| FY2010 |  |  |  | $21.54B |  | yes | before the operating budget data (FY2017); payments only |
| FY2009 |  |  |  | $21.33B |  | yes | before the operating budget data (FY2017); payments only |
| FY2008 |  |  |  | $19.88B |  | yes | before the operating budget data (FY2017); payments only |

Operating budget basis (excludes public higher education; the all-funds columns in the CSV add it). Payments leave out payroll and include capital and pass-through money, so they are never added to or netted against the budget.
- PASS Every year's budget and payments equal the State's own sites: 20 years
- PASS No year shows a plan and an actual from the open data at once (one stage per year): 0 years

## 3. Docs

- PASS docs scanned: 34 files; only problems are listed above
