from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import duckdb

SCHEMA_VERSION = 1


class WarehouseValidationError(ValueError):
    """Raised before publishing an analytically unsafe warehouse."""


def _text(value: Any) -> str | None:
    return None if value in (None, "") else str(value)


def _timestamp(value: Any, field: str) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as error:
        raise WarehouseValidationError(f"invalid timestamp in {field}") from error


def _decimal(value: Any, field: str) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation as error:
        raise WarehouseValidationError(f"invalid decimal in {field}") from error


def _integer(value: Any, field: str) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(Decimal(str(value)))
    except (InvalidOperation, ValueError) as error:
        raise WarehouseValidationError(f"invalid integer in {field}") from error


def _validate_references(
    contracts: Sequence[Mapping[str, Any]],
    modifications: Sequence[Mapping[str, Any]],
    findings: Sequence[Mapping[str, Any]],
) -> None:
    contract_ids = [str(item["id_contrato"]) for item in contracts]
    if len(contract_ids) != len(set(contract_ids)):
        raise WarehouseValidationError("duplicate contract IDs")

    known = set(contract_ids)
    if any(str(item["id_contrato"]) not in known for item in modifications):
        raise WarehouseValidationError("orphan modifications")
    if any(str(item["contract_id"]) not in known for item in findings):
        raise WarehouseValidationError("orphan attention findings")


def _create_schema(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        """
        DROP VIEW IF EXISTS v_contract_attention_summary;
        DROP VIEW IF EXISTS v_rule_counts;
        DROP TABLE IF EXISTS attention_findings;
        DROP TABLE IF EXISTS modifications;
        DROP TABLE IF EXISTS contracts;

        CREATE TABLE contracts (
            contract_id VARCHAR PRIMARY KEY,
            entity_name VARCHAR,
            department VARCHAR,
            city VARCHAR,
            sector VARCHAR,
            contract_state VARCHAR,
            signed_at TIMESTAMP,
            starts_at TIMESTAMP,
            ends_at TIMESTAMP,
            contract_value DECIMAL(38, 2),
            invoiced_value DECIMAL(38, 2),
            paid_value DECIMAL(38, 2),
            days_added INTEGER,
            source_updated_at TIMESTAMP,
            process_url VARCHAR,
            content_sha256 VARCHAR NOT NULL
        );
        CREATE TABLE modifications (
            contract_id VARCHAR NOT NULL REFERENCES contracts(contract_id),
            modification_id VARCHAR NOT NULL,
            version_number INTEGER NOT NULL,
            modification_state VARCHAR,
            loaded_at TIMESTAMP,
            approved_at TIMESTAMP,
            version_at TIMESTAMP,
            days_extended INTEGER,
            modification_value DECIMAL(38, 2),
            content_sha256 VARCHAR NOT NULL,
            PRIMARY KEY (modification_id, version_number)
        );
        CREATE TABLE attention_findings (
            finding_id VARCHAR PRIMARY KEY,
            contract_id VARCHAR NOT NULL REFERENCES contracts(contract_id),
            rule_id VARCHAR NOT NULL,
            ruleset_version VARCHAR NOT NULL,
            category VARCHAR NOT NULL,
            evidence_json JSON NOT NULL
        );
        """
    )


def _insert_contracts(
    connection: duckdb.DuckDBPyConnection,
    records: Sequence[Mapping[str, Any]],
) -> None:
    rows = [
        (
            str(item["id_contrato"]),
            _text(item.get("nombre_entidad")),
            _text(item.get("departamento")),
            _text(item.get("ciudad")),
            _text(item.get("sector")),
            _text(item.get("estado_contrato")),
            _timestamp(item.get("fecha_de_firma"), "fecha_de_firma"),
            _timestamp(item.get("fecha_de_inicio_del_contrato"), "fecha_inicio"),
            _timestamp(item.get("fecha_de_fin_del_contrato"), "fecha_fin"),
            _decimal(item.get("valor_del_contrato"), "valor_del_contrato"),
            _decimal(item.get("valor_facturado"), "valor_facturado"),
            _decimal(item.get("valor_pagado"), "valor_pagado"),
            _integer(item.get("dias_adicionados"), "dias_adicionados"),
            _timestamp(item.get("ultima_actualizacion"), "ultima_actualizacion"),
            _text(item.get("urlproceso")),
            str(item["_content_sha256"]),
        )
        for item in records
    ]
    if not rows:
        return
    connection.executemany(
        "INSERT INTO contracts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )


def _insert_modifications(
    connection: duckdb.DuckDBPyConnection,
    records: Sequence[Mapping[str, Any]],
) -> None:
    rows = [
        (
            str(item["id_contrato"]),
            str(item["identificador_modificacion"]),
            _integer(item["numero_version"], "numero_version"),
            _text(item.get("estado_modificacion")),
            _timestamp(item.get("fecha_de_carga"), "fecha_de_carga"),
            _timestamp(item.get("fecha_de_aprobacion"), "fecha_de_aprobacion"),
            _timestamp(item.get("fecha_version"), "fecha_version"),
            _integer(item.get("dias_extendidos"), "dias_extendidos"),
            _decimal(item.get("valor_modificacion"), "valor_modificacion"),
            str(item["_content_sha256"]),
        )
        for item in records
    ]
    if not rows:
        return
    connection.executemany(
        "INSERT INTO modifications VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )


def _insert_findings(
    connection: duckdb.DuckDBPyConnection,
    records: Sequence[Mapping[str, Any]],
) -> None:
    rows = []
    for item in records:
        evidence = json.dumps(
            item["evidence"],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        identity = json.dumps(
            {
                "contract_id": str(item["contract_id"]),
                "rule_id": str(item["rule_id"]),
                "ruleset_version": str(item["ruleset_version"]),
                "category": str(item["category"]),
                "evidence": item["evidence"],
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        rows.append(
            (
                hashlib.sha256(identity).hexdigest(),
                str(item["contract_id"]),
                str(item["rule_id"]),
                str(item["ruleset_version"]),
                str(item["category"]),
                evidence,
            )
        )
    if not rows:
        return
    connection.executemany(
        "INSERT INTO attention_findings VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )


def _create_views(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        """
        CREATE OR REPLACE VIEW v_contract_attention_summary AS
        SELECT
            c.contract_id,
            c.entity_name,
            c.department,
            c.contract_state,
            c.contract_value,
            COUNT(f.rule_id) AS finding_count,
            COUNT(f.rule_id) FILTER (
                WHERE f.category = 'data_quality'
            ) AS data_quality_count,
            COUNT(f.rule_id) FILTER (
                WHERE f.category = 'human_review'
            ) AS human_review_count
        FROM contracts AS c
        LEFT JOIN attention_findings AS f USING (contract_id)
        GROUP BY ALL;

        CREATE OR REPLACE VIEW v_rule_counts AS
        SELECT category, rule_id, COUNT(*) AS finding_count
        FROM attention_findings
        GROUP BY category, rule_id;
        """
    )


def build_warehouse(
    database: Path,
    contracts: Sequence[Mapping[str, Any]],
    modifications: Sequence[Mapping[str, Any]],
    findings: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    _validate_references(contracts, modifications, findings)
    database.parent.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(str(database))
    try:
        connection.execute("BEGIN TRANSACTION")
        _create_schema(connection)
        _insert_contracts(connection, contracts)
        _insert_modifications(connection, modifications)
        _insert_findings(connection, findings)
        _create_views(connection)
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise
    finally:
        connection.close()

    return {
        "schema_version": SCHEMA_VERSION,
        "result": "PASS",
        "database_file": database.name,
        "contract_count": len(contracts),
        "modification_count": len(modifications),
        "finding_count": len(findings),
        "views": ["v_contract_attention_summary", "v_rule_counts"],
    }
