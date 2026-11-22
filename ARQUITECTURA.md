# Arquitectura del proyecto: Presupuesto y Ejecución de Ingresos Municipales (MEF)

> Es la foto **actual** del proyecto: qué se construye, en qué orden y dónde vive cada cosa.
> La interpretación de los datos está en el `.md` de cada capa (`data/<capa>/<capa>.md`).

---

## 1. Contexto

**Examen final:** análisis para la toma de decisiones del Presupuesto y Ejecución de Ingresos del MEF, enfocado en las municipalidades.

El proyecto debe cubrir:
1. La arquitectura Medallion.
2. Pipelines de ingesta.
3. 6 dashboards de decisión en Power BI.
4. Un control de calidad de datos documentado.

| | |
| --- | --- |
| **Stack** | Jupyter + PySpark 4.3 (local), Python 3.14, Java 21. CSV en Bronze, Parquet desde Silver |
| **Alcance** | Gobierno Local (`NIVEL_GOBIERNO = 'M'`): municipalidades provinciales y distritales |
| **Años** | SIAF 2009–2026 (2026 parcial) · SISMEPRE completo (2013–2026) · RENAMU: solo Finanzas municipales, ediciones 2009–2026 (datos 2009–2025, sin 2014) |
| **Llave de integración** | `UBIGEO` (6 dígitos) + año. `SEC_EJEC` une el SIAF y el SISMEPRE (D-010) |

## 2. Fuentes

| ID | Fuente | Carpeta en Bronze | Notas |
| --- | --- | --- | --- |
| F1 | SIAF: presupuesto y ejecución de ingreso (MEF) | `data/bronze/siaf_ingreso/` | 1 CSV por año; 2025 y 2026 desde el archivo *Diario* (D-005) |
| F2 | SISMEPRE: meta del impuesto predial (MEF) | `data/bronze/sismepre_predial/` | 7 CSV relacionados; incluye la clasificación A–G de municipalidades (D-008) |
| F3 | RENAMU: Registro Nacional de Municipalidades (INEI) | `data/bronze/renamu/` | 1 ZIP por edición, 2009–2026 (D-006, D-011) |
| ~~F4~~ | ~~Categorías de municipalidades~~ | — | Descartada; la categoría se deriva de F2 y F3 (D-008) |

Las URLs están en `config.yaml → fuentes`.

## 3. Flujo Medallion

```
 Fuentes (MEF, INEI) ──descarga──► BRONZE  CSV crudo (última versión) + manifest.json   Fase 1
                                      │ limpieza, tipado, conformado (CSV → Parquet)
                                      ▼
                                   SILVER  Parquet confiable, grano fino ──► quarantine/  Fase 2
                                      │ modelado para decidir
                                      ▼
                                   GOLD    Parquet, modelo estrella                       Fase 3
                                      │
                                      ├──► consumo/ (Power BI, Streamlit, modelo)         Fases 4–5
 Transversal: bitácora por capa ──► auditoria/ (Parquet consolidado Bronze → Gold)
```

**Reglas:**
- El flujo va solo hacia abajo.
- Bronze guarda la **última versión** de cada fuente en una ruta fija (`data/bronze/<fuente>/<archivo>`). Una versión nueva se descarga aparte, se valida y recién entonces sobrescribe la anterior; el contenido nunca se edita (D-014).
- `manifest.json` es el inventario de lo que hay hoy en Bronze (URL, fecha de descarga, `run_id`, tamaño, sha256 y filas).
- Nada se corrige a mano: todo se regenera ejecutando los notebooks.
- Ninguna fila se pierde en silencio: lo que falla una regla crítica va a `quarantine/` con su motivo.
- Cada notebook que descarga, transforma o valida datos deja su registro en la bitácora de su capa (el perfilado es solo exploración, D-015), con un bloque `volumenes` común (capa, fuente, tabla, archivos, filas, bytes, fecha de los datos) que `src/auditoria.py` consolida en `data/auditoria/volumenes.parquet`.

## 4. Carpetas

```
Final_BI/
├── ARQUITECTURA.md · README.md
├── config.yaml                  # configuración única: rutas, años, Spark, fuentes, reglas_calidad (D-009)
├── requirements.txt
├── src/                         # recursos Python reutilizables
│   ├── config.py                #   raíz del proyecto, config.yaml, ruta('bronze')…
│   ├── spark.py                 #   crear_sesion()
│   ├── bronze.py                #   catálogo, descarga trazable, ZIP y manifest
│   ├── perfilado.py             #   formato real, lectura CSV sin inferir tipos, perfil de columnas
│   ├── renamu.py                #   diccionarios PDF del RENAMU como tablas (catálogo de variables)
│   ├── silver.py                #   aplicar(): paso de limpieza con conteo de cambios y ejemplos
│   └── auditoria.py             #   bitácora con bloque `volumenes` y data/auditoria/volumenes.parquet
├── data/
│   ├── 00_prueba_spark.ipynb    # prueba del entorno (Fase 0)
│   ├── _muestras/               # CSV sintético de prueba
│   ├── bronze/                  # Fase 1
│   │   ├── 01_bronze_descarga.ipynb · 02_bronze_perfilado.ipynb · bronze.md
│   │   ├── manifest.json        #   inventario: URL, fecha, tamaño, sha256, filas
│   │   ├── bitacora_ejecuciones.jsonl
│   │   └── siaf_ingreso/ · sismepre_predial/ · renamu/<edición>/   (ruta fija, última versión, D-014)
│   ├── silver/                  # Fase 2
│   │   ├── 03_siaf.ipynb · 05a_silver_renamu_mapeo.ipynb · 05b_silver_renamu.ipynb · silver.md
│   │   ├── renamu_mapeo.yaml    #   códigos del RENAMU por edición (fuente única para 05a y 05b)
│   │   ├── bitacora_ejecuciones.jsonl
│   │   └── siaf_ingreso/ · renamu_finanzas/   (Parquet; 04_sismepre pendiente)
│   ├── gold/                    # Fase 3: gold.md (boceto del modelo estrella); notebooks 06–07 y Parquet pendientes
│   ├── quarantine/              # filas rechazadas por reglas críticas (Parquet, con motivo)
│   └── auditoria/               # volumenes.parquet: filas, tamaño y fecha de los datos por capa y fuente
├── .spark_tmp/                  # temporales de Spark (no se versiona; en WSL /tmp está en memoria)
└── consumo/                     # Fases 4–5: leen solo de Gold
    ├── powerbi/ · streamlit/ · modelo/
```

**Convención:** cada capa tiene sus notebooks, **un `.md` que interpreta esos notebooks en el mismo orden** y su bitácora. Los notebooks no escriben CSV ni `.md` sueltos: el notebook ejecutado es la evidencia (D-012).

## 5. Fases

| Fase | Notebooks | Estado | Cierre |
| --- | --- | --- | --- |
| 0 Preparación | `data/00_prueba_spark` | ✅ | Spark crea su sesión, lee un CSV y escribe y lee Parquet |
| 1 Bronze | `01_bronze_descarga`, `02_bronze_perfilado` | ✅ | 3 fuentes en el manifest con hash y filas; sobrescritura validada; el perfilado es solo exploración (D-014, D-015) |
| 2 Silver | `03_siaf` ✅ · `05a_silver_renamu_mapeo` ✅ · `05b_silver_renamu` ✅ · `04_silver_sismepre` | 🔄 falta SISMEPRE | Silver + cuarentena + fuera de alcance = Bronze; reglas críticas en OK |
| 3 Gold | `06_gold_dimensiones`, `07_gold_hechos` *(propuesta)* | 🔄 boceto del modelo estrella (`gold.md`) | Los totales cuadran con Silver; ningún hecho queda sin dimensión |
| 4 Consumo | Power BI (6 dashboards), Streamlit opcional | — | Los dashboards no transforman datos |
| 5 Modelo | opcional | — | Lee solo de Gold |
| Transversal | `src/auditoria.py` ✅ · `00_orquestador` *(propuesta; Airflow como opción)* | 🔄 | `data/auditoria/volumenes.parquet` con los volúmenes de cada ejecución; falta el mini-modelo de calidad (`gold.md` §3b) |

## 6. Cómo trabajar

1. Una fase a la vez. Al terminarla, se resume y se espera la confirmación antes de seguir.
2. Perfilar antes de transformar: no asumir columnas, tipos ni llaves.
3. Cada capa escribe solo en su carpeta.
4. Preguntar antes de decisiones irreversibles o de alcance.
