# Walkthrough review for the Governor's office and GMI (Nov 18, 2026)

**What was reviewed:** `notebooks/walkthrough.html` (rendered from `notebooks/walkthrough.ipynb` by `make notebook`), as committed on `main` at `af975a3`.
**Audience asked for:** the Governor and GMI. The walkthrough's own opening says it is written for "budget analysts, auditors and interested residents", so the audience is the first gap.

## How this was done, and its limits

- The walkthrough was read and measured directly: headings, word count, a reading-grade estimate, figure and table counts, accessibility features, and a full re-execution from the published tables.
- Two research passes (executive-report practice; audit-style analysis of savings programs) used web search only. **Almost every source below was read as a search snippet, not as a full document.** Items the research could not confirm are marked *unverified*. Nothing here was checked against Maryland-specific standards, because no Governor's-office template, no Office of Legislative Audits style manual and no state savings-measurement standard was found. Ask the Governor's staff for their memo template before the rewrite.
- The reading-grade figure is my own Flesch-Kincaid estimate over the prose (code folded sections excluded), not a tool-certified score.

## Rating: 3.3 / 5

Each criterion is scored 1 to 5 (unweighted mean of ten).

| # | Criterion | Score | Evidence from the walkthrough |
|---|---|---|---|
| 1 | Bottom line first | 3 | A "Key findings" block opens the document, and each finding points to its section. It is long (seven findings with figures), is not a standalone page, and has no decision attached. |
| 2 | Plain language | 3 | About 2,900 words of prose at roughly US grade 10.6. A glossary exists. Terms such as MASE and "calibrated range" appear in the findings. |
| 3 | Fit for the Governor and GMI | 2 | The text never mentions the Governor, lists no decisions or actions requested, and names no owner for any next step. |
| 4 | Claims tied to evidence | 4 | Every number is computed from `site_data/`; provenance and reproduction sections exist; 143 checks are cited. Numbers are not yet linked to their metric id in `metrics.json`. |
| 5 | Uncertainty and limits | 5 | States that the published range held 63% against an intended 80%, gives the calibrated range's coverage with an interval, says leads are not savings, and has a Limits section. |
| 6 | Reported versus verified savings | 4 | Keeps reported, supported and assumed figures apart and says payments falling is evidence, not proof. Does not define the baseline, or separate cost avoidance from cash savings, or discuss double counting. |
| 7 | Audit-style structure | 3 | Has scope, methods and limits and an "independent prototype, not an official State product" line. No criteria-condition-cause-effect-recommendation form, no statement on prior audit findings, no invitation for the agency to respond. |
| 8 | Charts and accessibility | 4 | Six figures, each with alt text, a caption that states the finding and a data table; 19 tables (18 captioned); skip link, contents list, `lang` set, and a built-in validator. No independent WCAG 2.2 audit was run, and there is no print stylesheet. |
| 9 | Reproducibility and freshness | 3 | Provenance table with retrieval dates and portal row counts, and a rerun section. No data as-of date in the opening, no file checksums, no change log, and nothing fails when committed figures differ from the data. |
| 10 | Format for executive use | 2 | One 1 MB HTML page with 19 tables; no one-page summary, no print or PDF version. |

**What already works and should be kept:** the evidence discipline (claims are computed, not typed), the honesty about limits, and the reported/supported/assumed split. The gaps are mostly about audience and format, not rigor.

**Freshness check done for this review:** re-executing the notebook from the published tables reproduced all committed figure images and text outputs (random table ids aside). The figures match the Nov 16 snapshot of `site_data`. The Nov 18 extract has not been published there yet.

## Gap analysis

Priority: P1 do before the next briefing, P2 next, P3 later.

| # | Gap | Best practice and source (confidence) | Proposed fix | P |
|---|---|---|---|---|
| G1 | No decisions or actions for the reader | Put purpose, bottom line and the decision first. Federal Plain Language Guidelines, "state the bottom line" ([digital.gov](https://digital.gov/guides/plain-language); guidance; the federal site was reported redirected in 2025, unconfirmed). Decision memo: bottom line, options, recommendation, background ([Duke Nicholas School memo guide](https://sites.nicholas.duke.edu/studio/files/2024/09/Writing-Memos.pdf); moderate) | Add a "For the Governor and GMI" box at the top: the question, what the evidence says, three decisions or asks, who owns each | P1 |
| G2 | No standalone one-pager | One-page summary with detail in an appendix ([Queen's SPS decision note sample](https://www.queensu.ca/sps/sites/spswww/files/uploaded_files/GovTalk/2_2%20BN_Decision.pdf); moderate). No Maryland template found | Write a one-page summary from the Key findings, generated from `metrics.json` so numbers cannot drift; ask the Governor's staff for their memo format | P1 |
| G3 | Reading level too high for the summary | Use plain English, about reading age 9 ([GOV.UK: Writing for GOV.UK](https://www.gov.uk/guidance/content-design/writing-for-gov-uk); guidance, figure from secondary snippets). A US grade-8 target is *unverified*; Maryland standard not found | Rewrite the summary and findings at about grade 8; keep technical terms in the glossary and the sections | P1 |
| G4 | Savings measurement not defined | Separate cost avoidance from cash savings; agree the baseline first ([Suplari](https://suplari.com/blog/cost-avoidance-vs-cost-savings-why-both-matter-for-procurement), [Simfoni](https://simfoni.com/procurement-analytics/procurement-savings-define-measure-and-report-cost-reductions/); vendor blogs, low-moderate). OECD formula: (historical price minus price paid) times quantity ([OECD toolbox](https://search.oecd.org/governance/procurement/toolbox/principlestools/evaluation); moderate, from a 2014 draft). Reported versus verified savings ([GAO-12-919](https://www.gao.gov/products/GAO-12-919), [GAO-17-164](https://www.gao.gov/products/GAO-17-164); snippets only) | Add a short "How savings are counted" section: GMI's baseline and method as reported, what the tracker can and cannot confirm, double counting | P1 |
| G5 | Audit-style framing and fairness | Findings as criteria, condition, cause, effect, recommendation ([GAO Yellow Book 2024, GAO-24-106786](https://www.gao.gov/products/GAO-24-106786); date verified, chapter placement *unverified*). Maryland OLA layout: prior findings, numbered findings, agency response ([OLA reports](https://dls.maryland.gov/pubs/prod/NoPblTabPDF/DGSOS25.pdf); moderate, from front pages) | Add a short scope, independence and "not an audit under GAGAS" statement (the wording is our recommendation, unsourced); list prior audit findings the tracker already carries; offer GMI a response line | P2 |
| G6 | No data as-of date or version up top; no staleness check | State as-of date, version, change log and how to verify ([Analysis Function: Writing about data](https://analysisfunction.civilservice.gov.uk/policy-store/writing-about-data); guidance). Turing Way reproducibility definition ([book.the-turing-way.org](https://book.the-turing-way.org/reproducible-research); verified). Checksums are our recommendation, *unverified* as Turing Way guidance | Print "Data as of", release version and run id in the opening; add SHA-256 for each published input; add the CI step that re-renders and fails on difference (see the Nov 18 freshness note) | P1 |
| G7 | Data reliability not stated as a conclusion | Assess accuracy, completeness and applicability for the purpose, and report the conclusion ([GAO-20-283G, Assessing Data Reliability](https://www.gao.gov/products/GAO-20-283G); official, not opened) | Add one paragraph mapping the 143 checks and portal reconciliation to a reliability statement, and saying what is self-reported by agencies | P2 |
| G8 | Charts: accessibility proof and print | Put the description in visible text and give a data table ([Analysis Function: charts](https://analysisfunction.civilservice.gov.uk/policy-store/data-visualisation-charts), [GOV.UK text descriptions](https://accessibility.blog.gov.uk/2023/04/13/text-descriptions-for-data-visualisations/); guidance). WCAG 2.2 AA target ([W3C](https://www.w3.org/TR/WCAG22/); primary, not fetched) | Run an automated and a manual WCAG 2.2 AA pass; add a print stylesheet and a tagged PDF; keep four or fewer colours per chart where possible | P2 |
| G9 | State accessibility rules not checked | Maryland's Digital Accessibility Policy (Jan 2024) names WCAG 2.1 AA for vendors; a third party lists WCAG 2.0 AA in COMAR, so the version conflicts ([MD DoIT policy](https://doit.maryland.gov/policies/Accessibility/Pages/Maryland-Digital-Accessibility-Policy.aspx); primary for Maryland, from snippets). Federal ADA Title II web rule dates were delayed to 2027 for larger governments per law-firm summaries (secondary, unverified) | Confirm the standard with DoIT, which offers document accessibility help; record the answer in `docs/` | P2 |
| G10 | Numbers not linked to metric ids | One definition per metric (decision D14) | Link each headline number to its entry in `metrics.json`; add a test that the text equals the registry | P3 |
| G11 | Uncertainty guidance could be cited in full | [Analysis Function: Communicating quality, uncertainty and change](https://analysisfunction.civilservice.gov.uk/policy-store/communicating-quality-uncertainty-and-change/), [OSR: presenting uncertainty](https://osr.statisticsauthority.gov.uk/publication/approaches-to-presenting-uncertainty-in-the-statistical-system/pages/2) (guidance, snippets) | The walkthrough already follows this; add the two sources to its references | P3 |

## Suggested order

1. **One PR for the front matter (G1, G2, G3, G4, G6 header):** the Governor and GMI box, the one-page summary, a grade-8 rewrite of the findings, the savings-counting section, and the as-of line. Rendered from `metrics.json` where possible.
2. **A freshness PR (G6 remainder):** deterministic rendering, a CI check that fails when committed figures differ from the data, checksums, and the paused data-refresh PR so the Nov 18 extract is published first.
3. **Format and accessibility (G8, G9):** print stylesheet, tagged PDF, an accessibility pass, and the DoIT answer.
4. **Audit framing and reliability (G5, G7)** once GMI's staff have seen the first version.

## Open questions for the owner

- Does the Governor's office have a memo template or house style?
- Who should be named as owner for each decision requested?
- Should GMI be offered a written response before the walkthrough goes to the Governor's office?

## Sources and confidence

All links above were returned by web search. Pages were not opened in full. The Yellow Book chapter, the 2025 Green Book numbering (GAO-25-107721), the 2023 OECD savings text, the exact US reading-grade target, Maryland plain-language standards and the ADA Title II dates for smaller governments are *unverified*.

## Update, Nov 18, 2026 (night): what the Executive walkthrough tab closes

The dashboard's new **Executive walkthrough** tab (11th tab, right after Overview) is the one-page entry point this review asked for. It closes G1 (three decisions or asks, with owners left for GMI and the Governor's office to name), G2 (a standalone page that prints as a one-page brief, generated from the metric registry so numbers cannot drift), G3 (short plain-language sentences, checked by a test), G4 (reported, supported and assumed amounts kept apart, with the two reported totals shown separately) and the as-of and version line of G6. **Still open:** the owner for each ask; the CI check that fails when committed figures differ from the data, and file checksums (rest of G6); the audit-style framing (G5); the data-reliability statement (G7); the WCAG 2.2 AA pass on the PDF and the DoIT answer (G8, G9); linking each number to its metric id on the notebook (G10). This notebook is now the detailed evidence behind the tab.
