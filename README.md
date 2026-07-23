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

## Bounded ingestion

The command below requests at most 100 contracts. Generated data is excluded
from Git:

```bash
uv run secop-ingest \
  --department "Valle del Cauca" \
  --signed-from 2026-01-01 \
  --signed-before 2026-07-01 \
  --limit 100
```

Output:

```text
data/raw/contracts.jsonl
data/raw/manifest.json
```

Only fields declared in `CONTRACT_FIELDS` are requested and persisted.

Audit free text before using or publishing any generated sample:

```bash
uv run secop-audit
```

The audit reports only content hashes, field names and pattern categories. It
never prints the matching source text.

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
