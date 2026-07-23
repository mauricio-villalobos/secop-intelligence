from secop_intelligence.privacy import audit_record, audit_records


def test_audit_passes_clean_text() -> None:
    record = {
        "_content_sha256": "abc123",
        "descripcion_del_proceso": "Mantenimiento preventivo de equipos.",
    }

    assert audit_record(record) == []


def test_audit_reports_pattern_without_source_value() -> None:
    record = {
        "_content_sha256": "abc123",
        "descripcion_del_proceso": "Contacto: persona@example.com",
    }

    findings = audit_record(record)

    assert findings == [
        {
            "record_hash": "abc123",
            "field": "descripcion_del_proceso",
            "pattern": "email",
        }
    ]
    assert "persona@example.com" not in str(findings)


def test_audit_summary_requires_review_without_exposing_text() -> None:
    records = [
        {
            "_content_sha256": "abc123",
            "descripcion_del_proceso": "Teléfono 3001234567",
        }
    ]

    report = audit_records(records)

    assert report["result"] == "REVIEW_REQUIRED"
    assert report["finding_count"] == 1
    assert "3001234567" not in str(report)
