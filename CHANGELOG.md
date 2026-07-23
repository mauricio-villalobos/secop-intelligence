# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-07-23

### Added

- Complete bounded ingestion for SECOP II electronic contracts.
- Batched ingestion and deterministic curation of contract modifications.
- Privacy allowlists, prohibited-field tests and value-free audit output.
- Explicit quarantine for conflicting logical modification versions.
- Versioned deterministic rules with evidence and human-review guardrails.
- Reconciled calibration and transparent operational attention lanes.
- Typed DuckDB warehouse with referential-integrity validation.
- Read-only Spanish Streamlit interface with filters and case detail.
- Traceable ZIP review packages with CSV, manifest and SHA-256 integrity.
- Deterministic synthetic database for a safe public demonstration.
- Pinned reproducible environment, automated tests and GitHub Actions CI.

### Validated

- 51,662 official contracts ingested without missing or duplicate IDs.
- 523,017 curated modification records.
- 69,794 deterministic findings across 41,363 contracts.
- Interactive filters responding in under three seconds on the accepted PC.

### Security and privacy

- Personal identifiers, banking fields and unnecessary free text are excluded.
- Public deployment uses synthetic records and contains no official case data.
- Findings are review aids, not allegations, risk scores or legal conclusions.

[0.1.0]: https://github.com/mauricio-villalobos/secop-intelligence/releases/tag/v0.1.0
