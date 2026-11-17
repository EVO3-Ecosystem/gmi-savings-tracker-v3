-- mart.d_book_reconciliation (dashboard Data & pipeline tab: every year reconciled with DBM's own documents, v3.2)
-- Grain: one row per fiscal year and basis in reference/book_reconciliation.csv (written by src/pipeline/books.py from
-- DBM's budget books, the FY2027 Fiscal Digest, the supplemental budgets and the conference committee report).
-- What: the book figure, the data figure computed from this build, and the difference. Basis:
--   All funds, operating + higher education: core.fact_budget_all_funds (yu65-jmmv + 4mca-332u); the book side is
--     Total Expenditure less reimbursable and non-budgeted funds, which the State budget does not appropriate.
--   General / Special / Federal funds (FY2027): the data by fund (federal includes federal relief funds; higher
--     education's own funds are outside the Fiscal Digest's Exhibit B).
-- kind: reconcile (must agree), bridge (FY2026: appropriation + enacted deficiencies; the remainder is budget amendments
-- no document prints until the FY2028 books), walk (FY2027 from the allowance; the remainder is the Legislature's action).
CREATE OR REPLACE TABLE mart.d_book_reconciliation AS
WITH f AS (
  SELECT fiscal_year,
         sum(budget) AS all_funds,
         sum(budget) FILTER (WHERE fund_type = 'General Funds') AS general,
         sum(budget) FILTER (WHERE fund_type = 'Special Funds') AS special,
         sum(budget) FILTER (WHERE fund_type NOT IN ('General Funds', 'Special Funds', 'Current Unrestricted Funds', 'Current Restricted Funds')) AS federal
  FROM core.fact_budget_all_funds GROUP BY 1
)
SELECT r.fiscal_year, r.stage, r.basis, r.kind, r.source_document, r.url, r.book_total_expenditure, r.book_reimbursable, r.book_non_budgeted,
       r.book_comparable, r.bridge_items, r.book_comparable + coalesce(r.bridge_items, 0) AS book_side,
       CASE r.basis WHEN 'General funds' THEN f.general WHEN 'Special funds' THEN f.special WHEN 'Federal funds' THEN f.federal ELSE f.all_funds END AS data_total,
       data_total - book_side AS difference, difference / nullif(book_side, 0) AS difference_share,
       r.programs_in_both, r.programs_exact, r.programs_exact / nullif(r.programs_in_both, 0) AS exact_share,
       (SELECT count(*) FROM ref.book_program_differences d WHERE CAST(d.fiscal_year AS INTEGER) = r.fiscal_year AND d.reason <> 'Rounding (under $100)') AS programs_differing,
       CASE WHEN r.kind <> 'reconcile' THEN 'Explained remainder'
            WHEN abs(difference) <= {{books.tolerance_share}} * abs(book_side) AND coalesce(exact_share, 1) >= {{books.min_exact}} THEN 'Reconciles'
            ELSE 'Does not reconcile' END AS status,
       r.checked_on
FROM (SELECT CAST(fiscal_year AS INTEGER) AS fiscal_year, stage, basis, kind, source_document, url,
             try_cast(book_total_expenditure AS DOUBLE) AS book_total_expenditure, try_cast(book_reimbursable AS DOUBLE) AS book_reimbursable,
             try_cast(book_non_budgeted AS DOUBLE) AS book_non_budgeted, try_cast(book_comparable AS DOUBLE) AS book_comparable,
             try_cast(bridge_items AS DOUBLE) AS bridge_items, try_cast(programs_in_both AS DOUBLE) AS programs_in_both,
             try_cast(programs_exact AS DOUBLE) AS programs_exact, checked_on
      FROM ref.book_reconciliation) r LEFT JOIN f USING (fiscal_year)
ORDER BY r.fiscal_year, r.kind DESC, r.basis;
