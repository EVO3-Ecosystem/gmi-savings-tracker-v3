"""Payment-level (transaction) records: schema and loader (v3.1 strategy, improvement 1).

The State's open payments data (7syw-q4cy) is one row per agency, payee, ZIP and fiscal year. Payment number, invoice
number, invoice date, payment date, fund and line description exist in FMIS and in the agency systems, not in the open
data. This module fixes the schema those records will land in, so the marts and checks are ready when a Public
Information Act request is answered. Files placed in data/txn/*.csv (one per response, header row matching COLUMNS)
are loaded; with none present core.fact_payment_txn is created empty and the Data & pipeline tab says so.

Nothing here scrapes MD-VIEW: that search has no download and is used only for hand spot checks.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TXN = ROOT / "data" / "txn"

# (column, DuckDB type, meaning). fiscal_year is the Maryland fiscal year (July 1 - June 30) of payment_date.
COLUMNS = [
    ("source_file", "VARCHAR", "File in data/txn the row came from (one per records-request response)"),
    ("fiscal_year", "INTEGER", "Maryland fiscal year of the payment date"),
    ("agency_code", "VARCHAR", "Agency code (R00 = MSDE)"),
    ("payment_number", "VARCHAR", "Payment or voucher number"),
    ("payment_date", "DATE", "Date the payment was issued"),
    ("invoice_number", "VARCHAR", "Vendor invoice number"),
    ("invoice_date", "DATE", "Vendor invoice date"),
    ("vendor_number", "VARCHAR", "State vendor number"),
    ("payee_name", "VARCHAR", "Payee name as entered"),
    ("payee_zip", "VARCHAR", "Payee ZIP"),
    ("fund_type", "VARCHAR", "General, Special, Federal or Reimbursable"),
    ("fund_source_code", "VARCHAR", "Fund source; for federal funds the Assistance Listing number"),
    ("program_code", "VARCHAR", "Budget program code"),
    ("object_code", "VARCHAR", "Comptroller object code"),
    ("line_description", "VARCHAR", "Line or payment description"),
    ("amount", "DOUBLE", "Payment amount in dollars"),
]


def build(con):
    """Create core.fact_payment_txn from data/txn/*.csv, or empty with the fixed schema."""
    cols = ", ".join(f"{c} {t}" for c, t, _ in COLUMNS)
    con.execute(f"CREATE TABLE core.fact_payment_txn ({cols})")
    files = sorted(TXN.glob("*.csv")) if TXN.exists() else []
    for f in files:
        names = [c for c, _, _ in COLUMNS if c != "source_file"]
        types = {c: t for c, t, _ in COLUMNS if c != "source_file"}
        con.execute(f"""INSERT INTO core.fact_payment_txn SELECT '{f.name}', {', '.join(names)}
          FROM read_csv('{f.as_posix()}', header = true, columns = {types!r})""")
    return len(files)
