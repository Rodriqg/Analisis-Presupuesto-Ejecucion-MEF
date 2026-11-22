# Presupuesto y Ejecución de Ingresos Municipales (MEF)

Examen final de BI. Es un pipeline con **arquitectura Medallion** (Bronze → Silver → Gold) en **PySpark local + Jupyter**, sobre la ejecución de ingresos de los gobiernos locales del Perú. Termina en 6 dashboards de Power BI y un control de calidad de datos documentado.

- Diseño, fases y reglas del proyecto: [`ARQUITECTURA.md`](ARQUITECTURA.md)
- Interpretación de cada capa: `data/<capa>/<capa>.md`, junto a sus notebooks

## Requisitos

| Componente | Versión probada | Nota |
| --- | --- | --- |
| Python | 3.14 | dentro de `.venv/` |
| Java | OpenJDK 21 | PySpark 4.x exige Java 17 o 21 |
| PySpark | 4.3.0 | modo `local[*]` |
| RAM | ~8 GB | Spark usa 4 GB para el driver (`config.yaml`) |
| Disco | ≥ 15 GB libres | cada archivo anual del SIAF pesa entre 300 y 580 MB |

## Instalación

```bash
# 1. Java (Ubuntu/WSL)
sudo apt install openjdk-21-jdk

# 2. Entorno de Python
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 3. Registrar el kernel de Jupyter que usan los notebooks
.venv/bin/python -m ipykernel install --user --name final-bi --display-name "Python (Final BI)"
```

## Verificar el entorno (Fase 0)

Abre `data/00_prueba_spark.ipynb` con el kernel **Python (Final BI)** y ejecuta todas las celdas. El notebook crea una sesión de Spark, lee un CSV pequeño y escribe y lee Parquet.

## Estructura

```
config.yaml   configuración única: rutas, años, Spark, fuentes (URLs) y reglas de calidad
src/          recursos Python reutilizables (config, spark, bronze, perfilado, silver, renamu, auditoria)
data/         una carpeta por capa con sus notebooks, su .md y su bitácora:
              bronze/ (CSV crudo, última versión) · silver/ · gold/ (Parquet) · quarantine/ · auditoria/
consumo/      Power BI, Streamlit y modelo (leen solo de Gold)
.spark_tmp/   archivos temporales de Spark (no se versiona; en WSL /tmp está en memoria)
```

### Notebooks (en orden de ejecución)

| Capa | Notebook | Qué hace | Salida |
| --- | --- | --- | --- |
| — | `data/00_prueba_spark.ipynb` | Prueba del entorno | — |
| Bronze | `data/bronze/01_bronze_descarga.ipynb` | Descarga las 3 fuentes; solo sobrescribe si el servidor publicó una versión nueva | `data/bronze/<fuente>/` + `manifest.json` |
| Bronze | `data/bronze/02_bronze_perfilado.ipynb` | Exploración de los CSV (no modifica datos) | — |
| Silver | `data/silver/03_siaf.ipynb` | SIAF: municipalidades del nivel M, limpieza y cuadre | `data/silver/siaf_ingreso/` (12,7 millones de filas) |
| Silver | `data/silver/05a_silver_renamu_mapeo.ipynb` | RENAMU: selección de variables y códigos por edición | `data/silver/renamu_mapeo.yaml` |
| Silver | `data/silver/05b_silver_renamu.ipynb` | RENAMU: finanzas municipales, limpieza y cuadre | `data/silver/renamu_finanzas/` (29 841 filas) |

Cada notebook que descarga o transforma datos escribe una línea en la bitácora de su capa, y la auditoría las junta en `data/auditoria/volumenes.parquet` (filas, tamaño y fecha de los datos por capa y fuente).

Uso de `src/` desde un notebook:

```python
import sys
from pathlib import Path
RAIZ = next(p for p in (Path.cwd(), *Path.cwd().parents) if (p / "ARQUITECTURA.md").exists())
sys.path.insert(0, str(RAIZ))

from src.config import cargar_config, cargar_fuentes, ruta
from src.spark import crear_sesion

spark = crear_sesion()
```

## Estado

| Fase | Estado |
| --- | --- |
| 0 — Preparación | ✅ Cerrada (2026-11-20) |
| 1 — Bronze: descarga y perfilado | ✅ Cerrada · `data/bronze/` (sobrescritura validada y bitácora por fuente, 2026-11-22) |
| 2 — Silver | 🔄 SIAF ✅ · RENAMU ✅ · SISMEPRE pendiente (`data/silver/`) |
| 3 — Gold | 🔄 Boceto del modelo estrella en `data/gold/gold.md`; las métricas se definen después |
| 4 — Consumo (Power BI) | — |
| 5 — Modelo predictivo (opcional) | — |

## Reglas de trabajo

- Los datos solo fluyen hacia abajo: Bronze → Silver → Gold.
- Bronze guarda la última versión de cada fuente: si el servidor publica una nueva, se valida y sobrescribe la anterior; nunca se edita su contenido (D-014).
- Nada se corrige a mano: todo se regenera ejecutando los notebooks.
- Las filas que fallan una regla crítica van a `data/quarantine/` con su motivo.
