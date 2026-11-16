-- mart.d_audit_findings (dashboard Opportunities tab: audit and recoupment lifecycle, improvement 4 of the v3.1 strategy)
-- Grain: one row per finding. Two sources, kept apart by source_type:
--   reference/audit_findings.csv: findings with lifecycle fields (amount identified and recouped, recoupment status, waiver and
--     who decided it, legal-opinion request and status), seeded only from public documents; a blank field is unknown, never 0;
--     confirmation says whether an audit document confirms the row or it rests on a press or agency report.
--   ref.ola_findings: the Office of Legislative Audits' latest report per agency (findings, repeat findings); OLA reports do not
--     publish recoupment status, so those fields stay blank.
-- Amounts are what the source reports, not savings and not money owed.
CREATE OR REPLACE TABLE mart.d_audit_findings AS
SELECT finding_id, agency_code, agency, program, source_type, document, nullif(document_date, '') AS document_date, period, finding,
       try_cast(nullif(amount_identified, '') AS DOUBLE) AS amount_identified, try_cast(nullif(amount_recouped, '') AS DOUBLE) AS amount_recouped,
       nullif(recoupment_status, '') AS recoupment_status, nullif(waiver, '') AS waiver, nullif(waiver_decided_by, '') AS waiver_decided_by,
       nullif(legal_opinion, '') AS legal_opinion, nullif(legal_opinion_status, '') AS legal_opinion_status,
       nullif(fund_source, '') AS fund_source, confirmation, as_of, source_url, nullif(note, '') AS note
FROM ref.audit_findings
UNION ALL
SELECT 'OLA-' || agency_code, agency_code, agency_name, audit_unit, 'OLA audit report', 'OLA audit, ' || audit_unit, report_date, NULL,
       findings || ' findings, ' || repeat_findings || ' repeated from the prior audit', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
       'Confirmed in audit document', report_date, report_url, nullif(note, '')
FROM ref.ola_findings
ORDER BY source_type DESC, amount_identified DESC NULLS LAST;
