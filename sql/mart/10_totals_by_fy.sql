-- yoy: keys=none values=total_payments
-- Dashboard file totals_by_fy: all payments per fiscal year, rows, paying agencies, vendors.
-- partial_year marks the open (incomplete) year from core.fact_payment; the page tags it FYTD and the export
-- leaves its year-over-year change empty (a part-year against a full year is not a change).
WITH py AS (SELECT fiscal_year, bool_or(partial_year) AS partial_year FROM core.fact_payment GROUP BY 1)
SELECT p.fiscal_year, sum(p.amount) AS total_payments, count(*) AS payment_records, count(DISTINCT p.agency_code) AS agencies, count(DISTINCT p.vendor) AS vendors,
       bool_or(py.partial_year) AS partial_year
FROM mart.payment_area p JOIN py ON py.fiscal_year = p.fiscal_year GROUP BY 1
