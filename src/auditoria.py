"""Bitácoras por capa y consolidado de auditoría (Parquet).

Cada notebook agrega UNA línea a data/<capa>/bitacora_ejecuciones.jsonl. Para que la auditoría
pueda comparar capas, la línea trae un bloque `volumenes` con el mismo formato en todas:

    {"capa": "bronze", "fuente": "F1", "tabla": "siaf_ingreso",
     "archivos": 18, "filas": 15202372, "bytes": 7_721_000_000, "fecha_datos": "2026-11-22", ...}

- capa / fuente / tabla : qué se mide (tabla = carpeta de Bronze o tabla Parquet de Silver/Gold).
- archivos             : archivos (Bronze) o archivos Parquet (Silver/Gold).
- filas                : filas de datos.
- bytes                : tamaño en disco.
- fecha_datos          : fecha (AAAA-MM-DD) de la versión de los datos medidos.
Los campos extra de cada capa (descargados, filas_cuarentena, ...) se conservan.

`construir_auditoria()` lee todas las bitácoras, despliega `volumenes` (una fila por ejecución ×
fuente × tabla), ordena por fecha y capa, y escribe data/auditoria/volumenes.parquet.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.config import raiz_proyecto, ruta

ORDEN_CAPAS = {"bronze": 0, "silver": 1, "gold": 2}
NOMBRE_BITACORA = "bitacora_ejecuciones.jsonl"
CAMPOS_VOLUMEN = ("capa", "fuente", "tabla", "archivos", "filas", "bytes", "fecha_datos")


def tamano_en_disco(p: Path) -> tuple[int, int]:
    """(n° de archivos, bytes) de un archivo o de una carpeta (p. ej. una tabla Parquet)."""
    if p.is_file():
        return 1, p.stat().st_size
    archivos = [f for f in p.rglob("*") if f.is_file() and not f.name.startswith((".", "_"))]
    return len(archivos), sum(f.stat().st_size for f in archivos)


def volumen(capa: str, fuente: str, tabla: str, *, filas: int, archivos: int, bytes: int,
            fecha_datos: str | None, **extra: Any) -> dict[str, Any]:
    """Arma un registro de volumen con el formato común de auditoría."""
    return {"capa": capa, "fuente": fuente, "tabla": tabla, "archivos": int(archivos),
            "filas": int(filas), "bytes": int(bytes), "fecha_datos": fecha_datos, **extra}


def escribir_bitacora(capa: str, registro: dict[str, Any]) -> Path:
    """Agrega una línea a data/<capa>/bitacora_ejecuciones.jsonl."""
    faltan = [c for v in registro.get("volumenes", []) for c in CAMPOS_VOLUMEN if c not in v]
    if faltan:
        raise ValueError(f"volumenes sin los campos comunes: {sorted(set(faltan))}")
    p = ruta(capa) / NOMBRE_BITACORA
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")
    return p


def leer_volumenes() -> pd.DataFrame:
    """Todas las bitácoras → una fila por ejecución × volumen. Ignora líneas sin `volumenes`."""
    filas = []
    for p in sorted((raiz_proyecto() / "data").glob(f"*/{NOMBRE_BITACORA}")):
        for linea in p.read_text(encoding="utf-8").splitlines():
            if not linea.strip():
                continue
            reg = json.loads(linea)
            for v in reg.get("volumenes", []):
                filas.append({"run_id": reg["run_id"], "notebook": reg.get("notebook"),
                              "fin_utc": reg.get("fin_utc"), **v})
    df = pd.DataFrame(filas)
    if df.empty:
        return df
    df["fin_utc"] = pd.to_datetime(df["fin_utc"], utc=True, format="ISO8601")
    df["mb"] = (df["bytes"] / 1e6).round(1)
    df["_orden_capa"] = df["capa"].map(ORDEN_CAPAS).fillna(9)
    df = (df.sort_values(["fin_utc", "_orden_capa", "fuente", "tabla"])
            .drop(columns="_orden_capa").reset_index(drop=True))
    primeras = ["fin_utc", "capa", "fuente", "tabla", "archivos", "filas", "bytes", "mb", "fecha_datos",
                "run_id", "notebook"]
    return df[primeras + [c for c in df.columns if c not in primeras]]


def construir_auditoria() -> pd.DataFrame:
    """Escribe data/auditoria/volumenes.parquet con el historial de volúmenes de todas las capas."""
    df = leer_volumenes()
    destino = ruta("auditoria")
    destino.mkdir(parents=True, exist_ok=True)
    df.to_parquet(destino / "volumenes.parquet", index=False)
    return df


def ultimo_volumen(df: pd.DataFrame) -> pd.DataFrame:
    """Estado actual: la última medición de cada capa × fuente × tabla, en orden Bronze → Gold."""
    if df.empty:
        return df
    u = df.sort_values("fin_utc").groupby(["capa", "fuente", "tabla"], as_index=False).tail(1)
    u = u.assign(_o=u["capa"].map(ORDEN_CAPAS).fillna(9))
    return u.sort_values(["fuente", "_o", "tabla"]).drop(columns="_o").reset_index(drop=True)
