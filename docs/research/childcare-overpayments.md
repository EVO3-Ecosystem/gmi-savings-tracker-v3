# Child care overpayments at the State Department of Education (reported Nov 2026)

A reported finding the tracker did not find, recorded as a reference source and as a test of what the tracker can and cannot see.

**How this was verified.** The article's site is blocked from the environment this was written in, so the pages were not opened. The facts below come from search-result summaries of the Fox45 pages and their WCBM syndication, which agree with each other. Publication dates were not visible and are left out. Anyone citing a figure should open the original first. The article text is not reproduced here; it is the publisher's.

## What was reported

| Figure | What it is | Source |
|---|---|---|
| **$10.7 million** | Child care payments made in error that the department decided not to recoup. Reported as "at least" this much. | [Fox45 Project Baltimore](https://foxbaltimore.com/news/project-baltimore/maryland-taxpayers-107m-childcare-overpayments-state-wont-recoup-funds-dr-carey-wright-dr-joshua-micheal), [WCBM](https://wcbm.com/local-story/maryland-errors-cost-taxpayers-10-7m-in-childcare-overpayments-state-wont-recoup-funds/) |
| $66.5 million | Potential overpayments to child care providers found by the department's internal audits, 2023 to 2025. The department says more than 75% of it was properly paid. | [Fox45](https://foxbaltimore.com/news/project-baltimore/maryland-state-department-of-education-overpaid-childcare-providers-665m-money-not-recouped) |
| $44 million | An online child care system that was awarded and never launched. | [WCBM](https://wcbm.com/local-story/millions-awarded-nothing-delivered-maryland-never-launched-44m-online-childcare-system/) |
| about $560 million | The size of the child care scholarship program. | [Fox45](https://foxbaltimore.com/news/local/marylands-560million-child-care-scholarship-program-email-carey-wright-joshua-michael) |

- **The headline figure is $10.7 million, not $107 million.** The article's URL contains "107m", which is 10.7M without the decimal point.
- The State Superintendent (Dr. Carey Wright) and the President of the State Board of Education (Dr. Joshua Michael) defended the decision not to recoup. The board president is reported as saying the department lacked adequate information systems to track the money.
- A state senator (Jennings, Harford and Baltimore Counties) wrote to the Attorney General's office questioning whether forgiving the overpayments was legal. No answer had been reported.
- These are the department's internal audits as described in press reports. They are **not** Office of Legislative Audits findings, and `reference/ola_findings.csv` does not contain them.

## What the tracker shows

From the published tables of run `20261113T180346Z` (`f_program`, agency R00, unit Aid To Education, program 59), actual spending by fiscal year:

| FY | Program name in the budget data | Actual |
|---|---|---|
| 2017 | Child Care Subsidy Program | $76.9M |
| 2018 | Child Care Subsidy Program | $87.8M |
| 2019 | Child Care Subsidy Program | $101.1M |
| 2020 | Child Care Scholarship Program | $248.4M |
| 2021 | Child Care Assistance Grants | $196.9M |
| 2022 | Child Care Assistance Grants | $499.6M |
| 2023 | Child Care Assistance Grants | $338.0M |
| 2024 | Child Care Assistance Grants | $412.0M |
| 2025 | Child Care Assistance Grants | $562.2M |

FY2026 working budget: $557.2M. FY2027 legislative appropriation: $577.9M. The figure `docs/figures/overview/childcare_program.png` draws this series.

- **Confirmed: the program's size.** $562.2M in FY2025 matches the "about $560 million" in the reporting.
- **Confirmed: the growth.** Spending rose more than sevenfold from FY2017 to FY2025, with a fall of about a third from FY2022 to FY2023 and a rise of about a third from FY2024 to FY2025.
- **Not confirmed: $10.7M, $66.5M, $44M.** Nothing in the open data states or implies these amounts.

## Could the tracker have detected it?

No, not this problem.

- An overpayment to a provider is a payment that looks ordinary in a total. Finding it needs each payment with the attendance or eligibility record behind it. The open payments data is one total per payee, agency and year.
- The opportunity detectors work on controllable purchases. Child care grants are aid, not purchases, so no detector looks at them.
- What the tracker can do is say where to look: a program that grew sevenfold in eight years and swings by a third from one year to the next is a reasonable place to ask for payment-level records. That is context, not a finding.

## The same reading, applied to every program

The child care program is one case. `src/models/program_screen.py` applies the same two measures to every program of every agency with five or more actual years and at least $10M in its last one: how many times it grew, and its largest change from one year to the next. On the published data, 298 programs across 50 agencies are screened and 75 cross both thresholds (2x growth, a 30% swing). Child care is the sixth largest of those. The largest are two Department of Health programs at over $3B each. The figure is `docs/figures/overview/program_screen.png`; the table is `mart.d_program_screen`.

Many flagged programs have ordinary explanations: federal relief money in FY2021 and FY2022, reserve accounts filled and emptied by design, a new law phasing in. The screen orders the questions; it does not answer them.

## What would make it detectable

1. Payment-level child care scholarship records from the department (provider, month, children, rate, amount), by Public Information Act request.
2. The internal audit reports themselves, to replace press summaries with the audit's own figures and method.
3. `reference/audit_finding_programs.csv`: ties each finding in the audit register (`reference/audit_findings.csv`, the one source for the finding, its amount and its recoupment status) to a budget program, so reported findings sit beside the spending they concern. The two overpayment findings above are linked to the Child Care Assistance Grants program. The $44 million never-launched online system is a press report of an award that delivered nothing, not an overpayment, so it is not in the register and not linked to a program; it stays here as context.
