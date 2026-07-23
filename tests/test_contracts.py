from datetime import date

import httpx
import pytest

from secop_intelligence.contracts import (
    CONTRACT_FIELDS,
    PROHIBITED_FIELDS,
    ContractCompletenessError,
    ContractQuery,
    ContractValidationError,
    duplicate_contract_ids,
    fetch_complete_contracts,
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
    assert params["$offset"] == 0
    assert "fecha_de_firma >=" in str(params["$where"])
    assert "fecha_de_firma <" in str(params["$where"])


def test_query_rejects_unbounded_limit() -> None:
    with pytest.raises(ValueError, match="between 1 and 100000"):
        ContractQuery(
            department="Valle del Cauca",
            signed_from=date(2026, 1, 1),
            signed_before=date(2026, 7, 1),
            limit=100_001,
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


def test_complete_ingestion_paginates_and_proves_counts() -> None:
    records = [
        {
            **valid_record(),
            "id_contrato": f"CO1.PCCNTR.{index}",
        }
        for index in range(3)
    ]
    count_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal count_calls
        if request.url.params["$select"] == "count(*) AS record_count":
            count_calls += 1
            return httpx.Response(200, json=[{"record_count": "3"}])
        offset = int(request.url.params["$offset"])
        limit = int(request.url.params["$limit"])
        return httpx.Response(200, json=records[offset : offset + limit])

    query = ContractQuery(
        department="Valle del Cauca",
        signed_from=date(2026, 1, 1),
        signed_before=date(2026, 7, 1),
        limit=10,
        page_size=2,
    )
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result, evidence = fetch_complete_contracts(query, client=client)

    assert [item["id_contrato"] for item in result] == [
        "CO1.PCCNTR.0",
        "CO1.PCCNTR.1",
        "CO1.PCCNTR.2",
    ]
    assert evidence["record_count"] == 3
    assert evidence["unique_contract_ids"] == 3
    assert evidence["page_count"] == 2
    assert count_calls == 2


def test_complete_ingestion_rejects_source_change() -> None:
    count_values = iter(("1", "2"))

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params["$select"] == "count(*) AS record_count":
            return httpx.Response(
                200,
                json=[{"record_count": next(count_values)}],
            )
        return httpx.Response(200, json=[valid_record()])

    query = ContractQuery(
        department="Valle del Cauca",
        signed_from=date(2026, 1, 1),
        signed_before=date(2026, 7, 1),
    )
    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(ContractCompletenessError, match="changed"),
    ):
        fetch_complete_contracts(query, client=client)


def test_complete_ingestion_rejects_count_above_safety_limit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"record_count": "11"}])

    query = ContractQuery(
        department="Valle del Cauca",
        signed_from=date(2026, 1, 1),
        signed_before=date(2026, 7, 1),
        limit=10,
    )
    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(ContractCompletenessError, match="exceeds"),
    ):
        fetch_complete_contracts(query, client=client)
