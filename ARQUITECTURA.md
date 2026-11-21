# Arquitectura del proyecto: Presupuesto y Ejecución de Ingresos Municipales (MEF)

> Es la foto **actual** del proyecto: qué se construye, en qué orden y dónde vive cada cosa.
> El detalle de cada decisión está en [`DECISIONES.md`](DECISIONES.md) (resumen en [`DECISIONES_RESUMEN.md`](DECISIONES_RESUMEN.md)).
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
| **Años** | SIAF 2009–2026 (2026 parcial) · SISMEPRE completo (2013–2026) · RENAMU 2020–2026 para el análisis; Bronze guarda 2009–2026 |
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
 Fuentes (MEF, INEI) ──descarga──► BRONZE  CSV crudo, inmutable + manifest.json          Fase 1
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
- Bronze es inmutable: cada descarga va en su carpeta con fecha.
- Nada se corrige a mano: todo se regenera ejecutando los notebooks.
- Ninguna fila se pierde en silencio: lo que falla una regla crítica va a `quarantine/` con su motivo.
- Cada notebook deja su registro en la bitácora de su capa.

## 4. Carpetas

```
Final_BI/
├── ARQUITECTURA.md · README.md · DECISIONES.md · DECISIONES_RESUMEN.md
├── config.yaml                  # configuración única: rutas, años, Spark, fuentes, reglas_calidad (D-009)
├── requirements.txt
├── src/                         # recursos Python reutilizables
│   ├── config.py                #   raíz del proyecto, config.yaml, ruta('bronze')…
│   ├── spark.py                 #   crear_sesion()
│   ├── bronze.py                #   catálogo, descarga trazable, ZIP y manifest
│   └── perfilado.py             #   formato real, lectura CSV sin inferir tipos, perfil de columnas
├── data/
│   ├── 00_prueba_spark.ipynb    # prueba del entorno (Fase 0)
│   ├── _muestras/               # CSV sintético de prueba
│   ├── bronze/                  # Fase 1
│   │   ├── 01_bronze_descarga.ipynb · 02_bronze_perfilado.ipynb · bronze.md
│   │   ├── manifest.json        #   inventario: URL, fecha, tamaño, sha256, filas
│   │   ├── bitacora_ejecuciones.jsonl
│   │   └── siaf_ingreso/ · sismepre_predial/ · renamu/   (<AAAA-MM-DD>/…)
│   ├── silver/                  # Fase 2: notebooks 03–05, silver.md, bitácora y tablas Parquet
│   ├── gold/                    # Fase 3: notebooks 06–07, gold.md, bitácora y tablas Parquet
│   ├── quarantine/              # filas rechazadas por reglas críticas (Parquet, con motivo)
│   └── auditoria/               # consolidado de bitácoras y calidad Bronze → Gold (Parquet)
└── consumo/                     # Fases 4–5: leen solo de Gold
    ├── powerbi/ · streamlit/ · modelo/
```

**Convención:** cada capa tiene sus notebooks, **un `.md` que interpreta esos notebooks en el mismo orden** y su bitácora. Los notebooks no escriben CSV ni `.md` sueltos: el notebook ejecutado es la evidencia (D-012).

## 5. Fases

| Fase | Notebooks | Estado | Cierre |
| --- | --- | --- | --- |
| 0 Preparación | `data/00_prueba_spark` | ✅ | Spark crea su sesión, lee un CSV y escribe y lee Parquet |
| 1 Bronze | `01_bronze_descarga`, `02_bronze_perfilado` | ✅ | 3 fuentes en el manifest con hash y filas; llave confirmada |
| 2 Silver | `03_silver_siaf`, `04_silver_sismepre`, `05_silver_municipalidad` *(propuesta)* | ⏳ siguiente | Silver + cuarentena = Bronze filtrado; reglas críticas en OK |
| 3 Gold | `06_gold_dimensiones`, `07_gold_hechos` *(propuesta)* | — | Los totales cuadran con Silver; ningún hecho queda sin dimensión |
| 4 Consumo | Power BI (6 dashboards), Streamlit opcional | — | Los dashboards no transforman datos |
| 5 Modelo | opcional | — | Lee solo de Gold |
| Transversal | `08_auditoria` *(propuesta)*, `00_orquestador` | — | Parquet de auditoría con todas las ejecuciones y reglas |

## 6. Cómo trabajar

1. Una fase a la vez. Al terminarla, se resume y se espera la confirmación antes de seguir.
2. Perfilar antes de transformar: no asumir columnas, tipos ni llaves.
3. Cada capa escribe solo en su carpeta.
4. Los cambios a esta guía se aplican aquí y se registran en `DECISIONES.md`.
5. Preguntar antes de decisiones irreversibles o de alcance.
