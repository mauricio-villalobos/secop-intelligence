from __future__ import annotations

import hashlib
import os
import uuid
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from secop_intelligence.warehouse import build_warehouse

FULL_DATABASE = Path("data/warehouse/secop.duckdb")
DEMO_DATABASE = Path(".cache/secop-demo.duckdb")
DEMO_CONTRACT_COUNT = 36


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _contract(index: int) -> dict[str, Any]:
    starts_at = date(2026, 1, 1) + timedelta(days=index * 3)
    ends_at = starts_at + timedelta(days=90 + (index % 5) * 30)
    states = ("En ejecución", "Modificado", "Cerrado")
    return {
        "id_contrato": f"DEMO-{index:04d}",
        "nombre_entidad": f"Entidad demostrativa {((index - 1) % 12) + 1:02d}",
        "departamento": "Valle del Cauca",
        "ciudad": ("Cali", "Palmira", "Buenaventura")[index % 3],
        "sector": ("Salud", "Educación", "Transporte")[index % 3],
        "estado_contrato": states[index % len(states)],
        "fecha_de_firma": (starts_at - timedelta(days=10)).isoformat(),
        "fecha_de_inicio_del_contrato": starts_at.isoformat(),
        "fecha_de_fin_del_contrato": ends_at.isoformat(),
        "valor_del_contrato": str(50_000_000 + index * 7_500_000),
        "valor_facturado": str(20_000_000 + index * 2_000_000),
        "valor_pagado": str(18_000_000 + index * 1_750_000),
        "dias_adicionados": 15 if index % 4 == 0 else 0,
        "ultima_actualizacion": "2026-07-23T00:00:00+00:00",
        "urlproceso": None,
        "_content_sha256": _digest(f"contract-{index}"),
    }


def _modifications(index: int) -> list[dict[str, Any]]:
    if index % 4 != 0:
        return []
    return [
        {
            "id_contrato": f"DEMO-{index:04d}",
            "identificador_modificacion": f"DEMO-MOD-{index:04d}",
            "numero_version": 1,
            "estado_modificacion": "Aprobada",
            "fecha_de_carga": "2026-05-01T00:00:00+00:00",
            "fecha_de_aprobacion": "2026-05-02T00:00:00+00:00",
            "fecha_version": "2026-05-02T00:00:00+00:00",
            "dias_extendidos": 15,
            "valor_modificacion": "0",
            "_content_sha256": _digest(f"modification-{index}"),
        }
    ]


def _finding(
    index: int,
    rule_id: str,
    category: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "contract_id": f"DEMO-{index:04d}",
        "rule_id": rule_id,
        "ruleset_version": "1.0",
        "category": category,
        "evidence": evidence,
    }


def _findings(
    index: int,
    contract: dict[str, Any],
) -> list[dict[str, Any]]:
    as_of = date(2026, 7, 23)
    end_date = date.fromisoformat(contract["fecha_de_fin_del_contrato"])
    state = str(contract["estado_contrato"])
    records: list[dict[str, Any]] = []
    if end_date < as_of and state in {"En ejecución", "Modificado"}:
        records.append(
            _finding(
                index,
                "REVIEW_ACTIVE_AFTER_END_DATE",
                "human_review",
                {
                    "as_of": as_of.isoformat(),
                    "end_date": end_date.isoformat(),
                    "state": state.lower(),
                },
            )
        )
    if index % 4 == 0:
        records.append(
            _finding(
                index,
                "REVIEW_EXTENSION_RECORDED",
                "human_review",
                {"days_extended": 15, "modification_count": 1},
            )
        )
    if index % 12 == 0:
        records.append(
            _finding(
                index,
                "DQ_MODIFICATION_VERSION_CONFLICT",
                "data_quality",
                {
                    "differing_fields": ["dias_extendidos"],
                    "identificador_modificacion": f"DEMO-MOD-{index:04d}",
                },
            )
        )
    if as_of <= end_date <= as_of + timedelta(days=30):
        records.append(
            _finding(
                index,
                "REVIEW_ENDING_WITHIN_30_DAYS",
                "human_review",
                {
                    "as_of": as_of.isoformat(),
                    "days_remaining": (end_date - as_of).days,
                    "end_date": end_date.isoformat(),
                },
            )
        )
    return records


def build_demo_database(database: Path) -> dict[str, Any]:
    contracts = [_contract(index) for index in range(1, DEMO_CONTRACT_COUNT + 1)]
    modifications = [
        record
        for index in range(1, DEMO_CONTRACT_COUNT + 1)
        for record in _modifications(index)
    ]
    findings = [
        record
        for index, contract in enumerate(contracts, start=1)
        for record in _findings(index, contract)
    ]
    return build_warehouse(database, contracts, modifications, findings)


def ensure_demo_database(database: Path = DEMO_DATABASE) -> Path:
    if database.is_file():
        return database
    database.parent.mkdir(parents=True, exist_ok=True)
    temporary = database.with_name(
        f".{database.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    )
    try:
        build_demo_database(temporary)
        os.replace(temporary, database)
    finally:
        temporary.unlink(missing_ok=True)
    return database


def resolve_database() -> tuple[Path, bool]:
    if os.getenv("SECOP_DEMO_MODE") == "1":
        return ensure_demo_database(), True
    configured = os.getenv("SECOP_DATABASE_PATH")
    if configured:
        return Path(configured), False
    if FULL_DATABASE.is_file():
        return FULL_DATABASE, False
    return ensure_demo_database(), True
