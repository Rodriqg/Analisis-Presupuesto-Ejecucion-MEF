# Capa Silver: interpretación de los notebooks

Este documento acompaña a los notebooks de `data/silver/` y sigue su orden.

| Notebook | Fuente | Estado |
| --- | --- | --- |
| `03_siaf.ipynb` | SIAF: tabla Silver `siaf_ingreso` | ✅ |
| `05a_silver_renamu_mapeo.ipynb` | RENAMU: selección de variables y verificación de `renamu_mapeo.yaml` | ✅ |
| `05b_silver_renamu.ipynb` | RENAMU: tabla Silver `renamu_finanzas` | ✅ |
| `04_silver_sismepre.ipynb` | SISMEPRE | Pendiente |

---

## 03 — SIAF: tabla `siaf_ingreso`

**Flujo:** igual que `05b`, en un solo notebook. El SIAF no necesita un mapeo: sus 36 columnas son las mismas en los 18 años. Corre en unos 6 minutos y guarda una caché en disco (`.spark_tmp/`) para no releer los 7,3 GB en cada paso.

### 1. Archivos y columnas
- **Archivos:** se usan los 18 (2009–2024 anual, 2025–2026 *Diario*). Los *Mensual* no se descargan (D-005).
- **Filas:** solo el nivel **M** y, dentro de él, las **municipalidades**.
  - E (nacional) y R (regional) no son municipalidades y no se cruzan con el RENAMU ni el SISMEPRE.
  - Las mancomunidades son asociaciones de municipalidades: usan el `ubigeo` de su sede y sumarlas contaría dos veces las transferencias de sus socias.
  - Todo se cuenta como *fuera de alcance*.
- **Columnas:** se quitan 6 sin información en el nivel M (`NIVEL_GOBIERNO`, `SECTOR`, `PLIEGO` y sus nombres). Se conservan el período, la ejecutora, la ubicación, el clasificador (código y nombre) y los montos.

### 2–3. Carga y diagnóstico
| Hallazgo | Resultado |
| --- | --- |
| Filas cargadas = manifest | 15 204 055 en los 18 archivos |
| Fuera de alcance | 2 457 615 (E 927 613 · R 1 525 420 · mancomunidades 4 582) |
| Códigos de ubicación de 1 dígito, ubicación vacía, año o mes inválidos | 0 en municipalidades. Los de 1 dígito del perfilado eran de mancomunidades |
| Ejecutoras que cambian de nombre dentro del año | 11 casos: NAZCA → NASCA, ECHARATI → ECHARATE, MOLINO → MOLINOS, Lima como PROVINCIAL en julio de 2016, … |
| Filas repetidas por la llave de negocio | 74 filas en 37 llaves. Aparecen **cuando la ejecutora cambió de nombre a mitad de año**: la misma partida quedó con el nombre anterior y con el nuevo. Las 291 del perfilado incluían todos los niveles |
| Montos no numéricos | 0 |
| Recaudado negativo | 1 575–7 802 por año (devoluciones y extornos) |
| Filas con todos los montos en 0 | 5–33 % según el año; **se conservan** |

### 4. Limpieza
| Paso | Qué hace |
| --- | --- |
| 4.1 | Alcance: municipalidades del nivel M |
| 4.2 | Se quitan 6 columnas sin información y el resto pasa a minúsculas (`anio`, `mes`) |
| 4.3 | Espacios sobrantes, sobre todo en los nombres |
| 4.4 | `ubigeo` = departamento + provincia + distrito (2 dígitos cada uno) |
| 4.5 | `tipo_municipalidad` según el nombre. **Lima va siempre como PROVINCIAL** (en 2010–2012 figura como "PROVINCIAL DE LIMA") |
| 4.6 | `anio` y `mes` a entero, montos a `decimal(18,2)` (0 no convertidos) |
| 4.7 | Consolidación de las 74 copias en 37 filas, sumando los montos. Queda el **nombre principal del año** (el que se usó en más meses) |
| 4.8 | `anio_parcial` (2026 llega hasta noviembre) |

### 5. Reglas de calidad
Se ejecutan en una celda con un solo resumen. 5.1 muestra el cuadre.
- **Cuarentena** (`SLV-F1-001` a `003`): 0.
- **Registrar:**
  - `SLV-F1-004`: lo fuera de alcance, contado;
  - `SLV-F1-005`: 37 filas consolidadas;
  - `SLV-F1-006`: 0, cada `sec_ejec` tiene un solo `ubigeo` por año;
  - `SLV-F1-007`: 72 301 filas con recaudado negativo.
- **Detener:**
  - `SLV-TODAS-001`, privacidad: OK;
  - `SLV-F1-008`, montos por año: OK en los 18 años;
  - `SLV-TODAS-002`, filas por archivo: OK.

### 6–8. Escritura, bitácora y resumen
- **Silver:** `data/silver/siaf_ingreso/`, Parquet particionado por `anio`: **12 746 403 filas, 41 columnas y 201 MB** (frente a 7,3 GB de CSV). La cuarentena queda vacía.
- **Trazabilidad:** `_run_id`, `_fecha_proceso_utc`, `_fuente` y, por fila, `_archivo_origen`, `_sha256_origen`, `_fecha_descarga` y `_filas_origen`.
- **Bitácora:** el bloque `volumenes` registra silver F1 con 12 746 403 filas y datos de las descargas del 2026-11-20 y 2026-11-22. En `data/auditoria/volumenes.parquet` aparece debajo de Bronze F1.

**Para Gold:**
- PIA y PIM anuales = suma de los meses.
- `dim_ejecutora` con el último nombre de cada `sec_ejec`.
- 2026 marcado como año parcial.

---

## 05a — RENAMU: con qué nos quedamos

**Criterio:** el objetivo es la toma de decisiones sobre el **presupuesto y la ejecución de ingresos** municipales. El SIAF es la fuente principal. Del RENAMU nos quedamos solo con lo más importante y comparable entre años.

### 1–2. Estructura de los diccionarios

Las 7 ediciones 2020–2026 tienen la misma estructura: variables globales, 5 módulos y 19 secciones.

| Módulo | Secciones |
| --- | --- |
| — | Definición de variables globales |
| I | Datos generales de la municipalidad |
| II | Equipamiento y TIC |
| III | Recursos humanos |
| IV | Planificación municipal · Gestión de administración tributaria · Licencias · Desarrollo urbano y/o rural |
| V | Saneamiento ambiental · Educación, cultura y deporte · Servicios sociales · DEMUNA · Salud · Seguridad ciudadana · Gestión del riesgo · Desarrollo económico local · Medio ambiente · Participación vecinal · **Finanzas municipales** |

El notebook muestra los campos por sección y 2 preguntas de ejemplo de cada una.

### 3. Elección

Cada edición tiene **1 300–1 400 columnas** y unas 1 875–1 892 municipalidades. Los códigos **cambian de una edición a otra**: por ejemplo, el cuadro de ingresos se llama `P103`, `P113`, `P118`, `C115`, `C119`, `C100` y `C96` según el año. Armonizar todo sería muy costoso y poco útil. Por eso se conserva solo:

| Qué | Por qué |
| --- | --- |
| **Variables globales** (`Ubigeo`, `Tipomuni`, departamento, provincia, distrito) | Son la conexión con el SIAF y el SISMEPRE, y sirven para segmentar |
| **Finanzas municipales: ingresos ejecutados**: informante, total y las 4 categorías principales | Es el tema del proyecto |
| **Finanzas municipales: gastos ejecutados**: informante, total y las 3 categorías principales | Complementa a los ingresos; nuestra fuente SIAF trae solo ingresos |

- **Solo el total y la categoría principal.** El detalle (por ejemplo, `C97_1_1` *Personal y obligaciones sociales*) cambia entre ediciones y no encajaría en la serie.
- **Lo que se descarta:** el directorio (datos de contacto), el inventario, el personal, la planificación, las licencias, el desarrollo urbano y los servicios públicos locales. Ninguno informa sobre los ingresos.
- **Nota:** *Gestión de administración tributaria* (personal tributario, ejecución coactiva) podría servir más adelante para explicar la recaudación. Solo existe desde 2015 y con otros códigos, así que no entra en esta selección.

### 4–5. Códigos por edición

| Edición | Ingresos: informante · total · I corrientes · II capital · III transferencias · IV financiamiento | Gastos: informante · total · I corrientes · II capital · III deuda |
| --- | --- | --- |
| 2009 | `VFI_P102` · `P102_01` · `_02` · `_60` · — · `_71` + `_74` | `VFI_P104` · `P104_01` · `_02` · `_08` · `_13` |
| 2010–2011 | `VFI_P103` · `P103_01` · `_02` · `_33` · `_36` · `_43` | `VFI_P104` · `P104_01` · `_02` · `_08` · `_13` |
| 2012 | `VFI_P113` · `P113_01` · `_02` · `_33` · `_36` · `_43` | `VFI_P105` · `P105_01` · `_02` · `_08` · `_13` |
| 2013 | igual a 2012 | `VFI_P114` · `P114_01` · `_02` · `_08` · `_13` |
| 2014 · 2016 | **no existe el cuadro** | **no existe el cuadro** |
| 2015 | `VFI_P118` · `P118` · `_1` · `_2` · `_3` · `_4` | `VFI_P119` · `P119` · `_1` · `_2` · `_3` |
| 2017 | `VFI_C115` · `C115` · `_1` … `_4` | `VFI_C116` · `C116` · `_1` … `_3` |
| 2018 | `VFI_C119` · `C119` · `_1` … `_4` | `VFI_C120` · `C120` · `_1` … `_3` |
| 2019 | `VFI_C100` · `C100` · `_1` … `_4` | `VFI_C101` · `C101` · `_1` … `_3` |
| 2020–2026 | `VFI_C96` · `C96` · `_1` … `_4` | `VFI_C97` · `C97` · `_1` … `_3` |

**Todos los códigos se verificaron en el CSV de su edición (✓).**

**Notas:**
- **2009:**
  - el PDF llama al cuadro de ingresos `P103`, pero el CSV usa `P102` (con los mismos sufijos);
  - no hay categoría III: las transferencias van dentro de los ingresos corrientes;
  - **IV = `_71` + `_74`.** En el diccionario, *IV. Financiamiento* (`_71`) incluye el endeudamiento interno (`_72`), el externo (`_73`) y el saldo de balance (`_74`). En el CSV, `_71` solo trae el endeudamiento (`_71 = _72 + _73`, S/ 334 millones) y deja fuera el saldo de balance (S/ 6 152 millones). Con `_71` + `_74`, el total cuadra con I + II + IV en el 100 % de las municipalidades; con `_71` solo, en el 2,3 %. Desde 2010 el saldo ya está dentro de la IV.
- **2012:** el PDF llama al cuadro de gastos `P114`, pero el CSV usa `P105`.
- **2013:** el PDF no trae el cuadro. **Se usa el diccionario de 2012:** mismo archivo (`C104.csv`, `C105.csv`) y mismos códigos.
- **Año del dato:** en 2009–2015 la edición reporta el mismo año; desde 2017, el año anterior (la edición 2026 trae 2025). Los PDF lo confirman: la edición 2015 dice "…, 2015" y la 2017, "…, 2016". La edición 2016, la del cambio, no trae el cuadro. Por eso el año 2016 sí tiene dato (lo trae la edición 2017) y solo **2014** queda vacío.

### 6. Resultado

El total de ingresos declarado sube de **18 413 millones (2009) a 47 501 millones (2025)**. La serie cubre 2009–2025 salvo **2014**. El gráfico muestra, bajo cada año del dato, la edición que lo trae.

**Hallazgos (verificación hecha durante el análisis, fuera del notebook):**
- **El total declarado coincide con la recaudación municipal del SIAF (±0,5 %) en todos los años.** El INEI prellena el cuadro. Comparar *declarado vs. registrado* no sirve como indicador; solo como control de calidad entre fuentes. La excepción es 2025 (+2,9 %), que se revisará por municipalidad.
- **Separador decimal:** coma en casi todas las ediciones; punto en 2023–2024. No hay separador de miles, así que basta con cambiar `,` por `.`.
- **Corrección:** el "−7 % en 2019–2021" de un reporte anterior era un error de lectura (se borraba la coma decimal).

### 7. Para Silver (`05b`)

**Tabla `renamu_finanzas`:** una fila por municipalidad y edición.
- **Llaves:** `ubigeo`, `edicion`, `anio_dato`, `tipo_municipalidad`.
- **Ingresos:** `ing_informo`, `ing_total`, `ing_corrientes`, `ing_capital`, `ing_transferencias`, `ing_financiamiento` (en 2009 = `_71` + `_74`).
- **Gastos:** `gas_informo`, `gas_total`, `gas_corrientes`, `gas_capital`, `gas_servicio_deuda`.
- **Trazabilidad:** `_run_id`, `_fecha_proceso_utc`, `_fuente`, `_archivo_origen`, `_sha256_origen`, `_fecha_descarga`.

Si una variable no existe en la edición, queda vacía con su `estado_dato`. Las ediciones 2014 y 2016 no aportan filas, y el año del dato 2014 queda sin información.

**Uso en los dashboards (propuesta):**
- **Ingreso vs. gasto por municipalidad:** ¿cuánto del gasto se cubre con lo que se recauda?
- **Estructura del ingreso:** corrientes, capital, transferencias y financiamiento.
- **Control de calidad entre fuentes:** el RENAMU frente al SIAF, en la página de auditoría.

**Mapeo:** los códigos y el archivo de cada cuadro están en `data/silver/renamu_mapeo.yaml`. Es la fuente única: `05a` la verifica y `05b` la usa.
- **Archivo fijo:** algunos códigos se repiten en otro CSV con otra pregunta (en 2009 y 2012, `C093.csv`).
- **Lista de códigos:** significa "sumar esas columnas" (2009: financiamiento).

---

## 05b — RENAMU: tabla `renamu_finanzas`

**Flujo:** primero se cargan todas las filas tal cual. Luego se limpia paso a paso, mostrando qué cambia en cada paso. Al final se aplican las reglas de calidad, se escribe en Parquet, se cuadra y se anota en la bitácora. Corre en unos 30 segundos.

### 1. Carga cruda
- **Qué entra:** 42 747 filas de 23 archivos (en 2009–2017, ingresos y gastos vienen en archivos distintos).
- **Columnas:** solo las del mapeo (`ccdd`, `ccpp`, `ccdi`, el tipo y los dos cuadros), todo como texto.
- **Sin nombres:** departamento, provincia y distrito no se cargan. La conexión es el `ubigeo`, y en Gold los nombres salen de una sola fuente (SIAF).
- **Trazabilidad:** cada fila lleva su archivo, su `sha256`, la fecha de descarga y su número de fila. En la tabla final van con sufijo `_ing` / `_gas`, una por archivo de origen.

### 2. Diagnóstico inicial (antes de limpiar)

Se ve en tres tablas: **2.1 identificación**, **2.2 montos y banderas** y **2.3 tipo de municipalidad**. Cada una muestra solo las columnas con algún caso y trae su nota de diagnóstico.

| Hallazgo | Dónde | Cuántos |
| --- | --- | --- |
| Códigos sin el cero a la izquierda (`1` en vez de `01`) | 2023 (`ccdd`), 2015 y 2024 | 931 valores |
| Celdas con un solo espacio (`" "`) en lugar de vacías | 2009–2013, 2015, 2019, 2023 | 318 valores |
| Montos con coma decimal | Todas salvo 2017 (enteros) y 2023–2024 (punto) | ~174 000 valores |
| Decimales sin cero inicial (`.9`) | 2024 | 2 valores (válidos) |
| Montos vacíos | 2009–2011 y 2023 (municipalidades que no informaron), 2013 y 2019 (celdas sueltas) | pocos; quedan nulos |
| Montos negativos | 2011, 2018, 2025 (más 3 en 2009 al sumar `P102_74`) | 5 en bruto, 8 tras la suma de 2009 |
| Tipo vacío | 2015, archivo de gastos | 2 filas (el tipo se toma del archivo de ingresos) |
| Bandera de informante vacía | 2023 | 1 fila |
| Filas vacías o ubigeos repetidos | — | 0 |

### 3. Limpieza paso a paso

| Paso | Qué hace | Valores cambiados |
| --- | --- | --- |
| 3.1 | Nombres universales de columna (en la carga; los valores no cambian) | — |
| 3.2 | Espacios sobrantes (`trim` y espacios dobles) | 318 |
| 3.3 | Vacíos a nulos. Solo la celda vacía; **un 0 se queda como 0** (0 = respondió cero; nulo = no hay dato) | 318 |
| 3.4 | Marca de filas vacías (`_fila_vacia`) | 0 filas |
| 3.5 | Ceros a la izquierda y `ubigeo`. Hasta 2017 cada municipalidad aparece en dos archivos: `filas_con_ubigeo` es el doble de `municipalidades` | 931 |
| 3.6 | Tipo: 1 → PROVINCIAL, 2 → DISTRITAL, 3 → CENTRO POBLADO (se guarda `tipo_codigo`) | — |
| 3.7 | Montos a `double` (coma → punto) y banderas a entero | 173 941 (0 no convertidos) |
| 3.8 | `anio_dato` y suma de 2009: financiamiento = `P102_71` (endeudamiento) + `P102_74` (saldo de balance, que solo en 2009 va fuera de la IV) | 1 791 de 1 834 (las que tienen saldo ≠ 0) |
| 3.9 | Unión de ingresos y gastos por `ubigeo` (2009–2017) | 0 en un solo archivo |
| 3.10 | Estados: `INFORMO`, `NO_INFORMO` (33, en 2009–2011), `SIN_RESPUESTA` (1, en 2023) | — |

### 4. Antes / después
- **Filas:** 29 841 en la tabla limpia (una por municipalidad y edición).
- **Montos:** los totales de ingresos y gastos son **idénticos** antes y después en las 16 ediciones.

### 5. Reglas de calidad

Todas se ejecutan en **una sola celda**, que muestra un resumen (regla, acción, evaluadas, fallidas, estado). Las de tipo *detener* paran el notebook después de mostrarlo. El detalle del cuadre (por archivo y montos por edición) está en **5.1**.

| # | Regla | Qué verifica | Acción | Resultado |
| --- | --- | --- | --- | --- |
| 1 | `SLV-F3-003` | `ubigeo` de 6 dígitos, sin departamento `00`, y fila con datos | Cuarentena | 0 |
| 2 | `SLV-F3-001` | Una sola fila por municipalidad en su archivo | Cuarentena (todas las copias) | 0 |
| 3 | `SLV-F3-002` | Tipo 1 o 2; el 3 (centro poblado) es fuera de alcance; otro o vacío, cuarentena | Cuarentena o fuera de alcance | 0 y 0 |
| 4 | `SLV-TODAS-001` | La salida no tiene columnas de datos personales | Detener | OK |
| 5 | `SLV-TODAS-002` | Carga cruda = Silver + cuarentena + fuera de alcance, por archivo; y los montos, por edición | Detener | OK (42 747 filas) |
| 6 | `SLV-F3-005` | El total es la suma de sus categorías (±1 sol por categoría) | Registrar | 1: 2026, `150113`, ingresos +11 709 soles |
| 7 | `SLV-F3-006` | Montos numéricos y no negativos | Registrar | 8 negativos: 5 en financiamiento (2009 ×3, 2011, 2018) y 3 en ingresos corrientes (2025) |
| 8 | `SLV-F3-007` | Bandera de informante: no informó (0) o vacía (sin respuesta) | Registrar | 34 (33 no informó en 2009–2011, 1 sin respuesta en 2023); ninguna trae montos |

- **Cuarentena:** la fila no entra a Silver; se guarda con `_regla` y `_motivo`.
- **Registrar:** la fila entra a Silver y el id de la regla queda en `_alertas` (43 filas con alerta).
- **Pendientes para el cruce con el SIAF:** `SLV-F3-004` (tipo RENAMU vs. SIAF) y `SLV-X-001` (municipalidades del SIAF sin RENAMU).

### 6–8. Escritura, bitácora y resumen

**Recorrido de las filas:**

| Etapa | Filas |
| --- | --- |
| 1. Carga cruda (23 archivos) | 42 747 |
| 2. Tabla limpia (ingresos y gastos unidos en una fila hasta 2017) | 29 841 |
| 3. Cuarentena | 0 |
| 4. Fuera de alcance (centro poblado) | 0 |
| 5. Silver | 29 841 |

- **Silver:** `data/silver/renamu_finanzas/`, Parquet particionado por `edicion`: 29 841 filas y 30 columnas (identificación, 11 variables, 2 estados, `_alertas` y trazabilidad). Se vuelve a leer y se verifica el conteo.
- **Cuarentena:** `data/quarantine/renamu_finanzas/`, vacía (se escribe igual para que exista el esquema).
- **Bitácora:** una línea por ejecución en `data/silver/bitacora_ejecuciones.jsonl`, con el bloque `volumenes` en formato de auditoría: capa `silver`, fuente `F3`, tabla `renamu_finanzas`, 43 archivos Parquet, 29 841 filas, 2,3 MB y `fecha_datos` = 2026-11-20, la descarga de Bronze de origen. También trae los cambios de la limpieza y el resultado de cada regla.
- **Auditoría:** al final se reconstruye `data/auditoria/volumenes.parquet`, donde Silver F3 aparece debajo de Bronze F1/F2/F3.
- **Resumen final (parte 8):** en markdown, sin código.

**Para Gold:**
- Excluir de los promedios las filas con `estado_*` = `NO_INFORMO` o `SIN_RESPUESTA`.
- Revisar en la página de auditoría las filas con `_alertas`.
- Los nombres de las municipalidades se toman del SIAF por `ubigeo`.
