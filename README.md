# SECOP Intelligence

Privacy-minimized ingestion and decision-support tooling for Colombia's public
procurement data.

This portfolio project turns official SECOP II records into a traceable human
review queue. It does **not** detect corruption, make legal claims, or automate
procurement decisions.

## Current milestone

Milestone 1 establishes the governed data boundary:

- an explicit allowlist of non-sensitive contract fields;
- bounded queries to the official Socrata API;
- deterministic record validation and content hashing;
- JSON Lines output plus an ingestion manifest;
- tests that prevent accidental collection of prohibited personal fields.

Dashboarding and AI-assisted explanations remain gated on data-quality
acceptance.

## Source

- Dataset: SECOP II - Contratos Electrónicos
- Publisher: Agencia Nacional de Contratación Pública - Colombia Compra Eficiente
- Dataset ID: `jbjy-vk9h`
- Official page: <https://www.datos.gov.co/Estad-sticas-Nacionales/SECOP-II-Contratos-Electr-nicos/jbjy-vk9h>

## Local setup

Install [`uv`](https://docs.astral.sh/uv/) and run:

```bash
uv sync --locked --all-groups
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

## Complete bounded ingestion

The command below retrieves the complete six-month departmental slice while
enforcing a 60,000-record safety ceiling. Generated data is excluded from Git:

```bash
uv run secop-ingest \
  --department "Valle del Cauca" \
  --signed-from 2026-01-01 \
  --signed-before 2026-07-01 \
  --max-records 60000 \
  --page-size 1000
```

Output:

```text
data/raw/contracts.jsonl
data/raw/manifest.json
```

Only fields declared in `CONTRACT_FIELDS` are requested and persisted. The
manifest proves count stability, completeness, uniqueness and a deterministic
collection hash.

Audit free text before using or publishing any generated sample:

```bash
uv run secop-audit
```

The audit reports only content hashes, field names and pattern categories. It
never prints the matching source text.

Fetch modifications linked only to the bounded local contract sample:

```bash
uv run secop-ingest-modifications \
  --batch-size 150 \
  --page-size 1000
```

The modification layer excludes free-text descriptions in this milestone. It
retrieves the complete contract cohort in bounded ID batches and stable ordered
pages. It removes only byte-equivalent logical duplicates. Conflicting
representations of one modification/version are excluded from curated output
and recorded in a value-free quarantine report with `REVIEW_REQUIRED`.

Build the first deterministic attention queue using an explicit evaluation
date:

```bash
uv run secop-build-attention --as-of 2026-07-23
```

Profile accepted rule prevalence and concentration without changing findings:

```bash
uv run secop-calibrate-rules \
  --output data/curated/rule-calibration.json
```

The read-only interface groups existing findings into transparent operational
lanes for data quality, extension follow-up, recent closure, stale status and
upcoming closure. Lanes never replace rule IDs or evidence and are not scores.

Rules emit evidence-bearing data-quality or human-review findings. They do not
produce a corruption/fraud score. See
[`docs/attention-rules.md`](docs/attention-rules.md).

Materialize the accepted artifacts as typed local analytical tables:

```bash
uv run secop-build-warehouse
```

The command creates `data/warehouse/secop.duckdb` transactionally and rejects
orphan references. See [`docs/warehouse.md`](docs/warehouse.md).

Launch the read-only analytical interface:

```bash
uv run streamlit run app.py
```

The interface exposes transparent metrics, rule counts and an evidence-bearing
review queue. See [`docs/interface.md`](docs/interface.md).

## Privacy boundary

The project intentionally excludes:

- personal identification numbers;
- representative, supervisor and payment-authorizer names;
- physical addresses;
- bank and account information;
- gender and nationality.

Free-text fields may still contain incidental personal data and must be scanned
before any sample is published.

## License

MIT. See [LICENSE](LICENSE).
