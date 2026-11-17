-- mart.d_vendor_alias (dashboard Vendors tab: payee alias evidence, improvement 3 of the v3.1 strategy)
-- Grain: one row per company (ref.map_payee_vendor.vendor) x payee name as entered x ZIP, over all payment years.
-- What: the evidence behind each name-to-company mapping: every spelling an agency clerk entered, with its ZIP, how many
-- agencies used it, its years and dollars, and the rule that mapped it (name = normalization, family = reviewed company
-- family, reference/vendor_families.csv). The payments data carries no vendor number or tax ID, so name and ZIP are the
-- only keys the public data offers; a vendor number would come from the FMIS vendor file (records request).
CREATE OR REPLACE TABLE mart.d_vendor_alias AS
SELECT m.vendor, t.payee_type, p.vendor_name_as_paid AS payee_name, coalesce(nullif(trim(p.vendor_zip), ''), '(none)') AS zip, m.rule,
       count(DISTINCT p.agency_code) AS agencies, min(p.fiscal_year) AS first_fy, max(p.fiscal_year) AS last_fy,
       round(sum(p.amount), 2) AS paid, count(*) AS records
FROM core.fact_payment_mapped p JOIN ref.map_payee_vendor m ON m.payee = p.vendor_name_as_paid
LEFT JOIN mart.vendor_type t ON t.vendor = m.vendor
WHERE NOT m.is_government AND coalesce(t.payee_type, '') <> 'Government'  -- State agencies, pension funds, courts: not vendors
GROUP BY ALL HAVING sum(p.amount) >= {{vendor_alias.min_paid}}
ORDER BY m.vendor, paid DESC;
