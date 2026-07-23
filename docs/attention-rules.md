# Deterministic Attention Rules

version: 1.0
ruleset_version: 1.0

## Principle

Rules create evidence-bearing review tasks. They do not estimate corruption,
fraud, illegality or culpability. No composite risk score is produced.

Every run requires an explicit `as_of` date so results are reproducible.

## Rules

| Rule | Category | Condition | Intended action |
|---|---|---|---|
| `DQ_END_BEFORE_START` | data quality | contract end date precedes start date | verify source dates |
| `DQ_PAID_EXCEEDS_CONTRACT_VALUE` | data quality | reported paid value exceeds contract value | verify value semantics/source |
| `DQ_MODIFICATION_VERSION_CONFLICT` | data quality | one modification/version has multiple representations | keep quarantined; request source review |
| `REVIEW_ACTIVE_AFTER_END_DATE` | human review | state is `En ejecución` or `Modificado`, but end date precedes `as_of` | verify whether status is stale or contract was extended |
| `REVIEW_ENDING_WITHIN_30_DAYS` | human review | active contract ends from `as_of` through the next 30 days | review upcoming closure or extension |
| `REVIEW_EXTENSION_RECORDED` | human review | contract or curated modification reports positive added/extended days | review extension evidence |

## Guardrails

- Conflicting modification versions never feed numeric rules.
- Missing optional values do not create findings.
- Invalid dates or decimals stop processing rather than being coerced.
- Source values are evidence, not conclusions.
- Rule definitions and versions must be published with every result.
- New rules require tests and a documented human action.
- Calibration reports are descriptive only and cannot silently change a rule.
