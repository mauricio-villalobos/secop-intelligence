from datetime import date

import pytest

from secop_intelligence.contracts import (
    CONTRACT_FIELDS,
    PROHIBITED_FIELDS,
    ContractQuery,
    ContractValidationError,
    duplicate_contract_ids,
    normalize_record,
)


def valid_record() -> dict[str, object]:
    return {
        "id_contrato": "CO1.PCCNTR.1",
        "departamento": "Valle del Cauca",
        "fecha_de_firma": "2026-01-15T00:00:00",
        "valor_del_contrato": "1000000",
        "urlproceso": {"url": "https://example.invalid/contract/1"},
    }


def test_allowlist_does_not_include_prohibited_fields() -> None:
    assert set(CONTRACT_FIELDS).isdisjoint(PROHIBITED_FIELDS)


def test_query_is_bounded_and_selects_only_allowlisted_fields() -> None:
    query = ContractQuery(
        department="Valle del Cauca",
        signed_from=date(2026, 1, 1),
        signed_before=date(2026, 7, 1),
        limit=100,
    )

    params = query.params()

    assert params["$select"] == ",".join(CONTRACT_FIELDS)
    assert params["$limit"] == 100
    assert "fecha_de_firma >=" in str(params["$where"])
    assert "fecha_de_firma <" in str(params["$where"])


def test_query_rejects_unbounded_limit() -> None:
    with pytest.raises(ValueError, match="between 1 and 1000"):
        ContractQuery(
            department="Valle del Cauca",
            signed_from=date(2026, 1, 1),
            signed_before=date(2026, 7, 1),
            limit=1001,
        )


def test_normalize_rejects_prohibited_fields() -> None:
    record = valid_record()
    record["documento_proveedor"] = "not-allowed"

    with pytest.raises(ContractValidationError, match="prohibited fields"):
        normalize_record(record)


def test_normalize_rejects_unexpected_fields() -> None:
    record = valid_record()
    record["unknown"] = "not-allowed"

    with pytest.raises(ContractValidationError, match="unexpected fields"):
        normalize_record(record)


def test_normalize_adds_stable_content_hash() -> None:
    first = normalize_record(valid_record())
    second = normalize_record(valid_record())

    assert first["_content_sha256"] == second["_content_sha256"]
    assert len(str(first["_content_sha256"])) == 64


def test_duplicate_contract_ids() -> None:
    records = [
        {"id_contrato": "A"},
        {"id_contrato": "B"},
        {"id_contrato": "A"},
    ]

    assert duplicate_contract_ids(records) == {"A"}
