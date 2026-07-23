# Modifications Source Data Contract

version: 1.1
source_dataset: `u8cx-r425`
publisher: Agencia Nacional de Contratación Pública - Colombia Compra Eficiente

## Purpose

Provide versioned modification facts linked exclusively to the current bounded
contract cohort.

## Grain and logical key

- Source grain: one reported version of a contract modification.
- Parent key: `id_contrato`.
- Logical key: `identificador_modificacion` plus `numero_version`.
- Exact duplicate logical versions are collapsed and counted.
- Conflicting rows for the same logical key are excluded from the curated
  output and placed in a value-free quarantine report.

## Allowlisted fields

- `id_contrato`;
- `identificador_modificacion`;
- `estado_modificacion`;
- `fecha_de_carga`;
- `fecha_de_aprobacion`;
- `fecha_version`;
- `numero_version`;
- `dias_extendidos`;
- `valor_modificacion`.

Free-text descriptions and modification purposes are excluded from this
milestone. They are not required to establish reliable version linkage.

## Referential integrity

Every modification must reference a contract in the bounded input file.
Orphans stop the run and are reported only as a count.

## Bounded batch retrieval

Contract identifiers are sorted, deduplicated and divided into bounded groups
before they enter a SoQL `IN` clause. Each group is retrieved in stable ordered
pages until the source returns a short terminal page.

The manifest records input contracts, configured and completed batches, page
count, source row count and a deterministic collection hash. Output files are
published by replacement only after every batch completes. This is exhaustion
evidence for the bounded cohort, not a claim that the remote mutable dataset
provides transactional snapshot isolation.

## Conflict quarantine

If one logical key has multiple non-identical representations, the run returns
`REVIEW_REQUIRED` with exit code 2 after safely writing unambiguous records.
The quarantine report contains only:

- contract and modification identifiers;
- version;
- content hashes;
- names of differing fields.

It does not choose, merge or expose the conflicting values.

## Value semantics

`valor_modificacion` is retained as a source fact but MUST NOT be presented as
the incremental addition or used in attention rules until its semantic meaning
has been validated against source documentation and representative records.
