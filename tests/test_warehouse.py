from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

from secop_intelligence.warehouse import (
    WarehouseValidationError,
    build_warehouse,
)


def contract(contract_id: str = "CO1") -> dict[str, object]:
    return {
        "id_contrato": contract_id,
        "nombre_entidad": "Entidad",
        "departamento": "Valle del Cauca",
        "estado_contrato": "En ejecución",
        "fecha_de_firma": "2026-01-02T00:00:00",
        "fecha_de_inicio_del_contrato": "2026-01-03T00:00:00",
        "fecha_de_fin_del_contrato": "2026-06-30T00:00:00",
        "valor_del_contrato": "1250.50",
        "valor_pagado": "500",
        "dias_adicionados": "5",
        "urlproceso": "https://example.invalid",
        "_content_sha256": "a" * 64,
    }


def modification(contract_id: str = "CO1") -> dict[str, object]:
    return {
        "id_contrato": contract_id,
        "identificador_modificacion": "M1",
        "numero_version": "1",
        "dias_extendidos": "3",
        "valor_modificacion": "100.25",
        "_content_sha256": "b" * 64,
    }


def finding(contract_id: str = "CO1") -> dict[str, object]:
    return {
        "contract_id": contract_id,
        "rule_id": "REVIEW_EXTENSION_RECORDED",
        "ruleset_version": "1.0",
        "category": "human_review",
        "evidence": {"days": 5},
    }


def test_builds_typed_warehouse_and_views(tmp_path: Path) -> None:
    database = tmp_path / "secop.duckdb"
    manifest = build_warehouse(
        database,
        [contract()],
        [modification()],
        [finding()],
    )

    assert manifest["result"] == "PASS"
    with duckdb.connect(str(database), read_only=True) as connection:
        row = connection.execute(
            "SELECT contract_value, finding_count, human_review_count "
            "FROM v_contract_attention_summary"
        ).fetchone()
        rules = connection.execute(
            "SELECT rule_id, finding_count FROM v_rule_counts"
        ).fetchall()
    assert row == (Decimal("1250.50"), 1, 1)
    assert rules == [("REVIEW_EXTENSION_RECORDED", 1)]


@pytest.mark.parametrize("record_type", ["modification", "finding"])
def test_rejects_orphan_references(tmp_path: Path, record_type: str) -> None:
    modifications = [modification("MISSING")] if record_type == "modification" else []
    findings = [finding("MISSING")] if record_type == "finding" else []

    with pytest.raises(WarehouseValidationError, match="orphan"):
        build_warehouse(
            tmp_path / "secop.duckdb",
            [contract()],
            modifications,
            findings,
        )


def test_rejects_duplicate_contract_ids(tmp_path: Path) -> None:
    with pytest.raises(WarehouseValidationError, match="duplicate"):
        build_warehouse(
            tmp_path / "secop.duckdb",
            [contract(), contract()],
            [],
            [],
        )


def test_preserves_multiple_findings_for_one_contract_and_rule(
    tmp_path: Path,
) -> None:
    first = finding()
    second = finding()
    second["evidence"] = {"days": 9}
    database = tmp_path / "secop.duckdb"

    build_warehouse(database, [contract()], [], [first, second])

    with duckdb.connect(str(database), read_only=True) as connection:
        count = connection.execute("SELECT COUNT(*) FROM attention_findings").fetchone()
    assert count == (2,)


def test_accepts_empty_optional_collections(tmp_path: Path) -> None:
    database = tmp_path / "secop.duckdb"

    manifest = build_warehouse(database, [contract()], [], [])

    assert manifest["modification_count"] == 0
    assert manifest["finding_count"] == 0
    with duckdb.connect(str(database), read_only=True) as connection:
        counts = connection.execute(
            "SELECT "
            "(SELECT COUNT(*) FROM modifications), "
            "(SELECT COUNT(*) FROM attention_findings)"
        ).fetchone()
    assert counts == (0, 0)
