"""Funciones de la capa Bronze: catálogo de descargas, descarga trazable, ZIP y manifest.

Reglas que implementa (ARQUITECTURA.md §3 y §5 Fase 1):
- Bronze es inmutable: un archivo descargado nunca se sobrescribe ni se borra.
- Cada descarga va en data/bronze/<fuente>/<AAAA-MM-DD>/.
- Cada archivo queda en data/bronze/manifest.json con URL, fecha, tamaño, sha256 y n° de filas.
- No se abre, limpia, filtra ni convierte ningún dato (solo se cuentan líneas).
"""

from __future__ import annotations

import hashlib
import json
import time
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

import requests

from src.config import cargar_config, raiz_proyecto, ruta

FIRMAS_HTML = (b"<!doctype html", b"<html")
EXT_CON_FILAS = {".csv", ".txt"}


# --------------------------------------------------------------------------- catálogo
@dataclass
class Recurso:
    fuente: str
    carpeta_bronze: str
    archivo: str
    url: str | None
    modo: str = "automatica"            # automatica | manual
    subcarpeta: str = ""
    anio: int | None = None
    descomprimir: bool = False
    nota: str | None = None

    def destino(self, fecha: str) -> Path:
        base = ruta("bronze") / self.carpeta_bronze / fecha
        return (base / self.subcarpeta / self.archivo) if self.subcarpeta else base / self.archivo


def _rango(par: list[int]) -> range:
    return range(par[0], par[1] + 1)


def construir_catalogo(fuentes: dict[str, Any]) -> list[Recurso]:
    """Traduce config.yaml → fuentes a la lista de recursos a descargar."""
    recursos: list[Recurso] = []
    for fid, f in fuentes.items():
        if f["tipo"] == "referencia":
            continue
        carpeta = f["carpeta_bronze"]

        for a in f.get("archivos", []):
            if a.get("estado_url") == "pendiente":
                continue
            if f["tipo"] == "manual":
                recursos.append(Recurso(fid, carpeta, a["archivo"], None, modo="manual"))
                continue

            # Recurso por rango de años con plantilla de nombre/URL
            if "anios" in a:
                for anio in _rango(a["anios"]):
                    nombre = (a.get("plantilla") or a["archivo"]).format(anio=anio)
                    url = a["url"].format(anio=anio) if "url" in a else f"{f['url_base']}/{nombre}"
                    recursos.append(Recurso(
                        fid, carpeta, nombre, url, anio=anio,
                        subcarpeta=a.get("subcarpeta", "").format(anio=anio),
                        descomprimir=f.get("descomprimir_zip", False) and nombre.lower().endswith(".zip"),
                        nota=a.get("nota"),
                    ))
            else:
                nombre = a["archivo"]
                url = a.get("url") or f"{f['url_base']}/{nombre}"
                recursos.append(Recurso(
                    fid, carpeta, nombre, url, anio=a.get("anio"),
                    subcarpeta=str(a.get("subcarpeta", "")),
                    descomprimir=f.get("descomprimir_zip", False) and nombre.lower().endswith(".zip"),
                    nota=a.get("nota"),
                ))
    return recursos


# --------------------------------------------------------------------------- manifest
def leer_manifest() -> dict[str, Any]:
    p = ruta("manifest")
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"descripcion": "Inventario de archivos de la capa Bronze", "archivos": []}


def guardar_manifest(manifest: dict[str, Any]) -> None:
    p = ruta("manifest")
    manifest["actualizado_utc"] = _ahora()
    manifest["archivos"].sort(key=lambda e: e["ruta"])
    tmp = p.with_suffix(".json.part")
    tmp.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


def ultima_entrada(manifest: dict[str, Any], url: str) -> dict[str, Any] | None:
    """Entrada más reciente del manifest para una URL (descarga directa, no extraídos)."""
    cand = [e for e in manifest["archivos"] if e.get("url") == url and e.get("origen") == "descarga"]
    return max(cand, key=lambda e: e["fecha_descarga_utc"]) if cand else None


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rel(p: Path) -> str:
    return p.relative_to(raiz_proyecto()).as_posix()


# --------------------------------------------------------------------------- utilidades de archivo
def sha256_archivo(p: Path, chunk: int = 8 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        while b := f.read(chunk):
            h.update(b)
    return h.hexdigest()


def contar_filas(p: Path) -> int | None:
    """N° de filas de datos (líneas físicas − encabezado). None si no es un archivo de texto tabular.

    Es un conteo físico: si un campo trae saltos de línea entre comillas, el perfilado
    (02_bronze_perfilado) lo detectará comparando con el conteo de Spark.
    """
    if p.suffix.lower() not in EXT_CON_FILAS:
        return None
    lineas, ultimo = 0, b"\n"
    with p.open("rb") as f:
        while b := f.read(8 * 1024 * 1024):
            lineas += b.count(b"\n")
            ultimo = b[-1:]
    if ultimo != b"\n":
        lineas += 1                      # última línea sin salto final
    return max(lineas - 1, 0)


def entrada_manifest(p: Path, *, fuente: str, url: str | None, modo: str, origen: str,
                     fecha_carpeta: str, extra: dict[str, Any] | None = None,
                     sha256: str | None = None) -> dict[str, Any]:
    e = {
        "fuente": fuente,
        "ruta": _rel(p),
        "archivo": p.name,
        "url": url,
        "modo": modo,                     # automatica | manual
        "origen": origen,                 # descarga | extraido_de_zip | copia_manual
        "fecha_carpeta": fecha_carpeta,
        "fecha_descarga_utc": _ahora(),
        "bytes": p.stat().st_size,
        "sha256": sha256 or sha256_archivo(p),
        "filas": contar_filas(p),
    }
    if extra:
        e.update({k: v for k, v in extra.items() if v is not None})
    return e


# --------------------------------------------------------------------------- descarga
@dataclass
class Resultado:
    recurso: Recurso
    estado: str                       # descargado | sin_cambios | ya_existe | manual_registrado | manual_faltante | error
    detalle: str = ""
    entradas: list[dict[str, Any]] = field(default_factory=list)
    segundos: float = 0.0


def _sesion_http() -> requests.Session:
    cfg = cargar_config()["descarga"]
    s = requests.Session()
    s.headers["User-Agent"] = cfg["user_agent"]
    return ss

def _descargar_a(s: requests.Session, url: str, destino: Path) -> tuple[str, int]:
    """Descarga en streaming a <destino>.part, valida y renombra. Devuelve (sha256, bytes)."""
    cfg = cargar_config()["descarga"]
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_name(destino.name + ".part")
    ultimo_error: Exception | None = None

    for intento in range(1, cfg["reintentos"] + 1):
        try:
            h, n, primeros = hashlib.sha256(), 0, b""
            with s.get(url, stream=True, timeout=(cfg["timeout_conexion_s"], cfg["timeout_lectura_s"])) as r:
                r.raise_for_status()
                esperado = int(r.headers.get("Content-Length") or -1)
                with tmp.open("wb") as f:
                    for chunk in r.iter_content(chunk_size=cfg["chunk_mb"] * 1024 * 1024):
                        if not chunk:
                            continue
                        if not primeros:
                            primeros = chunk[:512]
                        f.write(chunk)
                        h.update(chunk)
                        n += len(chunk)
            if n == 0:
                raise ValueError("archivo vacío")
            if primeros.lstrip().lower().startswith(FIRMAS_HTML):
                raise ValueError("el servidor devolvió HTML en lugar del archivo")
            if esperado > 0 and n != esperado:
                raise ValueError(f"descarga incompleta: {n} de {esperado} bytes")
            if destino.suffix.lower() == ".zip" and not zipfile.is_zipfile(tmp):
                raise ValueError("el archivo no es un ZIP válido")
            tmp.replace(destino)
            return h.hexdigest(), n
        except Exception as e:  # noqa: BLE001 — se reintenta y se informa
            ultimo_error = e
            tmp.unlink(missing_ok=True)
            if intento < cfg["reintentos"]:
                time.sleep(5 * intento)
    raise RuntimeError(f"falló tras {cfg['reintentos']} intentos: {ultimo_error}")


def extraer_zip(zip_path: Path) -> list[Path]:
    """Descomprime junto al ZIP, en <carpeta_del_zip>/<nombre_del_zip>/, sin sobrescribir nada ni salir de ella.

    La subcarpeta con el nombre del ZIP evita choques cuando una misma edición trae
    varios ZIP (p. ej. RENAMU 2025 F01 y F02).
    """
    base = (zip_path.parent / zip_path.stem).resolve()
    extraidos: list[Path] = []
    with zipfile.ZipFile(zip_path) as z:
        if (malo := z.testzip()) is not None:
            raise ValueError(f"ZIP dañado: {malo}")
        for info in z.infolist():
            if info.is_dir():
                continue
            nombre = info.filename
            if not (info.flag_bits & 0x800):          # nombre no UTF-8: el INEI usa cp850/cp437
                try:
                    nombre = nombre.encode("cp437").decode("cp850")
                except UnicodeError:
                    pass
            partes = [p for p in PurePosixPath(nombre.replace("\\", "/")).parts if p not in ("", ".", "..")]
            destino = base.joinpath(*partes).resolve()
            if base not in destino.parents:
                raise ValueError(f"ruta insegura en el ZIP: {info.filename}")
            if destino.exists():
                raise FileExistsError(f"ya existe (Bronze es inmutable): {destino}")
            destino.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, destino.open("wb") as dst:
                while b := src.read(8 * 1024 * 1024):
                    dst.write(b)
            extraidos.append(destino)
    return extraidos


def procesar_recurso(r: Recurso, fecha: str, manifest: dict[str, Any],
                     s: requests.Session, forzar: bool = False) -> Resultado:
    t0 = time.time()
    destino = r.destino(fecha)
    extra = {"anio": r.anio, "nota": r.nota}

    # --- archivos manuales: se registran si alguien los copió en alguna fecha
    if r.modo == "manual":
        carpeta = ruta("bronze") / r.carpeta_bronze
        encontrados = sorted(carpeta.glob(f"*/{r.archivo}"))
        registrados = {e["ruta"] for e in manifest["archivos"]}
        nuevos = [p for p in encontrados if _rel(p) not in registrados]
        if not encontrados:
            return Resultado(r, "manual_faltante", f"copiar a {_rel(carpeta)}/<AAAA-MM-DD>/{r.archivo}")
        ents = [entrada_manifest(p, fuente=r.fuente, url=None, modo="manual", origen="copia_manual",
                                 fecha_carpeta=p.parent.name) for p in nuevos]
        estado = "manual_registrado" if ents else "ya_existe"
        return Resultado(r, estado, f"{len(encontrados)} copia(s) en Bronze", ents, time.time() - t0)

    # --- archivo ya presente en la carpeta de hoy
    if destino.exists():
        return Resultado(r, "ya_existe", _rel(destino), segundos=time.time() - t0)

    # --- sin cambios en el servidor respecto de la última descarga registrada
    remoto = info_remota(s, r.url)
    previo = ultima_entrada(manifest, r.url)
    if (not forzar and previo
            and previo.get("bytes") == remoto["bytes_remoto"]
            and previo.get("last_modified") == remoto["last_modified"]
            and (raiz_proyecto() / previo["ruta"]).exists()):
        return Resultado(r, "sin_cambios", f"vigente: {previo['ruta']}", segundos=time.time() - t0)

    sha, n = _descargar_a(s, r.url, destino)
    ents = [entrada_manifest(destino, fuente=r.fuente, url=r.url, modo="automatica", origen="descarga",
                             fecha_carpeta=fecha, sha256=sha,
                             extra={**extra, "last_modified": remoto["last_modified"]})]
    if r.descomprimir:
        for p in extraer_zip(destino):
            ents.append(entrada_manifest(p, fuente=r.fuente, url=r.url, modo="automatica",
                                         origen="extraido_de_zip", fecha_carpeta=fecha,
                                         extra={**extra, "zip": _rel(destino)}))
    return Resultado(r, "descargado", f"{n / 1e6:,.1f} MB", ents, time.time() - t0)
