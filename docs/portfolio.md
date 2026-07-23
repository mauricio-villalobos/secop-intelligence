# Caso de portafolio: Inteligencia SECOP

## Enlaces públicos

- Demo desplegada: <https://secop-intelligence-co.streamlit.app>
- Código fuente:
  <https://github.com/mauricio-villalobos/secop-intelligence>
- Release reproducible:
  <https://github.com/mauricio-villalobos/secop-intelligence/releases/tag/v0.1.0>

## Problema

Los datos públicos de contratación tienen volumen, cambios de estado,
modificaciones y problemas de calidad que dificultan una revisión consistente.
El proyecto convierte una cohorte oficial acotada en una cola trazable para
revisión humana, sin afirmar fraude ni automatizar decisiones.

## Resultado validado

- 51.662 contratos oficiales procesados;
- 523.017 modificaciones curadas;
- 69.794 hallazgos deterministas;
- 41.363 contratos organizados para atención;
- consultas y filtros interactivos por debajo de tres segundos;
- 12 incrementos integrados con pruebas y CI en verde.

Estas cifras pertenecen a la ejecución local aceptada. La demostración pública
usa datos sintéticos explícitos para no publicar casos individualizados.

La aplicación pública fue verificada desde una sesión externa el 23 de julio
de 2026: cargó sin autenticación, mostró el aviso de datos sintéticos y presentó
las 36 entidades demostrativas esperadas. Esta verificación confirma la
disponibilidad del producto público, no sustituye la aceptación local de la
cohorte oficial.

## Arquitectura

```text
API oficial SECOP II
        |
        v
Ingesta paginada y minimizada
        |
        v
Curación y cuarentena de conflictos
        |
        v
Reglas deterministas versionadas
        |
        v
DuckDB tipado y de solo lectura
        |
        v
Interfaz Streamlit + exportación trazable
```

## Decisiones de ingeniería

- allowlist de campos en lugar de almacenar respuestas completas;
- exclusión de identificadores personales y datos bancarios;
- conteos de completitud antes y después de la paginación;
- deduplicación exacta sin ocultar versiones conflictivas;
- evidencia y versión de regla en cada hallazgo;
- consultas parametrizadas y enlaces restringidos al host oficial;
- exportaciones acotadas con manifiesto e integridad SHA-256;
- demo pública sintética separada de la evidencia de aceptación.

## Competencias demostradas

Python, modelado de datos, APIs, DuckDB, pruebas automatizadas, CI/CD,
seguridad por diseño, privacidad, observabilidad, documentación técnica y
construcción incremental de producto.
