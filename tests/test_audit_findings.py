"""reference/audit_finding_programs.csv ties findings in the audit register (reference/audit_findings.csv) to budget programs.

The register is the one source for a finding's text, amount and recoupment status; this file only says which budget program a finding is about."""
from pathlib import Path

import pandas as pd
import pytest

from src.models import program_screen as PS

ROOT = Path(__file__).resolve().parents[1]
REG = pd.read_csv(ROOT / "reference" / "audit_findings.csv", dtype=str, keep_default_na=False)
LINK = pd.read_csv(ROOT / "reference" / "audit_finding_programs.csv", dtype=str, keep_default_na=False)
COLUMNS = ["finding_id", "agency_code", "unit_name", "program_code", "program_name"]


def test_layout_and_ids():
    assert list(LINK.columns) == COLUMNS
    assert LINK.finding_id.is_unique and (LINK.finding_id != "").all()
    assert (LINK[["agency_code", "unit_name", "program_code", "program_name"]] != "").all().all()


def test_every_linked_finding_is_in_the_register_for_the_same_agency():
    m = LINK.merge(REG[["finding_id", "agency_code"]], on="finding_id", how="left", suffixes=("", "_register"))
    assert m.agency_code_register.notna().all(), "a linked finding is not in the register"
    assert (m.agency_code == m.agency_code_register).all()


def test_linked_programs_exist_in_the_published_data():
    prog = pd.read_csv(ROOT / "site_data" / "f_program.csv", dtype=str)
    have = set(zip(prog.agency_code, prog.unit_name, prog.program_code))
    assert all((r.agency_code, r.unit_name, r.program_code) in have for r in LINK.itertuples())


def test_the_reported_findings_frame_takes_amount_and_status_from_the_register():
    rep = PS.reported_findings()
    assert list(rep.finding_id) == list(LINK.finding_id)
    ten_point_seven = rep[rep.finding_id == "MSDE-CCS-2026-02"].iloc[0]
    assert float(ten_point_seven.amount) == 10_700_000  # $10.7M, not $107M
    assert ten_point_seven.recoupment_status == REG[REG.finding_id == "MSDE-CCS-2026-02"].recoupment_status.iloc[0]


def test_a_link_to_a_finding_that_is_not_in_the_register_is_refused():
    bad = LINK.assign(finding_id=[f"NOT-A-FINDING-{i}" for i in range(len(LINK))])
    with pytest.raises(ValueError, match="not in the register"):
        PS.reported_findings(register=REG, links=bad)
