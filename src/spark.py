"""Creación de la sesión de Spark local a partir de config.yaml (sección spark)."""

from __future__ import annotations

import os
import sys
import warnings

from pyspark.sql import SparkSession

from src.config import cargar_config, raiz_proyecto, ruta


def crear_sesion(app_name: str | None = None) -> SparkSession:
    """Devuelve la sesión de Spark del proyecto (reutiliza la activa si ya existe)."""
    cfg = cargar_config()["spark"]

    # Spark debe usar el mismo Python del kernel (el del .venv) en driver y workers.
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)

    # PySpark 4.3 avisa que pandas 3.x no está soportado del todo; el proyecto no usa
    # la conversión Spark<->pandas en el pipeline, así que se silencia el aviso.
    warnings.filterwarnings("ignore", message=".*does not yet fully support pandas.*")

    warehouse = ruta("auditoria") / "_spark_warehouse"   # Spark lo exige; el proyecto no usa tablas del catálogo

    builder = (
        SparkSession.builder.appName(app_name or cfg["app_name"])
        .master(cfg["master"])
        .config("spark.driver.memory", cfg["driver_memory"])
        .config("spark.sql.shuffle.partitions", str(cfg["shuffle_partitions"]))
        .config("spark.sql.session.timeZone", cfg["timezone"])
        .config("spark.sql.warehouse.dir", str(warehouse))
        # Caché y shuffles en disco: en WSL /tmp es tmpfs (memoria) y no alcanza para el SIAF
        .config("spark.local.dir", str(raiz_proyecto() / ".spark_tmp"))
    )
    for clave, valor in (cfg.get("config_extra") or {}).items():
        builder = builder.config(clave, str(valor))

    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel(cfg.get("log_level", "WARN"))
    return spark
