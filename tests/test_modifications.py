import httpx
import pytest

from secop_intelligence.modifications import (
    MODIFICATION_FIELDS,
    build_params,
    deduplicate_modifications,
    fetch_modifications_batched,
    get_page_with_retry,
    normalize_modification,
    orphan_contract_ids,
)


def valid_modification() -> dict[str, object]:
    return {
        "id_contrato": "CO1.PCCNTR.1",
        "identificador_modificacion": "CO1.CTRMOD.1",
        "numero_version": "2",
        "estado_modificacion": "Aprobado",
    }


def test_normalization_adds_hash_and_only_allowlisted_fields() -> None:
    record = normalize_modification(valid_modification())

    assert set(record) == {*MODIFICATION_FIELDS, "_content_sha256"}
    assert len(str(record["_content_sha256"])) == 64


def test_exact_duplicates_are_removed() -> None:
    first = normalize_modification(valid_modification())
    second = normalize_modification(valid_modification())

    records, duplicate_count, conflicts = deduplicate_modifications([first, second])

    assert len(records) == 1
    assert duplicate_count == 1
    assert conflicts == []


def test_conflicting_duplicate_is_quarantined_without_values() -> None:
    first = normalize_modification(valid_modification())
    changed = valid_modification()
    changed["estado_modificacion"] = "Publicado"
    second = normalize_modification(changed)

    records, duplicate_count, conflicts = deduplicate_modifications([first, second])

    assert records == []
    assert duplicate_count == 0
    assert len(conflicts) == 1
    assert conflicts[0]["differing_fields"] == ["estado_modificacion"]
    assert "Aprobado" not in str(conflicts)
    assert "Publicado" not in str(conflicts)


def test_orphan_contract_ids_are_reported() -> None:
    modifications = [
        {"id_contrato": "A"},
        {"id_contrato": "B"},
    ]

    assert orphan_contract_ids(modifications, {"A"}) == {"B"}


def test_query_is_bounded_and_allowlisted() -> None:
    params = build_params(["CO1.PCCNTR.1", "CO1.PCCNTR.2"])

    assert params["$select"] == ",".join(MODIFICATION_FIELDS)
    assert params["$limit"] == 1000
    assert params["$offset"] == 0
    assert "CO1.PCCNTR.1" in params["$where"]


def test_query_rejects_empty_contract_set() -> None:
    with pytest.raises(ValueError, match="at least one"):
        build_params([])


def test_batched_retrieval_exhausts_every_ordered_batch() -> None:
    contract_ids = [
        "CO1.PCCNTR.1",
        "CO1.PCCNTR.2",
        "CO1.PCCNTR.3",
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        where = request.url.params["$where"]
        offset = int(request.url.params["$offset"])
        if "CO1.PCCNTR.3" in where:
            payload = (
                [{**valid_modification(), "id_contrato": "CO1.PCCNTR.3"}]
                if offset == 0
                else []
            )
        else:
            payload = (
                [
                    {**valid_modification(), "id_contrato": "CO1.PCCNTR.1"},
                    {**valid_modification(), "id_contrato": "CO1.PCCNTR.2"},
                ]
                if offset == 0
                else []
            )
        return httpx.Response(200, json=payload)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        records, evidence = fetch_modifications_batched(
            contract_ids,
            batch_size=2,
            page_size=2,
            client=client,
        )

    assert len(records) == 3
    assert evidence["batch_count"] == 2
    assert evidence["completed_batches"] == 2
    assert evidence["page_count"] == 3
    assert evidence["source_record_count"] == 3


@pytest.mark.parametrize(
    ("batch_size", "page_size", "message"),
    [
        (0, 1000, "batch_size"),
        (201, 1000, "batch_size"),
        (1, 0, "page_size"),
        (1, 1001, "page_size"),
    ],
)
def test_batched_retrieval_rejects_unsafe_bounds(
    batch_size: int,
    page_size: int,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        fetch_modifications_batched(
            ["CO1.PCCNTR.1"],
            batch_size=batch_size,
            page_size=page_size,
        )


def test_retry_recovers_from_rate_limit() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json=[valid_modification()])

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        payload = get_page_with_retry(client, {"$select": "test"})

    assert len(payload) == 1
    assert calls == 2
