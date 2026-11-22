"""Utilidades de la capa Silver: seguimiento de los pasos de limpieza."""

from __future__ import annotations

import pandas as pd
from IPython.display import display
from pyspark.sql import DataFrame, functions as F

from src.perfilado import a_pandas


def _legible(df: DataFrame, c: str):
    """Texto para mostrar un valor: los double con 2 decimales y sin notación científica."""
    return F.format_number(F.col(c), 2) if df.schema[c].dataType.typeName() == "double" else F.col(c).cast("string")


def aplicar(df: DataFrame, paso: str, nuevas: dict, registro: list, ejemplos: int = 2,
            por: str = "edicion", checkpoint: bool = True) -> DataFrame:
    """Aplica un paso de limpieza ({columna: expresión}) y muestra qué cambió.

    Cuenta los valores que cambian por `por` (edición o año) y columna, los agrega a
    `registro` y muestra hasta `ejemplos` casos de antes → después. Con `checkpoint`
    corta el linaje (localCheckpoint); en tablas grandes conviene False y persistir aparte.
    """
    tmp = df
    for c, expr in nuevas.items():
        tmp = tmp.withColumn(f"__n_{c}", expr)
    cambio = {c: ~F.col(c).eqNullSafe(F.col(f"__n_{c}")) for c in nuevas}
    res = a_pandas(tmp.groupBy(por).agg(*[F.sum(m.cast("int")).alias(c) for c, m in cambio.items()])
                   .orderBy(por)).set_index(por)
    for c in nuevas:
        registro.append({"paso": paso, "columna": c, "valores_cambiados": int(res[c].sum())})
    con_cambio = res.loc[res.sum(axis=1) > 0, res.sum() > 0]
    if con_cambio.empty:
        print(f"{paso}: sin cambios")
    else:
        print(f"{paso}: valores cambiados por {por} y columna")
        display(con_cambio)
        ej = []
        for c in [c for c in nuevas if res[c].sum() > 0][:ejemplos]:
            ej.append(a_pandas(tmp.where(cambio[c]).select(
                por, F.lit(c).alias("columna"),
                F.concat(F.lit("«"), F.col(c).cast("string"), F.lit("»")).alias("antes"),
                F.concat(F.lit("«"), _legible(tmp, f"__n_{c}"), F.lit("»")).alias("después")).limit(1)))
        if ej:
            print("Ejemplos (antes → después):")
            display(pd.concat(ej, ignore_index=True))
    out = tmp
    for c in nuevas:
        out = out.drop(c).withColumnRenamed(f"__n_{c}", c)
    return out.localCheckpoint() if checkpoint else out
