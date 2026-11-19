-- yoy: keys=agency_code values=controllable,fte,controllable_per_fte stage good=lower
-- Dashboard file agency_year: per agency and budget year: operating spending, controllable purchases, positions,
-- payments (all payees) and controllable purchases per position.
-- Years: budget years (FY2017 on, by source) plus every payments year from years.history_first_fy (FY2010), so a budget
-- agency's payments are kept for FY2010-FY2016 too, with stage 'Payments only' and no budget, positions or controllable.
WITH b AS (SELECT agency_code, fiscal_year, sum(budget) AS operating_spending, coalesce(sum(budget) FILTER (WHERE controllable), 0) AS controllable
           FROM core.fact_budget_scope GROUP BY ALL),
f AS (SELECT agency_code, fiscal_year, sum(fte) AS fte FROM core.fact_fte GROUP BY ALL),
p AS (SELECT agency_code, fiscal_year, sum(amount) AS payments FROM mart.payment_area
      WHERE agency_code IS NOT NULL AND fiscal_year >= {{years.history_first_fy}} AND agency_code IN (SELECT agency_code FROM b) GROUP BY ALL),
k AS (SELECT agency_code, fiscal_year FROM b UNION SELECT agency_code, fiscal_year FROM p)
SELECT k.agency_code, n.agency, k.fiscal_year, coalesce(s.stage, 'Payments only') AS stage, b.operating_spending, b.controllable, f.fte, p.payments,
       CASE WHEN f.fte > 0 THEN b.controllable / f.fte END AS controllable_per_fte
FROM k LEFT JOIN b USING (agency_code, fiscal_year) LEFT JOIN ref.dim_stage s USING (fiscal_year) LEFT JOIN mart.agency_name n USING (agency_code)
LEFT JOIN f USING (agency_code, fiscal_year) LEFT JOIN p USING (agency_code, fiscal_year)
WHERE b.agency_code IS NOT NULL OR s.stage IS NULL  -- payments-only rows only for years with no budget data
