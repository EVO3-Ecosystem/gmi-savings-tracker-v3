-- mart.f_vendor_pay (dashboard Vendors tab and vendor pages)
-- Grain: one row per listed vendor (mart.d_vendors) x paying agency x fiscal year, FY2010 (years.history_first_fy) to the open year (flagged partial at export).
-- Check: totals by vendor and year equal mart.d_vendors' year columns (payments with no agency included as agency NULL).
CREATE OR REPLACE TABLE mart.f_vendor_pay AS
SELECT v.vendor, v.agency_code, v.fiscal_year, sum(v.paid) AS paid
FROM mart.vendor_agency_year v JOIN mart.d_vendors d USING (vendor)
WHERE v.fiscal_year >= {{years.history_first_fy}} GROUP BY ALL;
