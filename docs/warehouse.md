# Local analytical warehouse

The warehouse materializes accepted, privacy-minimized artifacts in a local
DuckDB file. It is an analytical projection, not a new source of truth.

## Contract

- Contract identifiers must be unique.
- Every modification and finding must reference a loaded contract.
- Every finding receives a deterministic content-derived identifier, so
  repeated rules with distinct evidence remain independently traceable.
- Dates and monetary values are converted to typed columns.
- Publication occurs in one transaction.
- Generated databases remain under the ignored `data/` tree.

The views expose transparent finding counts. They do not calculate a composite
risk score or make allegations.
