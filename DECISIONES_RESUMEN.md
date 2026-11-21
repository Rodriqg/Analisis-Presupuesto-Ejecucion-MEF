# Decisiones — resumen

Una línea por decisión. El detalle (motivo, evidencia e impacto) está en [`DECISIONES.md`](DECISIONES.md).

| ID | Fase | Decisión |
| --- | --- | --- |
| D-001 | 0 | Se eliminó el borrador inicial y las carpetas vacías. No se usan pruebas con pytest: la verificación se hace en los notebooks |
| D-002 | 0 | Se agregó a la estructura una prueba del entorno y un CSV sintético en `data/_muestras/` |
| D-003 | 0 | Entorno: Python 3.14, PySpark 4.3, Java 21, pandas 3 (sin conversión Spark↔pandas por Arrow) |
| D-004 | 0 | Spark local: 4 GB de driver, 24 particiones, zona horaria Lima, ANSI desactivado (los casts inválidos se miden con reglas) |
| D-005 | 1 | SIAF 2009–2026. En 2025 y 2026 se usa el archivo **Diario** y se descarta el Mensual (repetido en 2025, desactualizado en 2026). 2026 es año parcial |
| D-006 | 1 | RENAMU: Bronze guarda todas las ediciones; se analiza desde 2020 (mismo formato e incluye la tabla de ingresos C96) |
| D-007 | 1 | *(reemplazada por D-008)* F4 como copia manual |
| D-008 | 1 | **Se descarta `CategoriasMunicipalidades.csv`.** La categoría se arma en Silver: `clasificacion_pi` (A–G, del SISMEPRE) y `tipo_municipalidad` (provincial o distrital, del RENAMU) |
| D-009 | 1 | Toda la configuración en **un solo `config.yaml`** en la raíz (pensando en Docker) |
| D-010 | 1 | Del perfilado: llave **UBIGEO + año**, con `SEC_EJEC` como puente entre el SIAF y el SISMEPRE. Silver incluye solo el nivel M y municipalidades (sin mancomunidades). PIA y PIM se analizan anuales. Las filas mal formadas van a cuarentena |
| D-011 | 1 | Se agrega el **RENAMU 2026**; el análisis del RENAMU pasa a ser **2020–2026** |
| D-012 | — | Reorganización: los notebooks, el `.md` y la bitácora de cada capa viven en `data/<capa>/`; se crea `data/auditoria/`; se elimina `docs/`; las decisiones pasan a la raíz |

**Pendiente (no bloquea):** P-003, diccionarios oficiales del SIAF y del SISMEPRE (solo se pueden bajar a mano).
