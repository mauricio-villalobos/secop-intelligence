# Public deployment

The public portfolio deployment uses Streamlit Community Cloud and the
synthetic demonstration database only.

## Community Cloud settings

- Repository: `mauricio-villalobos/secop-intelligence`
- Branch: `main`
- Entrypoint: `app.py`
- Python: `3.12`
- Secrets: none

The repository includes one supported dependency source, `uv.lock`, alongside
`pyproject.toml`. No operating-system packages are required.

## Data boundary

Generated data is excluded from Git by the `data/` rule. The public deployment
therefore has no accepted official warehouse and `resolve_database()` creates
the deterministic synthetic database under `.cache/`.

Do not configure `SECOP_DATABASE_PATH` or upload an official DuckDB file to the
public deployment. `SECOP_DEMO_MODE=1` remains available for explicit local
acceptance testing, but the absence of the official warehouse is sufficient to
select the safe public fallback.

Public acceptance must verify:

1. the blue synthetic-data notice is visible;
2. all contract IDs begin with `DEMO-`;
3. all entities begin with `Entidad demostrativa`;
4. no official process URL is displayed;
5. the review package contains synthetic records only.
