-- mart.f_fte: budgeted full-time equivalents exactly as published (x8qy-486w), every agency and fiscal year
-- Grain: one row per fiscal year x agency code.
-- What: FTEs summed from the portal rows with nothing left out, including public higher education (R13, R14, R30, R95),
-- which f_agency leaves out because it holds operating-budget agencies only. in_gmi_baseline is false for higher
-- education (out of every GMI savings baseline, decision D4). Check: every year and agency equals the portal's own sum.
CREATE OR REPLACE TABLE mart.f_fte AS
SELECT f.fiscal_year, coalesce(s.stage, 'Payments only') AS stage, f.agency_code,
       coalesce(n.agency, h.agency_name, r.agency_name) AS agency, sum(f.fte) AS fte,
       f.agency_code NOT IN ('R13', 'R14', 'R30', 'R95') AS in_gmi_baseline
FROM core.fact_fte f
LEFT JOIN ref.dim_stage s USING (fiscal_year)
LEFT JOIN mart.agency_name n USING (agency_code)
LEFT JOIN (SELECT agency_code, any_value(agency_name) AS agency_name FROM core.fact_budget_highered GROUP BY 1) h USING (agency_code)
LEFT JOIN (SELECT trim(agency_code) AS agency_code, arg_max(trim(agency_name), CAST(fiscal_year AS INTEGER)) AS agency_name FROM raw.fte GROUP BY 1) r USING (agency_code)  -- one name per agency (latest), so nothing fans out
GROUP BY f.fiscal_year, s.stage, f.agency_code, n.agency, h.agency_name, r.agency_name;
