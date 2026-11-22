"""Funciones del perfilado de Bronze (02_bronze_perfilado).

Principio: perfilar sin transformar. Todo se lee como texto (sin inferir tipos).
Privacidad: el perfil de columnas nunca publica valores de texto (solo conteos y
longitudes); min/max solo se calculan para columnas numéricas. Así no se filtran
correos, teléfonos ni nombres de personas presentes en algunas fuentes.
"""

from __future__ import annotations

import codecs
import csv
from pathlib import Path
from typing import Any

import pandas as pd
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

DELIMITADORES = [",", ";", "|", "\t"]
RE_NUMERO = r"^-?\d+(\.\d+)?$"


# --------------------------------------------------------------------------- formato
def detectar_formato(p: Path, muestra: int = 1_000_000) -> dict[str, Any]:
    """Encoding, BOM, delimitador, salto de línea y n° de columnas del encabezado."""
    with p.open("rb") as f:
        b = f.read(muestra)
    bom = b.startswith(codecs.BOM_UTF8)
    cuerpo = b[3:] if bom else b
    corte = cuerpo.rfind(b"\n")
    try:
        (cuerpo[:corte] if corte > 0 else cuerpo).decode("utf-8")
        encoding = "UTF-8"
    except UnicodeDecodeError:
        encoding = "ISO-8859-1"
    texto = cuerpo.decode("utf-8" if encoding == "UTF-8" else "latin-1", errors="replace")
    encabezado = texto.split("\n", 1)[0].rstrip("\r")
    sep = max(DELIMITADORES, key=encabezado.count)
    columnas = next(csv.reader([encabezado], delimiter=sep))
    return {
        "encoding": encoding,
        "bom": bom,
        "delimitador": {"\t": "TAB"}.get(sep, sep),
        "salto_linea": "CRLF" if b"\r\n" in b[:100_000] else "LF",
        "comillas": '"' in encabezado,
        "n_columnas": len(columnas),
        "columnas": [c.strip().lstrip("﻿") for c in columnas],
    }


# --------------------------------------------------------------------------- lectura
def leer_csv(spark: SparkSession, rutas: list[str] | str, fmt: dict[str, Any],
             corrupto: bool = False) -> DataFrame:
    """Lee CSV como texto con el formato detectado. Limpia el BOM del primer encabezado."""
    sep = "\t" if fmt["delimitador"] == "TAB" else fmt["delimitador"]
    r = (spark.read.option("header", True).option("inferSchema", False)
         .option("sep", sep).option("encoding", fmt["encoding"])
         .option("quote", '"').option("escape", '"').option("multiLine", False))
    if corrupto:
        r = r.option("mode", "PERMISSIVE").option("columnNameOfCorruptRecord", "_corrupt_record")
    if corrupto:
        # el esquema explícito permite capturar la fila corrupta completa
        from pyspark.sql.types import StringType, StructField, StructType
        campos = [StructField(c, StringType()) for c in fmt["columnas"]] + [StructField("_corrupt_record", StringType())]
        r = r.schema(StructType(campos))
    df = r.csv(rutas)
    return df.toDF(*[c.lstrip("﻿").strip() for c in df.columns])


def a_pandas(df: DataFrame) -> pd.DataFrame:
    """collect() -> pandas sin Arrow (PySpark 4.3 + pandas 3 no son 100 % compatibles)."""
    filas = df.collect()
    return pd.DataFrame([r.asDict() for r in filas], columns=df.columns)


# --------------------------------------------------------------------------- perfil de columnas
def perfil_columnas(df: DataFrame, fuente: str, tabla: str) -> pd.DataFrame:
    """Una pasada sobre el DataFrame: nulos, vacíos, distintos (aprox.), longitudes y qué contiene
    cada columna: `números` (todos los valores con dato son numéricos: montos o códigos),
    `texto` (nombres u otros textos) o `mixto` (parte números, parte texto)."""
    exprs = [F.count(F.lit(1)).alias("__filas")]
    for c in df.columns:
        col = F.col(f"`{c}`")
        vacio = col.isNull() | (F.trim(col) == "")
        num = F.regexp_replace(F.trim(col), ",", "")
        exprs += [
            F.sum(col.isNull().cast("long")).alias(f"{c}__nulos"),
            F.sum((~col.isNull() & (F.trim(col) == "")).cast("long")).alias(f"{c}__vacios"),
            F.approx_count_distinct(col, 0.02).alias(f"{c}__distintos"),
            F.min(F.length(col)).alias(f"{c}__lmin"),
            F.max(F.length(col)).alias(f"{c}__lmax"),
            F.sum((~vacio & ~num.rlike(RE_NUMERO)).cast("long")).alias(f"{c}__texto"),
        ]
    r = df.agg(*exprs).first().asDict()
    n = r["__filas"]
    filas = []
    for c in df.columns:
        con_dato = n - r[f"{c}__nulos"] - r[f"{c}__vacios"]
        texto = r[f"{c}__texto"]
        contenido = ("vacía" if con_dato == 0 else "números" if texto == 0
                     else "texto" if texto == con_dato else f"mixto ({texto:,} con texto)")
        filas.append({
            "fuente": fuente, "tabla": tabla, "columna": c, "filas": n,
            "nulos": r[f"{c}__nulos"], "vacios": r[f"{c}__vacios"],
            "pct_nulo_o_vacio": round(100 * (n - con_dato) / n, 2) if n else None,
            "distintos_aprox": r[f"{c}__distintos"],
            "largo_min": r[f"{c}__lmin"], "largo_max": r[f"{c}__lmax"],
            "contenido": contenido,
        })
    return pd.DataFrame(filas)


# --------------------------------------------------------------------------- utilidades
def tabla_md(df: pd.DataFrame, max_filas: int = 60) -> str:
    """DataFrame -> tabla Markdown (sin depender de 'tabulate')."""
    d = df.head(max_filas)
    def fmt(v):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return ""
        if isinstance(v, float):
            return f"{v:,.2f}" if abs(v) < 1e15 else f"{v:.3e}"
        if isinstance(v, int):
            return f"{v:,}"
        return str(v).replace("|", "\\|")
    lineas = ["| " + " | ".join(map(str, d.columns)) + " |", "| " + " | ".join("---" for _ in d.columns) + " |"]
    lineas += ["| " + " | ".join(fmt(v) for v in fila) + " |" for fila in d.itertuples(index=False)]
    if len(df) > max_filas:
        lineas.append(f"\n*… {len(df) - max_filas} filas más.*")
    return "\n".join(lineas)
