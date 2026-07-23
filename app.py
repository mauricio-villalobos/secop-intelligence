from __future__ import annotations

from datetime import UTC, datetime

import streamlit as st

from secop_intelligence.analytics import (
    ALL,
    CATEGORY_LABELS,
    LANE_LABELS,
    RULE_LABELS,
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
from secop_intelligence.demo import resolve_database
from secop_intelligence.review_export import build_review_artifact

DATABASE, DEMO_MODE = resolve_database()
DISPLAYED_LIMIT = 200

st.set_page_config(
    page_title="Inteligencia SECOP",
    page_icon="🔎",
    layout="wide",
)

st.title("Inteligencia SECOP")
st.caption(
    "Apoyo determinista para decisiones sobre datos públicos minimizados. "
    "Los hallazgos requieren revisión humana y no constituyen acusaciones."
)
if DEMO_MODE:
    st.info(
        "Modo de demostración pública: todas las entidades, contratos y "
        "evidencias son sintéticos. La validación a escala completa se ejecutó "
        "localmente sobre datos oficiales de SECOP II minimizados."
    )

try:
    metrics = overview(DATABASE)
    options = filter_options(DATABASE)
except AnalyticsDatabaseError as error:
    st.error(str(error))
    st.code("uv run secop-build-warehouse")
    st.stop()

columns = st.columns(5)
columns[0].metric("Contratos", metrics["contract_count"])
columns[1].metric("Hallazgos", metrics["finding_count"])
columns[2].metric("Contratos marcados", metrics["contracts_with_findings"])
columns[3].metric("Revisión humana", metrics["human_review_count"])
columns[4].metric("Calidad de datos", metrics["data_quality_count"])

summary_tab, queue_tab, methodology_tab = st.tabs(
    ["Resumen de reglas", "Cola de revisión", "Metodología"]
)

with summary_tab:
    st.subheader("Carriles operativos de atención")
    lanes = present_lane_counts(lane_counts(DATABASE))
    st.dataframe(
        lanes,
        width="stretch",
        hide_index=True,
        column_config={
            "Contratos": st.column_config.NumberColumn(format="%d"),
            "Hallazgos": st.column_config.NumberColumn(format="%d"),
        },
    )

    st.subheader("Conteos transparentes por regla")
    counts = present_rule_counts(rule_counts(DATABASE))
    st.dataframe(
        counts,
        width="stretch",
        hide_index=True,
        column_config={
            "Hallazgos": st.column_config.NumberColumn(format="%d"),
        },
    )

with queue_tab:
    filter_columns = st.columns(4)
    lane_id = filter_columns[0].selectbox(
        "Carril de atención",
        options["lanes"],
        format_func=lambda value: LANE_LABELS.get(value, value),
    )
    category = filter_columns[1].selectbox(
        "Categoría",
        options["categories"],
        format_func=lambda value: CATEGORY_LABELS.get(value, value),
    )
    rule_id = filter_columns[2].selectbox(
        "Regla",
        options["rules"],
        format_func=lambda value: RULE_LABELS.get(value, value),
    )
    contract_state = filter_columns[3].selectbox(
        "Estado del contrato",
        options["states"],
    )
    queue = present_queue(
        review_queue(
            DATABASE,
            category=category,
            rule_id=rule_id,
            contract_state=contract_state,
            lane_id=lane_id,
            limit=DISPLAYED_LIMIT,
        )
    )
    st.caption(f"{len(queue)} hallazgos con evidencia")
    export_payload = build_review_artifact(
        queue,
        filters={
            "attention_lane": lane_id,
            "category": category,
            "contract_state": contract_state,
            "rule_id": rule_id,
        },
        generated_at=datetime.now(UTC),
        displayed_limit=DISPLAYED_LIMIT,
    )
    st.download_button(
        "Descargar paquete de revisión visible",
        data=export_payload,
        file_name="secop-review-package.zip",
        mime="application/zip",
    )
    selection = st.dataframe(
        queue,
        width="stretch",
        hide_index=True,
        key="review_queue_table",
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "Valor (COP)": st.column_config.NumberColumn(format="localized"),
            "Evidencia": st.column_config.TextColumn(width="large"),
        },
    )
    selected_rows = selection.selection.rows
    if selected_rows:
        selected = queue[selected_rows[0]]
        detail = contract_detail(DATABASE, selected["ID del contrato"])
        if detail is None:
            st.error(
                "El contrato seleccionado ya no está en la base de datos aceptada."
            )
        else:
            contract = detail["contract"]
            modifications = detail["modifications"]
            st.divider()
            st.subheader(f"Caso contractual · {contract['contract_id']}")
            st.caption(
                "Contexto trazable para revisión humana. Los valores de la "
                "fuente no son conclusiones legales."
            )

            detail_columns = st.columns(4)
            detail_columns[0].metric(
                "Estado",
                contract["contract_state"] or "—",
            )
            detail_columns[1].metric(
                "Valor contractual (COP)",
                contract["contract_value"] or 0,
            )
            detail_columns[2].metric(
                "Registros de modificación",
                modifications["modification_count"],
            )
            detail_columns[3].metric(
                "Registros de prórroga",
                modifications["extension_record_count"],
            )

            st.write(f"**Entidad:** {contract['entity_name'] or '—'}")
            st.write(
                f"**Ubicación:** {contract['city'] or '—'}, "
                f"{contract['department'] or '—'}"
            )
            st.write(
                f"**Período:** {contract['starts_at'] or '—'} → "
                f"{contract['ends_at'] or '—'}"
            )

            process_url = trusted_process_url(contract["process_url"])
            if process_url:
                st.link_button("Abrir proceso oficial en SECOP", process_url)
            elif contract["process_url"]:
                st.warning(
                    "Existe una URL de origen, pero su host no pertenece a la "
                    "lista oficial permitida de SECOP."
                )

            st.markdown("#### Hallazgos con evidencia")
            st.dataframe(
                present_detail_findings(detail["findings"]),
                width="stretch",
                hide_index=True,
                column_config={
                    "Evidencia": st.column_config.TextColumn(width="large"),
                },
            )

with methodology_tab:
    st.markdown(
        """
        - Los registros provienen de conjuntos oficiales de SECOP II.
        - Los identificadores personales y campos bancarios se excluyen
          mediante una lista permitida.
        - Las versiones conflictivas de modificaciones se ponen en cuarentena.
        - Cada hallazgo conserva su regla determinista y evidencia.
        - Los carriles organizan los hallazgos sin suprimirlos.
        - Los carriles son etiquetas deterministas, no puntajes o conclusiones.
        - La interfaz abre DuckDB en modo de solo lectura.
        - No se produce un puntaje compuesto de riesgo, clasificación de fraude
          ni decisión automática.
        """
    )

st.caption(
    f"Reglas 1.0 · Base de datos: {DATABASE} · Valor predeterminado de filtros: {ALL}"
)
