-- mart.d_field_availability (dashboard Data & pipeline tab: what the open data holds, v3.1 strategy)
-- Grain: one row per field an audit-grade tracker needs. What: whether the State's open data publishes it, where it exists
-- otherwise, and the plan (built, or the records request that would supply it). From reference/field_availability.csv,
-- checked against the extract of the run; transaction_rows says how many payment-level rows have been loaded (0 until a
-- records request is answered, src/pipeline/txn.py).
CREATE OR REPLACE TABLE mart.d_field_availability AS
SELECT f.*, (SELECT count(*) FROM core.fact_payment_txn) AS transaction_rows
FROM ref.field_availability f;
