# Data sources (opendata.maryland.gov)

Full schemas, owners, licences, known issues and the assumptions register are in [data-governance.md](data-governance.md).

| Dataset | ID | Years | Notes |
|---|---|---|---|
| Operating budget | yu65-jmmv | FY2017–FY2027 | Portal `type` column is out of date; stages follow mtp.maryland.gov: FY2017–FY2025 Actual, FY2026 Working, FY2027 Legislative Appropriation |
| Funding source | gy87-e27x | FY2017–FY2027 | Totals equal the budget within $1 |
| Budgeted positions (FTE) | x8qy-486w | FY2017–FY2027 | Extracted through the API like the others; the extract matches the portal's own count and yearly totals. The portal's View Data page has no website download to compare. Portal description still calls FY2026 the Governor's Allowance; stages follow `reference/budget_stage.csv` |
| Payments to vendors | 7syw-q4cy | FY2008–FY2027 | Agency names, not codes; FY2027 is a partial year, published as FYTD; `date` and `fiscal_period` are placeholders. Portal title still reads "FY2008 to FY2024" (checked Nov 20, 2026). Marts keep FY2010 on (`years.history_first_fy`) |
| Grants and loans | absk-avps | FY2009–FY2025 | Year column is `fiscalyear`; portal title "FY2009 to FY2025"; marts keep FY2010 on |
| Public higher education budget | 4mca-332u | FY2017–FY2027 | "Maryland Operating Budget: CUR and CR"; reported separately (`d_all_funds`) and kept out of every savings baseline |

Quirks the code handles: 50,000-row pages drop without a token (use 20,000); sub-object codes in two spellings ("0930"/"930"); object and program codes "1"/"01"; function codes 10–12 carry more than one title (key by title); agency A15 named "…:A15" in FY2026–FY2027.

