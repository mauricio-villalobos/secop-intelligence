from __future__ import annotations

from pathlib import Path

import pytest

from secop_intelligence.analytics import (
    AnalyticsDatabaseError,
    contract_detail,
    filter_options,
    lane_counts,
    overview,
    present_detail_findings,
    present_lane_counts,
    present_queue,
    present_rule_counts,
    review_queue,
    rule_counts,
    trusted_process_url,
)
from secop_intelligence.warehouse import build_warehouse


def build_sample(database: Path) -> None:
    contracts = [
        {
            "id_contrato": "CO1",
            "nombre_entidad": "Entidad",
            "departamento": "Valle del Cauca",
            "estado_contrato": "En ejecución",
            "valor_del_contrato": "1000",
            "urlproceso": (
                "https://community.secop.gov.co/Public/Tendering/NoticeDetail/Index"
            ),
            "_content_sha256": "a" * 64,
        },
        {
            "id_contrato": "CO2",
            "nombre_entidad": "Otra entidad",
            "departamento": "Valle del Cauca",
            "estado_contrato": "Terminado",
            "valor_del_contrato": "500",
            "_content_sha256": "b" * 64,
        },
    ]
    findings = [
        {
            "contract_id": "CO1",
            "rule_id": "REVIEW_EXTENSION_RECORDED",
            "ruleset_version": "1.0",
            "category": "human_review",
            "evidence": {"days": 3},
        },
        {
            "contract_id": "CO1",
            "rule_id": "DQ_MODIFICATION_VERSION_CONFLICT",
            "ruleset_version": "1.0",
            "category": "data_quality",
            "evidence": {"version": 2},
        },
    ]
    build_warehouse(database, contracts, [], findings)


def test_overview_and_rule_counts(tmp_path: Path) -> None:
    database = tmp_path / "secop.duckdb"
    build_sample(database)

    assert overview(database) == {
        "contract_count": 2,
        "finding_count": 2,
        "data_quality_count": 1,
        "human_review_count": 1,
        "contracts_with_findings": 1,
    }
    assert len(rule_counts(database)) == 2


def test_filter_options_and_parameterized_queue(tmp_path: Path) -> None:
    database = tmp_path / "secop.duckdb"
    build_sample(database)

    options = filter_options(database)
    queue = review_queue(
        database,
        category="human_review",
        contract_state="En ejecución",
    )

    assert options["categories"] == ["Todos", "data_quality", "human_review"]
    assert options["lanes"] == [
        "Todos",
        "DATA_QUALITY_BLOCKER",
        "EXTENSION_FOLLOW_UP",
    ]
    assert len(queue) == 1
    assert queue[0]["rule_id"] == "REVIEW_EXTENSION_RECORDED"
    assert queue[0]["lane_id"] == "EXTENSION_FOLLOW_UP"

    extension_queue = review_queue(database, lane_id="EXTENSION_FOLLOW_UP")
    assert len(extension_queue) == 1


def test_lane_counts_use_unique_contracts(tmp_path: Path) -> None:
    database = tmp_path / "secop.duckdb"
    build_sample(database)

    assert lane_counts(database) == [
        {
            "lane_id": "DATA_QUALITY_BLOCKER",
            "finding_count": 1,
            "contract_count": 1,
        },
        {
            "lane_id": "EXTENSION_FOLLOW_UP",
            "finding_count": 1,
            "contract_count": 1,
        },
    ]


def test_queue_rejects_invalid_limit(tmp_path: Path) -> None:
    database = tmp_path / "secop.duckdb"
    build_sample(database)

    with pytest.raises(ValueError, match="limit"):
        review_queue(database, limit=0)


def test_contract_detail_is_parameterized_and_traceable(tmp_path: Path) -> None:
    database = tmp_path / "secop.duckdb"
    build_sample(database)

    detail = contract_detail(database, "CO1")

    assert detail is not None
    assert detail["contract"]["contract_id"] == "CO1"
    assert len(detail["findings"]) == 2
    assert detail["modifications"]["modification_count"] == 0
    assert trusted_process_url(detail["contract"]["process_url"]) is not None
    assert contract_detail(database, "missing") is None


def test_process_url_requires_exact_official_https_host() -> None:
    assert (
        trusted_process_url(
            "https://community.secop.gov.co/Public/Tendering/NoticeDetail"
        )
        is not None
    )
    assert trusted_process_url("http://community.secop.gov.co/path") is None
    assert trusted_process_url("https://community.secop.gov.co.evil.test") is None
    assert trusted_process_url("javascript:alert(1)") is None
    assert (
        trusted_process_url(
            "{'url': 'https://community.secop.gov.co/Public/Tendering/NoticeDetail'}"
        )
        is not None
    )


def test_missing_database_has_actionable_error(tmp_path: Path) -> None:
    with pytest.raises(AnalyticsDatabaseError, match="database not found"):
        overview(tmp_path / "missing.duckdb")


def test_presentation_hides_internal_hash_and_labels_rules() -> None:
    queue = present_queue(
        [
            {
                "finding_id": "internal-hash",
                "contract_id": "CO1",
                "entity_name": "Entidad",
                "contract_state": "En ejecución",
                "contract_value": 1000,
                "category": "human_review",
                "rule_id": "REVIEW_EXTENSION_RECORDED",
                "lane_id": "EXTENSION_FOLLOW_UP",
                "ruleset_version": "1.0",
                "evidence": '{"days":3}',
            }
        ]
    )
    counts = present_rule_counts(
        [
            {
                "category": "human_review",
                "rule_id": "REVIEW_EXTENSION_RECORDED",
                "finding_count": 1,
            }
        ]
    )
    lanes = present_lane_counts(
        [
            {
                "lane_id": "EXTENSION_FOLLOW_UP",
                "contract_count": 1,
                "finding_count": 1,
            }
        ]
    )
    detail_findings = present_detail_findings(
        [
            {
                "category": "human_review",
                "lane_id": "EXTENSION_FOLLOW_UP",
                "rule_id": "REVIEW_EXTENSION_RECORDED",
                "ruleset_version": "1.0",
                "evidence": '{"days":3}',
            }
        ]
    )

    assert "finding_id" not in queue[0]
    assert queue[0]["Regla"] == "Prórroga registrada"
    assert queue[0]["Carril de atención"] == "Seguimiento de prórroga"
    assert queue[0]["Versión de reglas"] == "1.0"
    assert counts[0]["Categoría"] == "Revisión humana"
    assert lanes[0]["Carril de atención"] == "Seguimiento de prórroga"
    assert lanes[0]["Contratos"] == 1
    assert detail_findings[0]["Versión de reglas"] == "1.0"
