# Contracts Source Data Contract

version: 1.0
source_dataset: `jbjy-vk9h`
publisher: Agencia Nacional de Contratación Pública - Colombia Compra Eficiente

## Purpose

Provide the minimum SECOP II contract attributes required to build a traceable
human-review queue. This contract does not authorize collection of every field
available in the source.

## Grain and key

- Grain: one current contract record.
- Primary key: `id_contrato`.
- The ingestion rejects duplicate primary keys within a bounded run.
- A canonical SHA-256 hash is added to each normalized record to support
  idempotent change detection.

## Required source fields

| Field | Expected type | Rule |
|---|---|---|
| `id_contrato` | text | non-null |
| `departamento` | text | non-null |
| `fecha_de_firma` | ISO-8601 timestamp text | non-null |
| `valor_del_contrato` | numeric text | non-null |
| `urlproceso` | URL object | non-null |

Optional allowlisted fields are declared in
`secop_intelligence.contracts.CONTRACT_FIELDS`. Any unexpected field causes the
record to be rejected rather than silently persisted.

## Explicit exclusions

The ingestion must never request or persist:

- personal or supplier identification numbers;
- names of representatives, supervisors or payment authorizers;
- addresses;
- bank or account details;
- gender or nationality.

The prohibited field set is enforced in code and tests.

## Free text

`descripcion_del_proceso` is retained because it is necessary for analytical
classification and later evidence-grounded explanations. Before a generated
sample can be published, it must pass `secop-audit`.

The audit reports only:

- record content hash;
- field name;
- pattern category.

It does not reproduce matching source text.

## Incremental behavior

`ultima_actualizacion` cannot be the sole cursor because it was absent in 93.2%
of the initial 1,000-record profile.

The planned production-shaped strategy is:

1. request an overlapping signature-date window;
2. normalize and validate each record;
3. upsert by `id_contrato`;
4. compare the canonical content hash;
5. retain run manifests and ingestion timestamps.

## Source change policy

The run fails closed when:

- a required field is absent;
- an unexpected field is returned;
- a prohibited field is returned;
- the response is not a JSON array;
- duplicate contract IDs occur in one bounded result.

Schema changes require a reviewed contract version update and new test evidence.
