from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from math import ceil
from time import sleep
from typing import Any

import httpx

from secop_intelligence.contracts import content_hash

DATASET_ID = "u8cx-r425"
RESOURCE_URL = f"https://www.datos.gov.co/resource/{DATASET_ID}.json"

MODIFICATION_FIELDS = (
    "id_contrato",
    "identificador_modificacion",
    "estado_modificacion",
    "fecha_de_carga",
    "fecha_de_aprobacion",
    "fecha_version",
    "numero_version",
    "dias_extendidos",
    "valor_modificacion",
)

REQUIRED_FIELDS = (
    "id_contrato",
    "identificador_modificacion",
    "numero_version",
)


class ModificationValidationError(ValueError):
    """Raised when modification data violates the source contract."""


def get_page_with_retry(
    client: httpx.Client,
    params: Mapping[str, Any],
    *,
    attempts: int = 4,
) -> list[dict[str, Any]]:
    retryable = {429, 500, 502, 503, 504}
    for attempt in range(attempts):
        response = client.get(RESOURCE_URL, params=params)
        if response.status_code not in retryable:
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list):
                raise ModificationValidationError("API response must be a JSON array")
            return payload
        if attempt + 1 < attempts:
            retry_after = response.headers.get("Retry-After")
            try:
                delay = min(float(retry_after), 30.0)
            except (TypeError, ValueError):
                delay = 2**attempt
            sleep(delay)
    response.raise_for_status()
    raise AssertionError("unreachable")


def normalize_modification(record: Mapping[str, Any]) -> dict[str, Any]:
    unexpected = set(record) - set(MODIFICATION_FIELDS)
    if unexpected:
        fields = ", ".join(sorted(unexpected))
        raise ModificationValidationError(f"unexpected fields received: {fields}")

    missing = [
        field
        for field in REQUIRED_FIELDS
        if field not in record or record[field] in (None, "")
    ]
    if missing:
        fields = ", ".join(missing)
        raise ModificationValidationError(f"required fields missing: {fields}")

    normalized = {field: record.get(field) for field in MODIFICATION_FIELDS}
    normalized["_content_sha256"] = content_hash(normalized)
    return normalized


def logical_key(record: Mapping[str, Any]) -> tuple[str, str]:
    return (
        str(record["identificador_modificacion"]),
        str(record["numero_version"]),
    )


def deduplicate_modifications(
    records: Iterable[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], int, list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for source_record in records:
        record = dict(source_record)
        grouped.setdefault(logical_key(record), []).append(record)

    unique: list[dict[str, Any]] = []
    duplicate_count = 0
    conflicts: list[dict[str, Any]] = []
    for key, versions in grouped.items():
        representations = {
            str(version["_content_sha256"]): version for version in versions
        }
        duplicate_count += len(versions) - len(representations)
        if len(representations) == 1:
            unique.append(next(iter(representations.values())))
            continue

        comparable_fields = set(MODIFICATION_FIELDS)
        differing_fields = sorted(
            field
            for field in comparable_fields
            if len({str(version.get(field)) for version in versions}) > 1
        )
        conflicts.append(
            {
                "id_contrato": str(versions[0]["id_contrato"]),
                "identificador_modificacion": key[0],
                "numero_version": key[1],
                "representations": len(representations),
                "content_hashes": sorted(representations),
                "differing_fields": differing_fields,
            }
        )

    ordered = sorted(
        unique,
        key=lambda item: (
            str(item["id_contrato"]),
            str(item["identificador_modificacion"]),
            int(item["numero_version"]),
        ),
    )
    conflicts.sort(
        key=lambda item: (
            item["id_contrato"],
            item["identificador_modificacion"],
            int(item["numero_version"]),
        )
    )
    return ordered, duplicate_count, conflicts


def orphan_contract_ids(
    modifications: Iterable[Mapping[str, Any]],
    contract_ids: set[str],
) -> set[str]:
    return {
        str(modification["id_contrato"])
        for modification in modifications
        if str(modification["id_contrato"]) not in contract_ids
    }


def build_params(
    contract_ids: Sequence[str],
    *,
    limit: int = 1000,
    offset: int = 0,
) -> dict[str, Any]:
    if not contract_ids:
        raise ValueError("at least one contract ID is required")
    if not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")
    if offset < 0:
        raise ValueError("offset must not be negative")
    escaped_ids = [contract_id.replace("'", "''") for contract_id in contract_ids]
    quoted_ids = ",".join(f"'{contract_id}'" for contract_id in escaped_ids)
    return {
        "$select": ",".join(MODIFICATION_FIELDS),
        "$where": f"id_contrato in ({quoted_ids})",
        "$order": "id_contrato,identificador_modificacion,numero_version",
        "$limit": limit,
        "$offset": offset,
    }


def fetch_modifications(
    contract_ids: Sequence[str],
    *,
    client: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    owns_client = client is None
    active_client = client or httpx.Client(timeout=30.0)
    try:
        response = active_client.get(
            RESOURCE_URL,
            params=build_params(contract_ids),
        )
        response.raise_for_status()
        payload = response.json()
    finally:
        if owns_client:
            active_client.close()

    if not isinstance(payload, list):
        raise ModificationValidationError("API response must be a JSON array")
    return [normalize_modification(record) for record in payload]


def fetch_modifications_batched(
    contract_ids: Sequence[str],
    *,
    batch_size: int = 150,
    page_size: int = 1000,
    client: httpx.Client | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int | str]]:
    unique_ids = sorted(set(contract_ids))
    if not unique_ids:
        raise ValueError("at least one contract ID is required")
    if not 1 <= batch_size <= 200:
        raise ValueError("batch_size must be between 1 and 200")
    if not 1 <= page_size <= 1000:
        raise ValueError("page_size must be between 1 and 1000")

    owns_client = client is None
    active_client = client or httpx.Client(timeout=60.0)
    records: list[dict[str, Any]] = []
    page_count = 0
    completed_batches = 0
    try:
        for start in range(0, len(unique_ids), batch_size):
            batch = unique_ids[start : start + batch_size]
            offset = 0
            while True:
                payload = get_page_with_retry(
                    active_client,
                    build_params(
                        batch,
                        limit=page_size,
                        offset=offset,
                    ),
                )
                records.extend(normalize_modification(record) for record in payload)
                page_count += 1
                if len(payload) < page_size:
                    break
                offset += len(payload)
            completed_batches += 1
    finally:
        if owns_client:
            active_client.close()

    collection_hash = content_hash(
        {"content_hashes": sorted(str(item["_content_sha256"]) for item in records)}
    )
    evidence: dict[str, int | str] = {
        "result": "PASS",
        "input_contract_count": len(unique_ids),
        "batch_size": batch_size,
        "batch_count": ceil(len(unique_ids) / batch_size),
        "completed_batches": completed_batches,
        "page_size": page_size,
        "page_count": page_count,
        "source_record_count": len(records),
        "collection_sha256": collection_hash,
    }
    return records, evidence
