"""v3.2 reconciliation with DBM's documents (src/pipeline/books.py): parsers on small extracts in the books' own formats."""
from src.pipeline import books as B

BOOK = """
R00A02.59 Child Care Assistance Grants - Aid To Education
Program Description
Appropriation Statement 2025
Total Expenditure        562,164,604     508,388,410     551,364,599
Net General Fund Expenditure   444,706,564   414,247,835   414,247,835
Special Fund Expenditure         5,609,114    13,488,410     7,616,764
Federal Fund Expenditure       111,157,064    80,652,165   129,500,000
American Rescue Plan Act of 21 Expenditure  691,862  0  0
Total Expenditure        562,164,604     508,388,410     551,364,599
J00J00.41 Operating Program (Including Debt Service) - Non-Budgeted
Total Expenditure        603,600,000     610,000,000     620,000,000
Non-Budgeted Fund Expenditure  603,600,000  610,000,000  620,000,000
Total Expenditure        603,600,000     610,000,000     620,000,000
D12A02.03 Developmental Disabilities Council
Total Expenditure        2,000,000       2,100,000       (50,000)
Federal Fund Expenditure 1,800,000 1,900,000 -
Reimbursable Fund Expenditure 200,000 200,000 (50,000)
Total Expenditure        2,000,000       2,100,000       (50,000)
R00A02.59 Child Care Assistance Grants - Aid To Education
Total Expenditure        48,847,835       1       2
"""


def test_parse_book_takes_each_programs_first_statement_and_its_funds():
    p = B.parse_book(BOOK)
    assert set(p) == {"R00A02.59", "J00J00.41", "D12A02.03"}
    cc = p["R00A02.59"]
    assert cc["total"] == (562164604.0, 508388410.0, 551364599.0)  # the later deficiency section is not read
    assert cc["Net General Fund"][0] == 444706564.0 and cc["American Rescue Plan Act of 21"][0] == 691862.0
    assert p["D12A02.03"]["total"][2] == -50000.0 and p["D12A02.03"]["Federal Fund"][2] == 0.0  # parentheses and dashes


def test_comparable_takes_out_reimbursable_and_non_budgeted_funds():
    p = B.parse_book(BOOK)
    assert B.comparable(p["R00A02.59"], 0) == 562164604.0
    assert B.comparable(p["J00J00.41"], 0) == 0.0  # non-budgeted: not in the State budget
    assert B.comparable(p["D12A02.03"], 0) == 1800000.0 and B.comparable(p["D12A02.03"], 2) == 0.0


def test_amount_reads_commas_parentheses_and_dashes():
    assert B.amount("1,234") == 1234.0 and B.amount("(450,000)") == -450000.0 and B.amount("-12") == -12.0 and B.amount("-") == 0.0


DIGEST = """
A15O0001       19150001   Disparity Grants                                     203,599,585                 -              -    203,599,585               -
F50A0101       2510101    Information Technology Investment Fund                27,831,054        28,000,000             -     55,831,054                  -
Total                     Grand Total                                       27,946,724,016     16,164,712,398 21,073,067,710 65,184,504,124 779,086,832
            Total Deficiencies                                                                 1,056,141,341      88,895,137     1,789,534,349   2,934,570,827
"""


def test_digest_rows_including_a_seven_digit_rstars_code_and_the_grand_total(tmp_path, monkeypatch):
    monkeypatch.setattr(B, "text", lambda url, year, layout=False: DIGEST)
    progs, grand, deficiencies = B.digest(2027)
    assert progs["A15O00.01"][0] == 203599585.0 and progs["F50A01.01"][3] == 55831054.0
    assert grand[:3] == (27946724016.0, 16164712398.0, 21073067710.0)
    assert deficiencies[3] == 2934570827.0


SUPP = """
                                            SUPPLEMENTAL APPROPRIATIONS
Appropriation
 2026 Fiscal Year             89,081,157          250,000         75,474,930               0                0   164,806,087
 2027 Fiscal Year             95,016,972        6,348,797         80,885,766               0                0   182,251,535
Reduction in Appropriation
 2026 Fiscal Year             -74,650,000     -18,232,157         -71,179,064              0                0   -164,061,221
 2027 Fiscal Year            -103,820,732      -3,383,374         -80,885,766              0                0   -188,089,872
"""


def test_supplemental_summary_by_fiscal_year(monkeypatch):
    monkeypatch.setattr(B, "text", lambda url, year, layout=False: SUPP)
    add, cut = B.supplemental("u", 2027)
    assert add == {2026: 164806087.0, 2027: 182251535.0} and cut == {2026: -164061221.0, 2027: -188089872.0}
    assert B.general_supplemental("u", 2027) == {2026: 89081157.0 - 74650000.0, 2027: 95016972.0 - 103820732.0}


def test_reason_labels():
    assert B.reason(False, True, 5.0).startswith("In the open data") and B.reason(True, True, 16.0) == "Rounding (under $100)"
    assert B.reason(True, True, 9000.0) == "Amount differs"


def test_volume_urls_follow_dbms_archive_layout():
    assert B.volumes(2019)[0].endswith("/2019/Proposed/Volume1.pdf") and len(B.volumes(2019)) == 3
    assert B.volumes(2021)[2].endswith("/2021/proposed/FY2021-Volume3.pdf") and len(B.volumes(2027)) == 2
