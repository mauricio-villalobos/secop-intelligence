# Read-only analytical interface

The Streamlit application exposes only accepted DuckDB tables and views.

```bash
uv run streamlit run app.py
```

The application:

- opens the local database in read-only mode;
- displays transparent counts rather than a composite score;
- supports parameterized lane, category, rule and contract-state filters;
- derives transparent operational lanes without changing source findings;
- preserves the rule version and evidence for human review;
- does not fetch source data or write analytical records.
- binds only to localhost and disables Streamlit usage telemetry;
- hides internal finding hashes from the decision-support table while retaining
  technical rule identifiers for traceability.

The interface is a decision-support surface, not a fraud detector or an
automated procurement decision system.

## Attention lanes

Lanes are deterministic presentation labels:

- data-quality findings become `DATA_QUALITY_BLOCKER`;
- extension findings and expired contracts with extension evidence become
  `EXTENSION_FOLLOW_UP`;
- expired contracts without extension evidence are separated into recent
  closure review (up to 30 days) and stale-status review (more than 30 days);
- contracts ending within 30 days become `UPCOMING_CLOSURE`.

They are not severity scores, legal conclusions or automated decisions. The
original rule ID, ruleset version and evidence remain available.
