import pytest

from secop_intelligence.modifications import (
    MODIFICATION_FIELDS,
    build_params,
    deduplicate_modifications,
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
    assert params["$limit"] == 5000
    assert "CO1.PCCNTR.1" in params["$where"]


def test_query_rejects_empty_contract_set() -> None:
    with pytest.raises(ValueError, match="at least one"):
        build_params([])
