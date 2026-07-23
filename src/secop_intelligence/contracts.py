from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx

DATASET_ID = "jbjy-vk9h"
RESOURCE_URL = f"https://www.datos.gov.co/resource/{DATASET_ID}.json"

CONTRACT_FIELDS = (
    "id_contrato",
    "nombre_entidad",
    "departamento",
    "ciudad",
    "sector",
    "proceso_de_compra",
    "estado_contrato",
    "codigo_de_categoria_principal",
    "descripcion_del_proceso",
    "tipo_de_contrato",
    "modalidad_de_contratacion",
    "fecha_de_firma",
    "fecha_de_inicio_del_contrato",
    "fecha_de_fin_del_contrato",
    "valor_del_contrato",
    "valor_facturado",
    "valor_pagado",
    "valor_pendiente_de_pago",
    "valor_pendiente_de_ejecucion",
    "dias_adicionados",
    "ultima_actualizacion",
    "urlproceso",
)

REQUIRED_FIELDS = (
    "id_contrato",
    "departamento",
    "fecha_de_firma",
    "valor_del_contrato",
    "urlproceso",
)

PROHIBITED_FIELDS = frozenset(
    {
        "documento_proveedor",
        "identificaci_n_representante_legal",
        "nombre_representante_legal",
        "nombre_supervisor",
        "nombre_ordenador_del_gasto",
        "nombre_ordenador_de_pago",
        "direcci_n_de_ejecuci_n_del_contrato",
        "nombre_del_banco",
        "tipo_de_cuenta",
        "n_mero_de_cuenta",
        "g_nero_representante_legal",
        "nacionalidad_representante_legal",
    }
)


class ContractValidationError(ValueError):
    """Raised when a source record violates the ingestion contract."""


class ContractCompletenessError(RuntimeError):
    """Raised when a bounded source snapshot cannot be proven complete."""


@dataclass(frozen=True)
class ContractQuery:
    department: str
    signed_from: date
    signed_before: date
    limit: int = 100
    page_size: int = 1000

    def __post_init__(self) -> None:
        if self.signed_from >= self.signed_before:
            raise ValueError("signed_from must be earlier than signed_before")
        if not 1 <= self.limit <= 100_000:
            raise ValueError("limit must be between 1 and 100000")
        if not 1 <= self.page_size <= 1000:
            raise ValueError("page_size must be between 1 and 1000")
        if not self.department.strip():
            raise ValueError("department must not be empty")

    def where_clause(self) -> str:
        department = self.department.replace("'", "''")
        return (
            f"departamento='{department}' "
            f"AND fecha_de_firma >= '{self.signed_from.isoformat()}T00:00:00' "
            f"AND fecha_de_firma < '{self.signed_before.isoformat()}T00:00:00'"
        )

    def params(
        self,
        *,
        offset: int = 0,
        page_limit: int | None = None,
    ) -> dict[str, str | int]:
        if offset < 0:
            raise ValueError("offset must not be negative")
        effective_limit = page_limit or min(self.limit, self.page_size)
        if not 1 <= effective_limit <= self.page_size:
            raise ValueError("page_limit exceeds configured page_size")
        return {
            "$select": ",".join(CONTRACT_FIELDS),
            "$where": self.where_clause(),
            "$order": "fecha_de_firma,id_contrato",
            "$limit": effective_limit,
            "$offset": offset,
        }

    def count_params(self) -> dict[str, str]:
        return {
            "$select": "count(*) AS record_count",
            "$where": self.where_clause(),
        }


def normalize_record(record: Mapping[str, Any]) -> dict[str, Any]:
    unexpected = set(record) - set(CONTRACT_FIELDS)
    prohibited = set(record) & PROHIBITED_FIELDS
    if prohibited:
        fields = ", ".join(sorted(prohibited))
        raise ContractValidationError(f"prohibited fields received: {fields}")
    if unexpected:
        fields = ", ".join(sorted(unexpected))
        raise ContractValidationError(f"unexpected fields received: {fields}")

    normalized = {field: record.get(field) for field in CONTRACT_FIELDS}
    normalized["urlproceso"] = normalize_process_url(record.get("urlproceso"))

    missing = [field for field in REQUIRED_FIELDS if normalized[field] in (None, "")]
    if missing:
        fields = ", ".join(missing)
        raise ContractValidationError(f"required fields missing: {fields}")

    normalized["_content_sha256"] = content_hash(normalized)
    return normalized


def normalize_process_url(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, str):
        return value.strip() or None
    if not isinstance(value, Mapping):
        raise ContractValidationError("urlproceso must be a URL object or string")

    unexpected = set(value) - {"url", "description"}
    if unexpected:
        raise ContractValidationError("urlproceso contains unexpected properties")
    url = value.get("url")
    if not isinstance(url, str) or not url.strip():
        raise ContractValidationError("urlproceso.url must be a non-empty string")
    return url.strip()


def content_hash(record: Mapping[str, Any]) -> str:
    payload = json.dumps(
        record,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def fetch_contracts(
    query: ContractQuery,
    *,
    client: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    owns_client = client is None
    active_client = client or httpx.Client(timeout=30.0)
    try:
        response = active_client.get(RESOURCE_URL, params=query.params())
        response.raise_for_status()
        payload = response.json()
    finally:
        if owns_client:
            active_client.close()

    if not isinstance(payload, list):
        raise ContractValidationError("API response must be a JSON array")
    return [normalize_record(record) for record in payload]


def fetch_contract_count(
    query: ContractQuery,
    *,
    client: httpx.Client | None = None,
) -> int:
    owns_client = client is None
    active_client = client or httpx.Client(timeout=30.0)
    try:
        response = active_client.get(RESOURCE_URL, params=query.count_params())
        response.raise_for_status()
        payload = response.json()
    finally:
        if owns_client:
            active_client.close()

    if (
        not isinstance(payload, list)
        or len(payload) != 1
        or not isinstance(payload[0], Mapping)
    ):
        raise ContractValidationError("count response must contain one object")
    try:
        count = int(payload[0]["record_count"])
    except (KeyError, TypeError, ValueError) as error:
        raise ContractValidationError("invalid count response") from error
    if count < 0:
        raise ContractValidationError("record count must not be negative")
    return count


def fetch_complete_contracts(
    query: ContractQuery,
    *,
    client: httpx.Client | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int | str]]:
    owns_client = client is None
    active_client = client or httpx.Client(timeout=30.0)
    try:
        expected_before = fetch_contract_count(query, client=active_client)
        if expected_before > query.limit:
            raise ContractCompletenessError(
                f"source count {expected_before} exceeds max records {query.limit}"
            )

        records: list[dict[str, Any]] = []
        pages = 0
        while len(records) < expected_before:
            page_limit = min(query.page_size, expected_before - len(records))
            response = active_client.get(
                RESOURCE_URL,
                params=query.params(
                    offset=len(records),
                    page_limit=page_limit,
                ),
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list):
                raise ContractValidationError("API response must be a JSON array")
            if not payload:
                raise ContractCompletenessError(
                    "source returned an empty page before expected count"
                )
            records.extend(normalize_record(record) for record in payload)
            pages += 1

        expected_after = fetch_contract_count(query, client=active_client)
    finally:
        if owns_client:
            active_client.close()

    duplicates = duplicate_contract_ids(records)
    if duplicates:
        raise ContractCompletenessError("duplicate contract IDs received")
    if expected_before != expected_after:
        raise ContractCompletenessError("source count changed during pagination")
    if len(records) != expected_before:
        raise ContractCompletenessError("received count differs from source count")

    collection_hash = hashlib.sha256(
        "".join(sorted(str(item["_content_sha256"]) for item in records)).encode()
    ).hexdigest()
    evidence: dict[str, int | str] = {
        "result": "PASS",
        "expected_count_before": expected_before,
        "expected_count_after": expected_after,
        "record_count": len(records),
        "unique_contract_ids": len(records),
        "page_count": pages,
        "page_size": query.page_size,
        "collection_sha256": collection_hash,
    }
    return records, evidence


def duplicate_contract_ids(records: Iterable[Mapping[str, Any]]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for record in records:
        contract_id = str(record["id_contrato"])
        if contract_id in seen:
            duplicates.add(contract_id)
        seen.add(contract_id)
    return duplicates
