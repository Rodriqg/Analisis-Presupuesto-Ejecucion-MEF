# Bitácora de decisiones (detallada)

Registro completo de las decisiones tomadas y de los cambios a `ARQUITECTURA.md`: es la guía de trabajo del proyecto. La entrada más reciente va primero.
La versión corta, para lectura rápida, está en [`DECISIONES_RESUMEN.md`](DECISIONES_RESUMEN.md).

| Campo | Contenido |
| --- | --- |
| **ID** | D-NNN |
| **Fecha** | AAAA-MM-DD |
| **Fase** | fase en la que se tomó |
| **Decisión** | qué se decidió |
| **Motivo** | por qué |
| **Impacto** | qué archivos o fases afecta |

---

## Pendientes

| ID | Tema | Estado |
| --- | --- | --- |
| P-001 | Rango de años | ✅ Resuelto en D-005 y D-006 |
| P-002 | SIAF 2025–2026: Diario vs. Mensual | ✅ Resuelto en D-005 |
| P-003 | Diccionarios del SIAF y del SISMEPRE | ⏳ **No bloquea:** el perfilado documenta las columnas reales (`data/bronze/02_bronze_perfilado.ipynb`, sección 2.3), y los nombres del SIAF son descriptivos. Las URLs supuestas dan 404 y el portal del MEF solo las expone por una API interna. **Hay que descargarlos a mano** desde la página de cada dataset y copiarlos a la carpeta de la fuente. El RENAMU trae sus diccionarios en PDF dentro de cada ZIP. |
| P-004 | `CategoriasMunicipalidades.csv` | ✅ Descartado; la categoría se deriva en Silver (D-008) |
| P-005 | Años del RENAMU | ✅ Resuelto en D-006 |
| P-006 | Llave de integración | ✅ Confirmada en el perfilado (D-010) |

---

## D-012 · 2026-11-20 · Reorganización: notebooks y documentación junto a su capa

- **Decisión (del usuario):**
  1. Cada capa vive en `data/<capa>/` con sus notebooks, su `.md` de interpretación y su bitácora:
     - `data/bronze/` contiene `01_bronze_descarga.ipynb`, `02_bronze_perfilado.ipynb`, `bronze.md`, `manifest.json` y `bitacora_ejecuciones.jsonl`.
     - Lo mismo en `data/silver/` y `data/gold/`.
     - La prueba del entorno queda en `data/00_prueba_spark.ipynb`.
  2. Se crea `data/auditoria/`, que consolidará en Parquet las bitácoras y la calidad de Bronze a Gold. Se mantiene `data/quarantine/`.
  3. Se elimina `docs/`:
     - Las decisiones pasan a la raíz: `DECISIONES.md` (detallada) y `DECISIONES_RESUMEN.md`.
     - Los cierres de fase y los informes sueltos se eliminan: el notebook ejecutado es la evidencia.
     - El `.md` de cada capa sigue el orden de sus notebooks y explica lo que muestran: hallazgos, sugerencias y, al final, la conexión propuesta para la capa siguiente.
  4. Los notebooks **no escriben CSV ni `.md`**: muestran sus resultados y dejan su registro en la bitácora de la capa. Se elimina `data/control/`.
  5. `consumo/` se queda (Power BI, Streamlit y `modelo/`) y lee solo de Gold.
- **Motivo:** la estructura se estaba alejando del orden por fases. Los documentos sueltos no se iban a revisar más adelante.
- **Impacto:**
  - `ARQUITECTURA.md` §4 se reescribe.
  - En `config.yaml → rutas` sale `control` y entra `auditoria`.
  - `src/spark.py` usa `data/auditoria/_spark_warehouse`.

## D-011 · 2026-11-20 · RENAMU 2026 en Bronze y en el análisis (2020–2026)

- **Decisión (del usuario):** se agrega la edición **RENAMU 2026** (`1049-Modulo1963.zip`), que reporta información de 2025. El rango de análisis pasa a **2020–2026** (`config.yaml → anios.renamu_analisis`).
- **Evidencia:** 1 892 municipalidades (las mismas que el SIAF de 2025 y 2026), 1 397 columnas, un solo CSV en UTF-8 con BOM y `;`.
- **Impacto:** el D-006 se extiende hasta 2026. El cruce SIAF ↔ RENAMU usa el año del SIAF igual a la edición; la edición 2026 se cruza con el SIAF 2026.

## D-010 · 2026-11-20 · Fase 1 — Resultados del perfilado que fijan reglas para Silver

- **Decisión:**
  1. **Llave de integración (P-006):** `UBIGEO` de 6 dígitos (más año) identifica a la municipalidad.
     - En el SIAF se arma con `lpad(DEPARTAMENTO_EJECUTORA,2)+lpad(PROVINCIA_EJECUTORA,2)+lpad(DISTRITO_EJECUTORA,2)`.
     - `SEC_EJEC` es el código común del SIAF y del SISMEPRE, con relación 1 a 1 con el UBIGEO.
  2. **Alcance del SIAF en Silver:** `NIVEL_GOBIERNO = 'M'` y ejecutoras cuyo nombre empieza con "MUNICIPALIDAD". Las mancomunidades municipales (19 a 49 por año) se excluyen **y se cuentan**.
  3. **PIA y PIM se analizan como anuales** (suma de meses). Su distribución mensual cambió en 2012.
  4. **Cuarentena en Silver:**
     - Las 9 filas mal formadas del SISMEPRE.
     - Las 8 filas sin UBIGEO del RENAMU 2020.
     - Las filas del SIAF que fallen SLV-F1-001 a SLV-F1-003.
  5. Las reglas `SLV-*` se agregan a `config.yaml → reglas_calidad`.
- **Motivo:** el perfilado con Spark de los 15,2 millones de filas del SIAF, el SISMEPRE completo y el RENAMU 2020–2025 (`data/bronze/bronze.md`, sección 02).
- **Correcciones a evaluaciones anteriores:**
  - El SIAF **sí** tiene Gobierno Nacional (E).
  - El RENAMU histórico **sí** trae una tabla de ingresos con el predial (2009–2012, 2015 y 2017–2019), con códigos distintos en cada edición. D-006 no cambia; el uso del histórico queda como opción para la Fase 2.
- **Impacto:** notebooks `03_silver_siaf`, `04_silver_sismepre` y `05_silver_municipalidad`.

## D-009 · 2026-11-20 · Fase 1 — Configuración en un solo `config.yaml` en la raíz

- **Decisión:** los tres archivos de `config/` (`config.yaml`, `fuentes.yaml` y `reglas_calidad.yaml`) se unen en **un único `config.yaml` en la raíz**. Sus secciones son `proyecto`, `rutas`, `anios`, `descarga`, `spark`, `fuentes` y `reglas_calidad`. `src/config.py` mantiene las mismas funciones (`cargar_config`, `cargar_fuentes`, `cargar_reglas` y `ruta`) y acepta la variable de entorno `FINAL_BI_CONFIG` para usar otro archivo.
- **Motivo:**
  - Lo pidió el usuario, pensando en dockerizar más adelante: un solo archivo es más fácil de montar como volumen (`-v ./config.yaml:/app/config.yaml`) o de cambiar con `FINAL_BI_CONFIG` sin reconstruir la imagen.
  - La carpeta `config/` no era necesaria para Docker. Unificarla simplifica el proyecto.
- **Impacto:** se elimina `config/`. Se actualizan `ARQUITECTURA.md` §4 y §5, el README, `src/` y los notebooks. Si `reglas_calidad` crece mucho en las fases 2 y 3, se puede volver a separar sin cambiar los notebooks, porque todo pasa por `src/config.py`.

## D-008 · 2026-11-20 · Fase 1 — Se descarta F4; la categoría municipal se deriva en Silver

- **Decisión:** se descarta `CategoriasMunicipalidades.csv`, porque no está disponible y no tiene URL pública. La categoría de cada municipalidad se construirá en Silver (`05_silver_municipalidad`) con dos atributos:

| Atributo | Fuente | Columna | Valores | Cobertura |
| --- | --- | --- | --- | --- |
| `tipo_municipalidad` | F3 RENAMU 2020–2025 | `Tipomuni` | 1 = Provincial, 2 = Distrital | Todas las municipalidades (1 874 a 1 891) |
| `clasificacion_pi` | F2 SISMEPRE `rentas_entidad_estado.csv` | `CLASIFICACION` (por `SEC_EJEC` y `ANO_APLICACION`) | A a G (Clasificación de Municipalidades del Programa de Incentivos del MEF) | Ver abajo |

- **Evidencia (perfilado previo con los datos de Bronze):**
  - Los conteos coinciden con la clasificación oficial del MEF de 2022: A = 74, B = 122, C = 42, D = 129 y E = 378.
  - **Desde 2019 ninguna municipalidad cambia de tipo** (0 casos entre 2019 y 2026), así que el tipo se puede tratar como atributo fijo de la municipalidad. En 2013–2018 se usaba otro esquema (A, B, C con otro significado) y **no se usa**.
  - Los tipos **A–E están completos** en el SISMEPRE, porque todas esas municipalidades tienen meta predial. De F y G solo aparecen las que entraron a la meta desde 2024: 336 de F y 368 de G, frente a unas 509 y 634 en la clasificación oficial. En total hay 1 449 municipalidades con tipo.
- **Regla de derivación propuesta para Silver:**
  1. `clasificacion_pi` = la clasificación de 2019–2026 de la municipalidad. Se toma la del último año en que aparece; es igual en todos.
  2. Si la municipalidad no aparece en el SISMEPRE, se usa `"F/G (sin meta predial)"`. Es válido porque A–E están completos, así que la ausencia implica F o G.
  3. `tipo_municipalidad` siempre sale del RENAMU (`Tipomuni`).
- **Impacto:**
  - Se elimina F4 de `config.yaml` y la carpeta `data/bronze/categorias_municipalidades/`.
  - El criterio de cierre de la Fase 1 pasa a ser 3 fuentes (F1–F3).
  - El cruce `SEC_EJEC` (SIAF/SISMEPRE) ↔ `UBIGEO` (RENAMU) se valida en el perfilado.

## D-007 · 2026-11-20 · Fase 1 — F4 Categorías de municipalidades: fuente manual sin URL pública *(reemplazada por D-008)*

- **Decisión:** F4 queda como copia manual. `01_bronze_descarga` busca el archivo en `data/bronze/categorias_municipalidades/<AAAA-MM-DD>/CategoriasMunicipalidades.csv` y, si lo encuentra, lo registra en el manifest con `modo: manual`. Mientras falte, la regla `BRZ-TODAS-004` (severidad alta, solo se registra) queda en ALERTA.
- **Motivo:** el 2026-11-20 se buscó una URL pública y no existe. Lo más cercano es la *Clasificación de Municipalidades del Programa de Incentivos* (tipos A a G), que el MEF publica solo como anexo en PDF de cada decreto supremo.
- **Impacto:** el cierre de la Fase 1 exige las 4 fuentes en Bronze, así que **sin este archivo la Fase 1 no se puede cerrar**.

## D-006 · 2026-11-20 · Fase 1 — RENAMU: Bronze 2009–2025, análisis 2020–2025

- **Decisión:**
  - Bronze guarda **todas las ediciones del RENAMU de 2009 a 2025** en `data/bronze/renamu/<fecha>/<edición>/`. Cada ZIP se descomprime en su propia subcarpeta.
  - Silver y Gold usan **2020–2025**.
  - 2009–2019 se revisan en el perfilado por si alguna variable sirve. Lo más probable es que se descarten, porque no traen los ingresos declarados (C96).
  - La edición 2025 tiene dos formularios: F01 (municipalidades provinciales y distritales) y F02 (municipalidades de centros poblados). **No existe la edición 2026.**
- **Motivo:** de 2020 a 2025 el diseño es el mismo (95–99 % de columnas comunes) y todas las ediciones incluyen C96. Antes de 2020 cambian el formato y la numeración de las preguntas (auditoría en `data/bronze/bronze.md` (sección 01), sección 4.2).
- **Impacto:**
  - La carpeta `renamu_2022` pasa a llamarse `renamu`.
  - Cambian F3 en `ARQUITECTURA.md` §2 y §4 y `config/fuentes.yaml`.
  - Se agrega `anios.renamu_analisis` en `config/config.yaml`.

## D-005 · 2026-11-20 · Fase 1 — Alcance temporal: escenario A con SIAF Diario

- **Decisión:**
  - **SIAF 2009–2026:** los archivos anuales de 2009 a 2024, más `2025-Ingreso-Diario.csv` y `2026-Ingreso-Diario.csv`. **Se descartan los archivos Mensual.**
  - El SISMEPRE se descarga completo.
  - **RENAMU:** **2026 es año parcial**, aun asi se incluye para el análisis.
  - **Motivo:** el usuario eligió el escenario A. En la auditoría, el Mensual de 2025 resultó idéntico al Diario (+2 filas). El Mensual de 2026 está desactualizado: es una foto del 22-oct y le faltan S/ 5 974 millones de recaudación municipal.
- **Impacto:** `config/config.yaml → anios`, `config/fuentes.yaml → F1`. Como el Diario de 2026 cambia todos los días, cada descarga es una foto con su fecha.

---

## D-004 · 2026-11-20 · Fase 0 — Sesión de Spark y parámetros

- **Decisión:** la sesión de Spark se crea solo con `src/spark.py::crear_sesion()`, que lee `config/config.yaml`. Los parámetros son `local[*]`, 4 GB de driver, 24 particiones de shuffle, zona horaria `America/Lima` y `spark.sql.ansi.enabled=false`.
- **Motivo:**
  - El equipo tiene 12 núcleos y unos 7,6 GB de RAM, así que se dejan unos 3,5 GB libres para el sistema y Jupyter.
  - ANSI se desactiva para que los casts inválidos den `NULL` en lugar de detener el job. Esos casos se miden y se envían a cuarentena con reglas de calidad.
- **Impacto:** todos los notebooks. Si cambia la memoria del equipo, se ajusta en `config.yaml`.

## D-003 · 2026-11-20 · Fase 0 — Versiones del entorno

- **Decisión:** Python 3.14, PySpark 4.3.0, Java 21 y pandas 3.1.1. Las versiones quedan fijadas en `requirements.txt`. También se agregan `PyYAML`, `tqdm` y `nbclient`, que no estaban instalados.
- **Motivo:** es el entorno que ya existía en `.venv` y funciona. PySpark 4.3 avisa que pandas 3 no está soportado del todo. El pipeline no usa la conversión Spark↔pandas, así que el aviso se silencia en `crear_sesion()`. Si la Fase 4 o la 5 necesitan `toPandas()`, se reevalúa (la alternativa es pandas 2.x).
- **Impacto:** `requirements.txt`, `src/spark.py`.

## D-002 · 2026-11-20 · Fase 0 — Cambios a la estructura de ARQUITECTURA.md §4

Se agregaron elementos que la guía no tenía:

| Elemento | Para qué |
| --- | --- |
| `notebooks/fase0_preparacion/00_prueba_spark.ipynb` | Evidencia del cierre de la Fase 0. |
| `data/_muestras/` | CSV sintéticos para pruebas. No son datos del proyecto y no pasan por Bronze. |
| `docs/fase0_preparacion/` | Documentación del cierre de la Fase 0. |
| `.gitignore` | Los datos no se versionan; se regeneran con los notebooks. |

## D-001 · 2026-11-20 · Fase 0 — Material previo a la arquitectura

- **Decisión:**
  - Se eliminaron, a pedido del usuario, el notebook borrador `notebooks/01_ingesta_bronce.ipynb` y `data/bronze/untitled.txt` (un catálogo JSON de fuentes truncado).
  - Se eliminaron carpetas vacías y checkpoints automáticos de Jupyter: `data/bronze/{mef_ingresos,renamu/<año>,sismepre,categorias}`, `src/{ingestion,transformations,quality}`, `sql/` y `logs/`.
  - No se crean pruebas automatizadas (`tests/`, pytest), a pedido del usuario. La verificación se hace con notebooks.
- **Motivo:**
  - Era material de borrador y los nombres de carpeta no seguían la guía.
  - Bronze no debe tener archivos que no salgan de una descarga registrada.
- **Impacto:** ninguno sobre los datos (no había nada descargado).
