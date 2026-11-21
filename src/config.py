"""Ubicación de la raíz del proyecto y lectura de config.yaml (archivo único en la raíz, D-009)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

MARCADOR_RAIZ = "ARQUITECTURA.md"


def raiz_proyecto(desde: Path | None = None) -> Path:
    """Sube desde `desde` (o el directorio actual) hasta encontrar ARQUITECTURA.md."""
    actual = (desde or Path.cwd()).resolve()
    for carpeta in (actual, *actual.parents):
        if (carpeta / MARCADOR_RAIZ).exists():
            return carpeta
    raise FileNotFoundError(
        f"No se encontró {MARCADOR_RAIZ} subiendo desde {actual}. "
        "Abre el notebook dentro del proyecto."
    )


ARCHIVO_CONFIG = "config.yaml"


@lru_cache(maxsize=None)
def cargar_config() -> dict[str, Any]:
    """config.yaml completo. La ruta se puede sobrescribir con la variable de entorno
    FINAL_BI_CONFIG (útil al dockerizar: montar otro config.yaml sin tocar la imagen)."""
    import os
    ruta_cfg = Path(os.environ.get("FINAL_BI_CONFIG", raiz_proyecto() / ARCHIVO_CONFIG))
    with ruta_cfg.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def cargar_fuentes() -> dict[str, Any]:
    return cargar_config()["fuentes"]


def cargar_reglas() -> list[dict[str, Any]]:
    return cargar_config().get("reglas_calidad", [])


def ruta(clave: str) -> Path:
    """Ruta absoluta de una entrada de config.yaml -> rutas (p. ej. ruta('bronze'))."""
    rutas = cargar_config()["rutas"]
    if clave not in rutas:
        raise KeyError(f"'{clave}' no está en config.yaml -> rutas. Disponibles: {sorted(rutas)}")
    return raiz_proyecto() / rutas[clave]
