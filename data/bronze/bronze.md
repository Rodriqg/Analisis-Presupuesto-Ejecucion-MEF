# Capa Bronze: interpretación de los notebooks

Este documento acompaña a `01_bronze_descarga.ipynb` y `02_bronze_perfilado.ipynb` y sigue su orden. Los números exactos están en los notebooks ejecutados; aquí va **qué significan y qué se sugiere**.

---

## 01 — Descarga

El notebook baja las 3 fuentes y las guarda tal cual en una ruta fija, `data/bronze/<fuente>/[<edición>/]<archivo>`. `manifest.json` es el inventario de lo que hay hoy en Bronze: una entrada por archivo vigente con URL, fecha de descarga, `run_id`, tamaño, sha256 y filas (D-014).

| Fuente | Contenido | Tamaño |
| --- | --- | --- |
| F1 SIAF | 18 CSV: 2009–2024 anual + 2025 y 2026 *Diario* | 7,3 GB |
| F2 SISMEPRE | 7 CSV relacionados | 59 MB |
| F3 RENAMU | 19 ZIP (2009–2026, más el F02 de 2025), descomprimidos: ~1 030 CSV + diccionarios PDF | ~350 MB |

**Notas:**
- **Tamaño:** todo Bronze ocupa unos 7,75 GB. Con Silver y Gold se estiman unos 10 GB, lejos de ser un límite para el disco.
- **2025 y 2026 se toman del archivo *Diario*.** "Diario" indica la frecuencia de actualización, no el grano: ambos archivos traen los datos por mes. En 2025 el Mensual es idéntico al Diario (+2 filas). En 2026 el Mensual está desactualizado: es una foto del 22 de octubre y le faltan unos S/ 5 974 millones municipales. Por eso se descarta el Mensual (D-005).
- **RENAMU 2026:** lo agregó el usuario (D-011).
- **`CategoriasMunicipalidades.csv`:** se descartó porque no está disponible (D-008).
- **Reejecución y sobrescritura (D-014):** el notebook se puede volver a ejecutar sin riesgo. Si el servidor informa el mismo tamaño y fecha, no se descarga. Si informa otra fecha pero el contenido es igual (mismo sha256), tampoco se reemplaza; pasa a diario con el SISMEPRE. Si hay una versión nueva, se baja a `.part`, se valida y sobrescribe la anterior (en el RENAMU también se vuelve a descomprimir). Si la descarga falla, la versión anterior queda intacta. Bronze guarda una sola versión de cada archivo y no crece con cada descarga.
- **Bitácora y auditoría:** cada ejecución registra, por fuente, los archivos, las filas, los bytes y la fecha de los datos, más lo descargado en esa sesión. `data/auditoria/volumenes.parquet` junta esas mediciones de todas las capas.

---

## 02 — Perfilado

### 1. Formato real de cada archivo

**1.1 SIAF.** Los 18 archivos vienen en **UTF-8, sin BOM, separados por coma y con saltos de línea CRLF**, todos con 36 columnas. Es un formato uniforme y se leen todos con la misma configuración.

**1.2 SISMEPRE.** Los 7 archivos usan el mismo formato que el SIAF (UTF-8, coma, CRLF). El número de columnas va de 7 a 42 según el archivo, porque cada uno es una tabla distinta del sistema.

**1.3 RENAMU.** El formato **cambia con los años**:
- Hasta 2021 viene en **ISO-8859-1** (latin1), separado por `;`.
- Desde 2022 viene en **UTF-8 con BOM**, separado por `;`.
- El F02 de 2025 (centros poblados) es una excepción: usa coma.

Si se lee todo con UTF-8, las tildes y la ñ de las ediciones antiguas salen dañadas. Por eso **cada edición se lee con su propio encoding** (`src/perfilado.detectar_formato`).

### 2. F1 SIAF

**2.1 Columnas.** Las 36 columnas son las mismas y están en el mismo orden en los 18 años: no hay columnas nuevas ni renombradas. La estructura es estable de 2009 a 2026, así que un único proceso sirve para todos los años.

**2.2 Métricas por año.** Son tres observaciones:

- **2009–2011 tienen casi el doble de filas que el resto** (1,2–1,3 millones frente a 0,66–0,88 millones). La causa está en el gráfico de la derecha:
  - En 2009–2011 hay ~50 filas por ejecutora y mes; desde 2012, ~28.
  - En 2009–2011 el **PIA viene repartido en los 12 meses** (solo ~8 % en enero). **Desde 2012 el PIA está 100 % en enero**, y el PIM se registra como modificaciones mensuales.
  - Es decir, cambió la forma de registrar el presupuesto, no faltan ni sobran datos. Además, en esos años el 30 % de las filas tiene todos los montos en cero, frente al 6–20 % después.

  > **Sugerencia:** el PIA y el PIM se analizan **anuales** (suma de meses). Sumar los meses da el monto anual correcto en todos los años. No se debe comparar un "PIA de enero" de 2011 con uno de 2015.

- **Recaudado negativo:** hay entre 3 000 y 8 000 filas por año, que suman entre −S/ 99 y −S/ 1 045 millones. Son devoluciones y extornos.
  > **Sugerencia:** se conservan, porque el recaudado neto los incluye, y se miden con una regla de calidad.

- **El recaudado supera al PIM** en 2023–2025 (106–107 %). En el SIAF eso es posible: se recauda más de lo que se presupuestó. 2026 está en 91 % porque el año no ha terminado.
  > **Sugerencia:** el indicador "recaudado / PIM" es un buen KPI para Gold, pero 2026 debe marcarse como año parcial.

- **2026 llega hasta noviembre** (`mes_max = 11`), consistente con un año en curso.

**2.3 Perfil de columnas.** La columna `contenido` dice qué trae cada columna: *números* (montos o códigos), *texto* (nombres) o *mixto*.
- **Montos:** son 100 % *números*, sin ningún valor que no se pueda convertir.
- **Códigos:** casi todos son *números* (`SEC_EJEC`, `RUBRO`, `GENERICA`, …). `TIPO_RECURSO` es *mixto*: algunos códigos traen letras, así que en Silver se trata como texto.
- **`SECTOR` y `PLIEGO`:** están vacíos en el 84 % de las filas. La tabla siguiente muestra que **son exactamente las filas del nivel M**: en Gobierno Local el SIAF no usa sector ni pliego. No es un error, pero estas columnas no sirven para municipalidades.
- **Ubicación vacía:** hay 1 644 filas con el departamento, la provincia y el distrito en blanco. No son municipalidades: son ejecutoras nacionales y regionales, y 26 filas de mancomunidades en 2012. *Esto corrige una lectura anterior, que las interpretó como "códigos de un dígito".*
- **Niveles de gobierno:** hay tres, **E (nacional) 6 %, R (regional) 10 % y M (local) 84 %**. Filtrar Gobierno Local reduce poco el volumen.

**2.4 Ejecutoras del nivel M.**
- **Composición:** el nivel M tiene 1 639–1 696 municipalidades distritales, 194–195 provinciales y 1 metropolitana (Lima).
- **Mancomunidades municipales:** desde 2012 aparecen entre 19 y 49 por año. No son municipalidades.
  > **Sugerencia:** excluirlas de Silver y contarlas. No pertenecen a ningún UBIGEO de municipalidad.
- **`SEC_EJEC`:** **nunca cambia de UBIGEO dentro de un año**, y ningún UBIGEO tiene dos municipalidades. Es un código confiable.
- **Nombres:** cambian en 0 a 3 casos por año (correcciones de nombre). Se tomará el nombre más reciente.
- **Distritos nuevos:** el número de municipalidades crece con los años (1 834 → 1 892).

**2.5 Duplicados.**
- **Duplicados exactos:** no hay.
- **Llave de negocio:** hay **291 filas repetidas** (año, mes, ejecutora, fuente, rubro, tipo de recurso y clasificador), el 0,002 %. Son registros partidos de la misma partida.
  > **Sugerencia:** consolidarlas en Silver **sumando los montos**.

### 3. F2 SISMEPRE

**3.1 Archivos.** El SISMEPRE son 7 tablas de un mismo sistema, y no todas sirven:

| Archivo | Qué es | Uso propuesto |
| --- | --- | --- |
| `entidad_estado` | Municipalidad × año × periodo: estado de la meta y **CLASIFICACION A–G** | **Sí**: clasificación |
| `esat_estadistica_atm` | Estadística del predial por municipalidad (emisión, base imponible, recaudación, contribuyentes, predios) | **Sí**: montos del predial |
| `respuestas` | Respuesta de cada municipalidad a cada pregunta del formulario | Probablemente no |
| `ano_aplicacion`, `estadistica`, `formulario`, `preguntas` | Catálogos (periodos, formularios, preguntas) | No: referencia |

- **Filas mal formadas:** hay **9 en `rentas_respuestas.csv`**, por comillas sin escapar en los textos libres.
- **Datos personales:** `entidad_estado` trae `CORREO` y `USUARIO_ENVIO_ID`. **No pasan a Silver**.
- **Formatos:** las fechas vienen como `d/MM/yyyy HH:mm:ss`, y los vacíos son un espacio `' '`.

**3.2 Llaves.** Cada archivo tiene una llave (la combinación mínima de columnas que identifica la fila) y **ninguno tiene duplicados** por su llave. Por ejemplo, `entidad_estado` = SEC_EJEC + año + periodo.

**3.3 Conexión.**
- **Todos** los archivos tienen `ANO_APLICACION + PERIODO`.
- **Por dentro**, los catálogos se unen por `FORMULARIO_ID` y `PREGUNTA_ID`, y todas las uniones encuentran el 100 %.
- **Hacia afuera**, `entidad_estado`, `esat_estadistica_atm` y `respuestas` traen `SEC_EJEC` (→ SIAF). `esat_estadistica_atm` trae además `UBIGEO` (→ RENAMU).

**3.4 Clasificación A–G.**
- **Origen:** la columna `CLASIFICACION` de `rentas_entidad_estado.csv`. Es la *Clasificación de Municipalidades del Programa de Incentivos* del MEF.
- **Fuente oficial:** *Marco Conceptual del PI* (MEF, DGPP, dic. 2018, p. 27–28, <https://www.mef.gob.pe/contenidos/presu_publ/migl/pi/marco_conceptual_PI.pdf>):
  - A = provinciales de ciudades principales (74);
  - B = provinciales no pertenecientes a ciudades principales (122);
  - C = distritales de Lima Metropolitana (42);
  - D = distritales de otras ciudades principales (129);
  - E = distritales no principales con ≥ 60 % de población urbana (378);
  - F = distritales no principales con 30–60 % urbana (509);
  - G = distritales no principales con < 30 % urbana (620).
- **Conteos del SISMEPRE:** en 2019 coinciden con los oficiales en A–E.
- **Estabilidad:** desde 2019 **ninguna municipalidad cambia de tipo**.
- **F y G** aparecen en el SISMEPRE **desde 2024**, cuando esas municipalidades entraron a la meta del predial.
- **Esquema anterior:** en 2013–2018 la columna trae otra clasificación (A, B y C, con otro significado).
  > **Sugerencia:** usar la clasificación de 2019 en adelante como atributo fijo de la municipalidad. Una municipalidad que nunca aparece en el SISMEPRE queda "sin clasificación PI" (D-008).

### 4. F3 RENAMU

**4.1 Inventario y gráficos.** Los tres gráficos muestran por qué el análisis se centra en **2020–2026**:

1. **Archivos por edición:**
   - Hasta 2017, cada edición viene partida en **~100–116 CSV** (uno por cuadro).
   - En 2018–2020 viene en 19–35 CSV.
   - **Desde 2021, en un solo CSV** con una fila por municipalidad.
2. **Columnas comunes con 2022:** son menos del 33 % hasta 2018 y el 66 % en 2019. **Desde 2020 superan el 94 %.** Las preguntas antiguas tienen otros códigos y no se pueden comparar directamente.
3. **Tabla de ingresos con el predial:** aparece en casi todas las ediciones (faltan 2013, 2014 y 2016), pero **con un código distinto en cada una** (P103, P113, P118, C115, C119, C100 y, desde 2020, C96).

> **Escenario propuesto:**
> - Usar **2020–2026** en Silver: un formato estable, una fila por municipalidad y la tabla de ingresos C96 en todas las ediciones.
> - **Dejar 2009–2019 atrás, como posible escenario.** Solo valdría la pena recuperar su tabla de ingresos (mapeando los códigos por descripción) si se quiere una serie larga de "ingresos declarados vs. SIAF".
> - Bronze los conserva igual.

**4.2 Ediciones 2020–2026.**
- **UBIGEO:** es **único por municipalidad** en todas las ediciones. En 2020 no hay columna `Ubigeo` y se arma con `ccdd + ccpp + ccdi`.
- **2020:** está repartido en 19 módulos que se unen por ubicación. Dos de ellos traen **filas completamente vacías**: 5 en `C08` y 3 en `C01` (`filas_vacias` = 8). Por eso 4.1 muestra 1 879 filas y 4.2 muestra 1 874 municipalidades. **No son duplicados.**
  > **Sugerencia:** enviarlas a cuarentena.
- **`Tipomuni`:** 1 = provincial (196), 2 = distrital (1 678 → 1 696). Es el atributo `tipo_municipalidad`.
- **Tabla de ingresos C96:** está en todas las ediciones, con 57 columnas (64 en 2026). **El dato corresponde al año anterior a la edición**: el RENAMU 2026 informa los ingresos de 2025.
- **2026:** tiene **1 397 columnas y 1 892 municipalidades**, las mismas que el SIAF de 2025 y 2026.

### 5. Conexión de prueba entre las fuentes

| Prueba | Resultado |
| --- | --- |
| SIAF ↔ RENAMU por UBIGEO (mismo año) | **99,15–100 %**. Faltan 16 municipalidades en 2021–2022 y 1 en 2025: distritos creados después de la edición del RENAMU |
| SIAF ↔ SISMEPRE por SEC_EJEC (2019–2026, por año) | **100 %** de las municipalidades del SISMEPRE existen en el SIAF todos los años (`solo_SISMEPRE` = 0). El SISMEPRE cubre solo a las que tienen meta del predial: 745 (2019–2022) → 1 354 (2026) |
| Puente SEC_EJEC → UBIGEO (ESAT) | Coincide con el SIAF en el **100 %** de los pares de cada año. **2020 no tiene datos en el ESAT** |

---

## Conexión más probable entre las fuentes (para analizar en Silver)

```
                 SIAF (siaf_ingreso)                       SISMEPRE
      ┌───────────────────────────────────┐      ┌────────────────────────────┐
      │ anio, mes, SEC_EJEC, UBIGEO*,     │      │ entidad_estado             │
      │ fuente, rubro, clasificador,      │      │  SEC_EJEC + año + periodo  │
      │ PIA, PIM, recaudado               │      │  → CLASIFICACION (A–G)     │
      └──────────────┬────────────────────┘      │ esat / respuestas          │
                     │ SEC_EJEC ─────────────────┤  SEC_EJEC + año + periodo  │
                     │                           └────────────────────────────┘
                     │ UBIGEO + año
                     ▼
      ┌───────────────────────────────────┐
      │ RENAMU (edición = año)            │
      │ UBIGEO → Tipomuni, ingresos C96   │
      │ (C96 de la edición N = año N−1)   │
      └───────────────────────────────────┘
 * UBIGEO del SIAF = lpad(DEPARTAMENTO,2) + lpad(PROVINCIA,2) + lpad(DISTRITO,2) de la ejecutora
```

- **Municipalidad = `UBIGEO`.** Es la llave común. El SIAF la trae en la ejecutora; el RENAMU, directamente.
- **`SEC_EJEC`** es el código del MEF que comparten el SIAF y el SISMEPRE. Con el **puente `SEC_EJEC` ↔ `UBIGEO`** (armado desde el SIAF y validado con el ESAT) todo se cruza por UBIGEO.
- **Tiempo:**
  - SIAF: `ANO_DOC` y `MES_DOC`.
  - SISMEPRE: `ANO_APLICACION` y `PERIODO`.
  - RENAMU: la edición, pero sus ingresos C96 corresponden al año anterior.
- **Lo que hay que resolver en Silver:**
  - Excluir las mancomunidades.
  - Marcar como "No especificado" los distritos nuevos que no están en el RENAMU.
  - Unir los 19 módulos de 2020.
  - Asignar la clasificación A–G y "F/G (sin meta predial)" a las municipalidades sin meta.

---

## Anexo: información recolectada fuera de los notebooks

Durante la Fase 1 se hicieron consultas exploratorias (peticiones HEAD a los portales, DuckDB sobre los CSV y lectura de los PDF del RENAMU) que **no están en los notebooks**. Sus resultados se registran aquí para que quien continúe no tenga que repetirlas. Los scripts eran temporales y no forman parte del repositorio.

### A. Portales y URLs (2026-11-20)

| Tema | Resultado |
| --- | --- |
| Portal de datos abiertos del MEF | Es una aplicación Angular. Los archivos se bajan directo de `https://fs.datosabiertos.mef.gob.pe/datastorefiles/<archivo>`. La metadata de cada dataset solo sale por una API interna del portal, que no se usó |
| Diccionarios del SIAF y del SISMEPRE | Dan **HTTP 404** con los nombres supuestos: `Ingresos_Diccionario.csv`, `Ingreso_Diccionario.csv`, `Diccionario_Ingreso.csv` y `rentas_<tabla>_diccionario.csv` (los 7). Hay que bajarlos a mano desde la página del dataset (P-003) |
| SIAF 2007 y 2008 | También existen (`2007-Ingreso.csv`, 342 MB; `2008-Ingreso.csv`, 436 MB). No se descargaron porque el alcance empieza en 2009 |
| SIAF 2025 y 2026 anual | No existen (`<año>-Ingreso.csv` da 404): solo se publican *Mensual* y *Diario* |
| `Last-Modified` del SIAF | Los anuales 2009–2024 se republicaron el 21 y 22-oct-2026. El *Diario* se actualiza todos los días; el *Mensual* 2026 es del 22-oct |
| Velocidad de descarga | ~36 MB/s desde `fs.datosabiertos.mef.gob.pe` (todo Bronze baja en unos 3 minutos) |
| RENAMU 2009–2024 | `https://www.inei.gob.pe/media/DATOS_ABIERTOS/RENAMU/DATA/<año>.zip`. Para 2025 y 2026 esa ruta da 404 |
| RENAMU 2025 | `proyectos.inei.gob.pe/iinei/srienaho/descarga/CSV/984-Modulo1963.zip` es el **F01** (municipalidades) y `985-Modulo1964.zip` es el **F02** (centros poblados) |
| RENAMU 2026 | `…/CSV/1049-Modulo1963.zip` (lo agregó el usuario) |
| `CategoriasMunicipalidades.csv` | No existe en ningún portal público. Lo más parecido es la *Clasificación de Municipalidades del Programa de Incentivos* (tipos A–G), que el MEF publica solo como anexo PDF de cada decreto supremo. Por eso se reemplaza con `CLASIFICACION` del SISMEPRE (D-008) |

### B. SIAF: auditoría Diario vs. Mensual (archivos completos comparados con DuckDB)

| Año | Filas Mensual | Filas Diario | Solo en el Mensual | Solo en el Diario | Recaudado municipal |
| --- | --- | --- | --- | --- | --- |
| 2025 | 878 731 | 878 733 | 0 | 2 | Idéntico, mes a mes |
| 2026 | 655 508 | 793 830 | 13 105 (montos corregidos después) | 151 427 | El Diario tiene +S/ 5 974 millones (julio 835, agosto 499, septiembre 1 402, octubre 2 696 y noviembre 542) |

Los dos archivos tienen las mismas 36 columnas y el mismo grano mensual.

### C. Evaluación de almacenamiento (escenarios considerados antes de descargar)

| Escenario | Bronze | Total estimado (con Silver, Gold y temporales de Spark) |
| --- | --- | --- |
| **A (elegido):** SIAF 2009–2026 + SISMEPRE + RENAMU (análisis desde 2020) | ~7,4 GB | ~10 GB |
| B: además, RENAMU 2009–2024 unificado | ~7,6 GB | ~11 GB |
| C: solo 2018–2023 | ~2,3 GB | ~4 GB |

Notas:
- Hay unos 943 GB libres en el disco, así que el almacenamiento no limita.
- En una muestra de 2024 y 2009, Parquet comprime el SIAF unas 32 veces frente al CSV. Para estimar se usó un rango conservador de 10× a 30×.

### D. RENAMU: detalles útiles para el perfilado y para Silver

- **Estructura de 2020:** 19 módulos, todos con `idmunici, ccdd, ccpp, ccdi, Departamento, Provincia, Distrito, Tipomuni`.
  - `CDIR.csv` es el **directorio**: trae nombres, correos y teléfonos de autoridades (**datos personales**).
  - `C01.csv` tiene la identificación.
  - `C04.csv` tiene la **tabla de ingresos C96** (95 columnas).
  - En 2020, `idmunici` **no** es igual al UBIGEO; desde 2021 sí lo es.
- **Diccionarios PDF:** al extraer el texto, **los códigos y las descripciones salen desordenados**, así que no se pueden emparejar automáticamente. Para etiquetar las variables C96 hay que mapear a mano las principales.
  - Lo confirmado en 2022: `C96` = total de ingresos, `C96_1` = ingresos corrientes, `C96_1_1` = impuestos y contribuciones, `C96_1_1_1` = **Predial**, `C96_1_1_2` = Alcabala…
- **Tabla de ingresos en las ediciones históricas:** el código del predial que se encontró en cada una es:

  | Edición | Código | Edición | Código |
  | --- | --- | --- | --- |
  | 2009–2011 | P103_04 | 2017 | C115_1_1_1 |
  | 2012 | P113_04 | 2018 | C119_1_1_1 |
  | 2015 | P118_1_1_1 | 2019 | C100_1_1_1 |

  No se encontró en 2013, 2014 ni 2016. Desde 2017 el diccionario dice explícitamente que el dato corresponde al año anterior.
- **Otros temas con variables útiles** (todas las ediciones): catastro (último levantamiento o actualización), personal del área tributaria, área de ejecución coactiva, sistemas de recaudación (SRTM) y modalidades de pago de tributos. Los códigos cambian en cada edición antes de 2020.
- **El F02 de 2025** (centros poblados) trae `catmuni` (categoría del centro poblado). No es la categoría de la municipalidad distrital o provincial.

### E. SISMEPRE: formatos y valores observados

- **Fechas:** `d/MM/yyyy HH:mm:ss` (por ejemplo `31/12/2019 00:00:00`). Los valores vacíos vienen como un espacio `' '`.
- **`entidad_estado`:**
  - `ESTADO` es siempre `A`, `ORIGEN_INFORMACION` es siempre `1` y `IND_RESOL_ALCAL_ADJUNTO` vale `P` o `A`.
  - `TIPO_META` toma los valores 0, 2, 18, 22, 23, 27, 31 y 39; 2 es el más frecuente.
  - `CLASIFICACION`: en 2013–2018, A y B (y C en 2017–2018) con otro significado; desde 2019, A–G.
- **`esat_estadistica_atm`:** los montos `MON_*` son 100 % numéricos. Las banderas `FLAG_EMILIQUIDA` y `FLAG_EMISION_INICIAL` valen `S`, `N` o vacío.
- **`respuestas`:** `RESPUESTA_DECIMAL` y `RESPUESTA_ENTERO` son 100 % numéricos. Hay respuestas de texto libre largas, y en ellas están las comillas sin escapar que dañan 9 filas.

### F. Herramientas

- **DuckDB** (ya instalado en el `.venv`) recorre los 15 millones de filas del SIAF en unos 8 segundos. Sirve para explorar rápido.
- **Spark** es la herramienta oficial del pipeline: el perfilado completo tarda unos 4 minutos.
- **PDF:** los diccionarios del RENAMU se leen con `pypdf` (en `requirements.txt`).
