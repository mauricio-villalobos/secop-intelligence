# Modifications Source Data Contract

version: 1.0
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
