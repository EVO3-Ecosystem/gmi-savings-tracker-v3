-- mart.d_vendor_alias_review (dashboard Vendors tab: alias review queue, improvement 3 of the v3.1 strategy)
-- Grain: one row per review item. Two kinds, both leads for a reviewer, neither changes a mapping by itself:
--   'ZIPs disagree': a multi-name company family whose spellings were paid at ZIPs in more than one 3-digit ZIP area (a
--     subsidiary, a branch, or a wrong merge); lists the areas.
--   'Possible missed merge': two companies, each paid at least vendor_alias.min_paid, whose normalized names share their first
--     vendor_alias.stem_tokens words and a ZIP, but are mapped to different companies (a family the reference file lacks); paid is the smaller company's dollars,
--     the most a merge could move.
-- A reviewed decision goes into reference/vendor_families.csv; the queue then empties for that item.
CREATE OR REPLACE TABLE mart.d_vendor_alias_review AS
WITH a AS (SELECT * FROM mart.d_vendor_alias WHERE regexp_matches(zip, '^[0-9]{5}')),  -- a usable ZIP only
fam AS (
  SELECT vendor, count(DISTINCT payee_name) AS names, count(DISTINCT left(zip, 3)) AS zip3s,
         string_agg(DISTINCT left(zip, 3), ', ' ORDER BY left(zip, 3)) AS zip3_list, sum(paid) AS paid
  FROM a GROUP BY vendor
), stem AS (
  SELECT vendor, zip, sum(paid) AS paid,
         array_to_string(list_slice(string_split(regexp_replace(upper(vendor), '[^A-Z0-9 ]', ' ', 'g'), ' ')
                                   .list_filter(lambda x: x <> ''), 1, {{vendor_alias.stem_tokens}}), ' ') AS stem
  FROM a GROUP BY vendor, zip
), pairs AS (
  SELECT x.stem, x.zip, x.vendor AS vendor_a, y.vendor AS vendor_b, x.paid AS paid_a, y.paid AS paid_b
  FROM stem x JOIN stem y ON x.stem = y.stem AND x.zip = y.zip AND x.vendor < y.vendor
  WHERE length(x.stem) >= 4 AND len(string_split(x.stem, ' ')) >= {{vendor_alias.stem_tokens}}
)
SELECT 'ZIPs disagree' AS kind, vendor AS company, NULL AS other_company, names, zip3s, zip3_list AS evidence, paid
FROM fam WHERE names >= 2 AND zip3s >= 2
UNION ALL
SELECT 'Possible missed merge', vendor_a, vendor_b, NULL, NULL, 'same first words "' || stem || '" and ZIP ' || zip, least(paid_a, paid_b)
FROM pairs
ORDER BY kind, paid DESC;
