-- mart.d_book_program_differences (dashboard Data & pipeline tab, v3.2): every program whose amount differs from DBM's
-- book or Fiscal Digest by $0.50 or more, with the reason. From reference/book_program_differences.csv (src/pipeline/books.py).
CREATE OR REPLACE TABLE mart.d_book_program_differences AS
SELECT CAST(fiscal_year AS INTEGER) AS fiscal_year, program, nullif(agency, '') AS agency, nullif(program_name, '') AS program_name,
       try_cast(book AS DOUBLE) AS book, try_cast(data AS DOUBLE) AS data, try_cast(difference AS DOUBLE) AS difference, reason, source
FROM ref.book_program_differences
ORDER BY abs(try_cast(difference AS DOUBLE)) DESC;
