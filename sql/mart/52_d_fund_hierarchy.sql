-- mart.d_fund_hierarchy (dashboard Budget tab: where the money comes from, improvement 2 of the v3.1 strategy)
-- Grain: one row per fiscal year x budget agency x program x fund type x fund source (gy87-e27x, core.fact_fund).
-- What: the funding-source hierarchy agency -> program -> fund group -> fund type -> fund source, with each line's share of
-- its program. fund_group folds the federal relief types (COVID, ARRA, ARPA, CARES, CRRSA) into "Federal relief" so a program
-- moving from federal or relief money to general funds shows as one shift. assistance_listing is the fund source code when
-- it is a federal Assistance Listing number (NN.NNN, e.g. 93.575 Child Care and Development Block Grant), else NULL.
-- The portal publishes no reimbursable fund type in either budget dataset; none is invented here.
-- Checks: the hierarchy ties to core.fact_fund by year to the dollar; shares sum to 1 per program-year.
CREATE OR REPLACE TABLE mart.d_fund_hierarchy AS
WITH f AS (
  SELECT fiscal_year, agency_code, program_code, program_name, fund_type, fund_source_code, fund_source_name, sum(budget) AS budget
  FROM core.fact_fund GROUP BY ALL
), g AS (
  SELECT *, CASE WHEN fund_type = 'General Funds' THEN 'General'
                 WHEN fund_type = 'Special Funds' THEN 'Special'
                 WHEN fund_type = 'Federal Funds' THEN 'Federal'
                 ELSE 'Federal relief' END AS fund_group,
         CASE WHEN regexp_matches(fund_source_code, '^[0-9]{2}\.[0-9]{3}[A-Z]?$') THEN fund_source_code END AS assistance_listing,
         sum(budget) OVER (PARTITION BY fiscal_year, agency_code, program_code, program_name) AS program_budget
  FROM f
)
SELECT g.fiscal_year, s.stage, g.agency_code, coalesce(a.agency, g.agency_code) AS agency, g.program_code, g.program_name,
       g.fund_group, g.fund_type, g.fund_source_code, g.fund_source_name, g.assistance_listing, g.budget, g.program_budget,
       CASE WHEN g.program_budget <> 0 THEN g.budget / g.program_budget END AS share_of_program
FROM g JOIN ref.dim_stage s USING (fiscal_year) LEFT JOIN mart.agency_name a USING (agency_code)
ORDER BY g.fiscal_year, g.agency_code, g.program_code, g.budget DESC;
