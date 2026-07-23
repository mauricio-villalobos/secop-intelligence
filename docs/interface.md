# Read-only analytical interface

The Streamlit application exposes only accepted DuckDB tables and views.

```bash
uv run streamlit run app.py
```

The application:

- opens the local database in read-only mode;
- displays transparent counts rather than a composite score;
- supports parameterized category, rule and contract-state filters;
- preserves the rule version and evidence for human review;
- does not fetch source data or write analytical records.
- binds only to localhost and disables Streamlit usage telemetry;
- hides internal finding hashes from the decision-support table while retaining
  technical rule identifiers for traceability.

The interface is a decision-support surface, not a fraud detector or an
automated procurement decision system.
