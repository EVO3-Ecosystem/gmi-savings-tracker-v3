"""v3.1: model registry and drift statistics, payment-level schema (calibration is tested in tests/test_calibration.py)."""
import duckdb
import numpy as np
import pandas as pd

from src.models import registry
from src.pipeline import txn


def test_psi_zero_for_same_and_large_for_shifted():
    rng = np.random.default_rng(0)
    a = rng.normal(size=5000)
    edges = np.quantile(a, np.linspace(0, 1, 11))
    edges[0], edges[-1] = -np.inf, np.inf
    assert registry.psi(a, a, edges) < 1e-9
    assert registry.psi(a, a + 1.0, edges) > 0.25
    assert registry.level(0.05) == "Stable" and registry.level(0.2) == "Moderate shift" and registry.level(0.3) == "Major shift"


def test_ks_matches_definition():
    assert registry.ks(np.array([1.0, 2, 3]), np.array([1.0, 2, 3])) == 0
    assert registry.ks(np.array([1.0, 2]), np.array([3.0, 4])) == 1


def test_psi_shares_handles_new_categories():
    a = pd.Series({"A": 50.0, "B": 50.0})
    assert registry.psi_shares(a, a) < 1e-9
    assert registry.psi_shares(a, pd.Series({"A": 50.0, "C": 50.0})) > 0.25


def test_txn_schema_empty_then_loads(tmp_path, monkeypatch):
    con = duckdb.connect()
    con.execute("CREATE SCHEMA core")
    monkeypatch.setattr(txn, "TXN", tmp_path)
    assert txn.build(con) == 0 and con.execute("SELECT count(*) FROM core.fact_payment_txn").fetchone()[0] == 0
    cols = [c for c, _, _ in txn.COLUMNS if c != "source_file"]
    row = {c: "" for c in cols} | {"fiscal_year": "2025", "agency_code": "R00", "payment_date": "2024-08-01", "invoice_date": "2024-07-15", "amount": "125.5"}
    pd.DataFrame([row])[cols].to_csv(tmp_path / "comptroller_2026.csv", index=False)
    con.execute("DROP TABLE core.fact_payment_txn")
    assert txn.build(con) == 1
    got = con.execute("SELECT source_file, fiscal_year, payment_date, amount FROM core.fact_payment_txn").fetchone()
    assert got[0] == "comptroller_2026.csv" and got[1] == 2025 and str(got[2]) == "2024-08-01" and got[3] == 125.5
