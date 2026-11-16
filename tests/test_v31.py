"""v3.1: conformal calibration, model registry and drift statistics, payment-level schema."""
import duckdb
import numpy as np
import pandas as pd

from src.models import forecast, registry
from src.pipeline import txn


def test_conformal_k_never_narrows_and_uses_rank_correction():
    assert forecast._conformal_k([0.1, 0.2, 0.3], 0.2) == 1.0  # already inside: never narrowed
    k = forecast._conformal_k(np.arange(1, 11) / 2, 0.2)  # misses 0.5..5.0; rank ceil(11 * 0.8) = 9 -> 4.5
    assert k == 4.5


def test_widen_contains_model_range_and_keeps_median():
    f = pd.DataFrame({"kind": ["Actual", "Forecast"], "p10": [None, 80.0], "p50": [None, 100.0], "p90": [None, 125.0], "value": [1.0, None]})
    w = forecast.widen(f, 2.0)
    r = w.iloc[1]
    assert r.p10 < r.p10_model < r.p50 < r.p90_model < r.p90 and r.p50 == 100
    assert abs(r.p10 - 64) <= 1 and abs(r.p90 - 156) <= 1  # log-symmetric: 100 * (0.8 ** 2), 100 * (1.25 ** 2)


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
