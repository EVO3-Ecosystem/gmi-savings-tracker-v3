-- mart.d_site_reconciliation: every fiscal year's total against the State's Open Finance sites (reference/site_totals.csv)
CREATE OR REPLACE TABLE mart.d_site_reconciliation AS
SELECT s.dataset, s.fiscal_year, s.host, s.url, s.site_total,
       CASE s.dataset WHEN 'budget' THEN b.total ELSE p.total END AS data_total, data_total - s.site_total AS difference,
       coalesce(p.partial, false) AS partial_year, s.checked_on
FROM (SELECT dataset, CAST(fiscal_year AS INTEGER) AS fiscal_year, host, url, CAST(site_total AS DOUBLE) AS site_total, checked_on FROM ref.site_totals) s
LEFT JOIN (SELECT fiscal_year, sum(budget) AS total FROM core.fact_budget GROUP BY 1) b ON s.dataset = 'budget' AND b.fiscal_year = s.fiscal_year
LEFT JOIN (SELECT fiscal_year, sum(amount) AS total, bool_or(partial_year) AS partial FROM core.fact_payment GROUP BY 1) p ON s.dataset = 'payments' AND p.fiscal_year = s.fiscal_year
ORDER BY 1, 2;
