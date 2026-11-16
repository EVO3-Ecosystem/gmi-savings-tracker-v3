"""reference/audit_findings_override.csv: one row per reported finding, with a program, an amount and a recoupment status."""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
F = pd.read_csv(ROOT / "reference" / "audit_findings_override.csv", dtype=str, keep_default_na=False)
STATUSES = {"", "Active", "Waived/Forgiven", "Pending Attorney General Review", "Recovered"}
COLUMNS = ["finding_id", "agency_code", "report_date", "unit_name", "program_code", "program_name", "finding", "amount", "period",
           "recoupment_status", "source", "source_url", "verified", "note"]


def test_layout_ids_and_statuses():
    assert list(F.columns) == COLUMNS
    assert F.finding_id.is_unique and (F.finding_id != "").all()
    assert set(F.recoupment_status) <= STATUSES
    assert (F.finding != "").all() and (F.source != "").all() and F.source_url.str.startswith("https://").all() and (F.verified != "").all()
    assert pd.to_numeric(F.amount[F.amount != ""]).gt(0).all()


def test_agencies_and_programs_exist_in_the_published_data():
    agencies = set(pd.read_csv(ROOT / "reference" / "ola_findings.csv", dtype=str).agency_code)
    assert set(F.agency_code) <= agencies
    prog = pd.read_csv(ROOT / "site_data" / "f_program.csv", dtype=str)
    have = set(zip(prog.agency_code, prog.program_code, prog.program_name))
    named = F[F.program_code != ""]
    assert all((r.agency_code, r.program_code, r.program_name) in have for r in named.itertuples())


def test_an_ola_report_date_must_match_an_ola_row_and_press_findings_carry_none():
    ola = pd.read_csv(ROOT / "reference" / "ola_findings.csv", dtype=str)
    dated = F[F.report_date != ""]
    assert all(((ola.agency_code == r.agency_code) & (ola.report_date == r.report_date)).any() for r in dated.itertuples())
    assert (F[F.source.str.contains("press report")].report_date == "").all()


def test_the_child_care_amount_is_ten_point_seven_million_not_one_hundred_and_seven():
    row = F[F.finding_id == "A002"].iloc[0]
    assert float(row.amount) == 10_700_000 and row.recoupment_status == "Waived/Forgiven"
