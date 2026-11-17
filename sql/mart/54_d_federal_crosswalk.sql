-- mart.d_federal_crosswalk (dashboard Budget tab: federal cross-check, improvement 2 of the v3.1 strategy)
-- Grain: one row per State fiscal year x federal Assistance Listing number that the State budget funds (d_fund_hierarchy).
-- What: the State budget's federal fund sources for that listing (all agencies and programs) next to USAspending's federal
-- grant obligations (award types 02-05) to government recipients in Maryland for the same listing (raw.federal_by_listing).
-- Years: the federal fiscal year runs Oct-Sep and Maryland's Jul-Jun; FFY N is set beside State FY N (they overlap nine
-- months) and the two are never added. Obligations are not spending, and they include local governments, so a ratio away
-- from 1 is a question to ask (timing, pass-through, misclassification), not an error. federal_reported = FALSE when the
-- listing has no USAspending row for that year (not yet reported, or no award).
CREATE OR REPLACE TABLE mart.d_federal_crosswalk AS
WITH st AS (
  SELECT fiscal_year, stage, assistance_listing AS listing, any_value(fund_source_name) AS listing_name,
         sum(budget) AS state_federal_budget, count(DISTINCT agency_code) AS agencies, count(DISTINCT program_code || program_name) AS programs
  FROM mart.d_fund_hierarchy WHERE assistance_listing IS NOT NULL GROUP BY ALL
), us AS (
  SELECT federal_fy, listing, sum(obligated) AS federal_obligated, bool_or(partial) AS partial
  FROM raw.federal_by_listing GROUP BY ALL
)
SELECT st.fiscal_year, st.stage, st.listing, st.listing_name, st.agencies, st.programs, st.state_federal_budget,
       us.federal_obligated, us.federal_obligated IS NOT NULL AS federal_reported, coalesce(us.partial, FALSE) AS federal_partial,
       CASE WHEN us.federal_obligated > 0 THEN st.state_federal_budget / us.federal_obligated END AS budget_to_obligated
FROM st LEFT JOIN us ON us.listing = st.listing AND us.federal_fy = st.fiscal_year
ORDER BY st.fiscal_year, st.state_federal_budget DESC;
