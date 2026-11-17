-- mart.d_fund_shift: per program and year, the general / federal / relief / special shares and the change in the general
-- share against two years earlier (the dashboard's latest actual year vs two years before). A program is flagged when its
-- general share rose by at least shift_pp points and it is at least min_program dollars: spending that moved from federal or
-- relief money onto the State's own general fund (the child care pattern DLS describes for FY2023-FY2025).
CREATE OR REPLACE TABLE mart.d_fund_shift AS
WITH p AS (
  SELECT fiscal_year, stage, agency_code, agency, program_code, program_name, max(program_budget) AS program_budget,
         sum(budget) FILTER (WHERE fund_group = 'General') AS general,
         sum(budget) FILTER (WHERE fund_group = 'Federal') AS federal,
         sum(budget) FILTER (WHERE fund_group = 'Federal relief') AS federal_relief,
         sum(budget) FILTER (WHERE fund_group = 'Special') AS special
  FROM mart.d_fund_hierarchy GROUP BY ALL
), s AS (
  SELECT *, coalesce(general, 0) / nullif(program_budget, 0) AS general_share,
         (coalesce(federal, 0) + coalesce(federal_relief, 0)) / nullif(program_budget, 0) AS federal_share
  FROM p
)
SELECT b.*, e.general_share AS general_share_2y_before, e.federal_share AS federal_share_2y_before,
       b.general_share - e.general_share AS general_share_change,
       (b.general_share - e.general_share >= {{fund_hierarchy.shift_pp}} / 100.0 AND b.program_budget >= {{fund_hierarchy.min_program}}) AS shift_to_general
FROM s b LEFT JOIN s e ON e.agency_code = b.agency_code AND e.program_code = b.program_code AND e.program_name = b.program_name
                       AND e.fiscal_year = b.fiscal_year - 2
ORDER BY b.fiscal_year, b.program_budget DESC;
