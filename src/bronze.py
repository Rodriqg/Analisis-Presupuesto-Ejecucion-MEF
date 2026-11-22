"""Funciones de la capa Bronze: catálogo de descargas, descarga trazable, ZIP, manifest y volúmenes.

Reglas que implementa (ARQUITECTURA.md §3 y §5 Fase 1, D-014):
- Cada archivo vive en una ruta fija: data/bronze/<fuente>/[<subcarpeta>/]<archivo> (sin carpeta por fecha).
- Si el servidor publica una versión nueva, se descarga a <archivo>.part, se valida y recién
  entonces reemplaza a la anterior. Si la descarga falla, la versión anterior queda intacta.
- manifest.json es el inventario de lo que hay hoy en Bronze: una entrada por archivo vigente,
  con URL, fecha de descarga, run_id, tamaño, sha256 y n° de filas.
- No se abre, limpia, filtra ni convierte ningún dato (solo se cuentan líneas).
"""

from __future__ import annotations

import hashlib
import json
import shutil
import time
import zipfile
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from zoneinfo import ZoneInfo

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

    def destino(self) -> Path:
        base = ruta("bronze") / self.carpeta_bronze
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
    return {"descripcion": "Inventario de los archivos vigentes en la capa Bronze", "archivos": []}


def guardar_manifest(manifest: dict[str, Any]) -> None:
    p = ruta("manifest")
    manifest["actualizado_utc"] = _ahora()
    manifest["archivos"].sort(key=lambda e: e["ruta"])
    tmp = p.with_suffix(".json.part")
    tmp.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


def entrada_descarga(manifest: dict[str, Any], url: str) -> dict[str, Any] | None:
    """Entrada vigente del manifest para una URL (el archivo descargado, no sus extraídos)."""
    cand = [e for e in manifest["archivos"] if e.get("url") == url and e.get("origen") == "descarga"]
    return max(cand, key=lambda e: e["fecha_descarga_utc"]) if cand else None


def registrar_resultado(manifest: dict[str, Any], res: "Resultado", run_id: str) -> bool:
    """Aplica al manifest el resultado de un recurso. Devuelve True si hubo cambios.

    - descargado / actualizado: se quitan las entradas anteriores de esa URL (archivo y extraídos)
      y se agregan las nuevas.
    - sin_cambios con `last_modified` nuevo (mismo contenido, otra fecha en el servidor): se
      actualiza esa fecha para no volver a descargarlo en la próxima ejecución.
    """
    r = res.recurso
    if res.estado in ("descargado", "actualizado"):
        manifest["archivos"] = [e for e in manifest["archivos"] if e.get("url") != r.url]
        for e in res.entradas:
            e["run_id"] = run_id
        manifest["archivos"].extend(res.entradas)
        return True
    if res.estado == "manual_registrado":
        for e in res.entradas:
            e["run_id"] = run_id
        manifest["archivos"] = [e for e in manifest["archivos"]
                                if e["ruta"] not in {n["ruta"] for n in res.entradas}] + res.entradas
        return True
    if res.estado == "sin_cambios" and res.last_modified:
        previo = entrada_descarga(manifest, r.url)
        if previo and previo.get("last_modified") != res.last_modified:
            previo["last_modified"] = res.last_modified
            return True
    return False


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fecha_local() -> str:
    """Fecha de hoy (AAAA-MM-DD) en la zona horaria del proyecto."""
    return datetime.now(ZoneInfo(cargar_config()["spark"]["timezone"])).strftime("%Y-%m-%d")


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
                     extra: dict[str, Any] | None = None, sha256: str | None = None) -> dict[str, Any]:
    e = {
        "fuente": fuente,
        "ruta": _rel(p),
        "archivo": p.name,
        "url": url,
        "modo": modo,                     # automatica | manual
        "origen": origen,                 # descarga | extraido_de_zip | copia_manual
        "fecha_descarga": fecha_local(),  # AAAA-MM-DD (hora de Lima)
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
    estado: str          # descargado | actualizado | sin_cambios | manual_registrado | manual_faltante | error
    detalle: str = ""
    entradas: list[dict[str, Any]] = field(default_factory=list)
    segundos: float = 0.0
    bytes_descargados: int = 0        # bytes que quedaron escritos en Bronze en esta ejecución
    last_modified: str | None = None  # Last-Modified que informó el servidor


def sesion_http() -> requests.Session:
    cfg = cargar_config()["descarga"]
    s = requests.Session()
    s.headers["User-Agent"] = cfg["user_agent"]
    return s


def info_remota(s: requests.Session, url: str) -> dict[str, Any]:
    """Tamaño y Last-Modified que informa el servidor (HEAD). None si no los informa."""
    try:
        with s.head(url, allow_redirects=True, timeout=(15, 60)) as resp:
            resp.raise_for_status()
            largo = resp.headers.get("Content-Length")
            return {"bytes_remoto": int(largo) if largo else None,
                    "last_modified": resp.headers.get("Last-Modified")}
    except requests.RequestException:
        return {"bytes_remoto": None, "last_modified": None}


def _descargar_a_temporal(s: requests.Session, url: str, destino: Path) -> tuple[Path, str, int]:
    """Descarga en streaming a <destino>.part y la valida. No toca `destino`.

    Devuelve (ruta_temporal, sha256, bytes). Quien llama decide si reemplaza o descarta.
    """
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
            return tmp, h.hexdigest(), n
        except Exception as e:  # noqa: BLE001 — se reintenta y se informa
            ultimo_error = e
            tmp.unlink(missing_ok=True)
            if intento < cfg["reintentos"]:
                time.sleep(5 * intento)
    raise RuntimeError(f"falló tras {cfg['reintentos']} intentos: {ultimo_error}")


def carpeta_extraccion(zip_path: Path) -> Path:
    """Carpeta donde se descomprime un ZIP: <carpeta_del_zip>/<nombre_del_zip>/."""
    return zip_path.parent / zip_path.stem


def eliminar_versiones_anteriores(destino: Path, descomprimir: bool) -> None:
    """Antes de poner una versión nueva: borra la carpeta extraída del ZIP anterior.

    El archivo descargado en sí no se borra aquí: lo reemplaza `Path.replace` de forma atómica.
    """
    if descomprimir:
        base = carpeta_extraccion(destino)
        if base.is_dir():
            shutil.rmtree(base)


def extraer_zip(zip_path: Path) -> list[Path]:
    """Descomprime en <carpeta_del_zip>/<nombre_del_zip>/ sin salir de ella.

    La subcarpeta con el nombre del ZIP evita choques cuando una misma edición trae
    varios ZIP (p. ej. RENAMU 2025 F01 y F02).
    """
    base = carpeta_extraccion(zip_path).resolve()
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
                raise FileExistsError(f"el ZIP trae dos veces el mismo archivo: {destino}")
            destino.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, destino.open("wb") as dst:
                while b := src.read(8 * 1024 * 1024):
                    dst.write(b)
            extraidos.append(destino)
    return extraidos


def procesar_recurso(r: Recurso, manifest: dict[str, Any], s: requests.Session,
                     forzar: bool = False) -> Resultado:
    """Descarga un recurso solo si cambió en el servidor; si cambió, sobrescribe la versión anterior."""
    t0 = time.time()
    destino = r.destino()
    extra = {"anio": r.anio, "nota": r.nota}

    # --- archivos manuales: se registran si alguien los copió en su carpeta
    if r.modo == "manual":
        if not destino.is_file():
            return Resultado(r, "manual_faltante", f"copiar a {_rel(destino)}")
        previa = next((e for e in manifest["archivos"] if e["ruta"] == _rel(destino)), None)
        sha = sha256_archivo(destino)
        if previa and previa["sha256"] == sha:
            return Resultado(r, "sin_cambios", _rel(destino), segundos=time.time() - t0)
        ent = entrada_manifest(destino, fuente=r.fuente, url=None, modo="manual",
                               origen="copia_manual", sha256=sha)
        return Resultado(r, "manual_registrado", _rel(destino), [ent], time.time() - t0, ent["bytes"])

    previo = entrada_descarga(manifest, r.url)
    vigente = previo is not None and destino.is_file()

    # --- 1) el servidor informa el mismo tamaño y fecha que la versión vigente: no se descarga
    remoto = info_remota(s, r.url)
    if (not forzar and vigente
            and remoto["bytes_remoto"] is not None and remoto["last_modified"] is not None
            and previo.get("bytes") == remoto["bytes_remoto"]
            and previo.get("last_modified") == remoto["last_modified"]):
        return Resultado(r, "sin_cambios", f"vigente desde {previo.get('fecha_descarga')}",
                         segundos=time.time() - t0, last_modified=remoto["last_modified"])

    # --- 2) se descarga a .part; si el contenido es idéntico (mismo sha256) se descarta
    tmp, sha, n = _descargar_a_temporal(s, r.url, destino)
    if not forzar and vigente and previo["sha256"] == sha:
        tmp.unlink(missing_ok=True)
        return Resultado(r, "sin_cambios", "mismo contenido (sha256), solo cambió la fecha en el servidor",
                         segundos=time.time() - t0, last_modified=remoto["last_modified"])

    # --- 3) versión nueva: reemplaza a la anterior
    eliminar_versiones_anteriores(destino, r.descomprimir)
    tmp.replace(destino)
    ents = [entrada_manifest(destino, fuente=r.fuente, url=r.url, modo="automatica", origen="descarga",
                             sha256=sha, extra={**extra, "last_modified": remoto["last_modified"]})]
    total = n
    if r.descomprimir:
        for p in extraer_zip(destino):
            ent = entrada_manifest(p, fuente=r.fuente, url=r.url, modo="automatica",
                                   origen="extraido_de_zip", extra={**extra, "zip": _rel(destino)})
            ents.append(ent)
            total += ent["bytes"]
    estado = "actualizado" if vigente else "descargado"
    return Resultado(r, estado, f"{n / 1e6:,.1f} MB", ents, time.time() - t0, total, remoto["last_modified"])


# --------------------------------------------------------------------------- volúmenes (bitácora / auditoría)
def volumenes_bronze(manifest: dict[str, Any], resultados: list[Resultado]) -> list[dict[str, Any]]:
    """Un registro por fuente con lo que hay hoy en Bronze y lo que se movió en esta ejecución.

    Formato común de auditoría (src.auditoria): capa, fuente, tabla, archivos, filas, bytes,
    fecha_datos. `filas` suma las filas de datos de los archivos tabulares (CSV/TXT);
    `bytes` es lo que ocupa la fuente en disco (en RENAMU incluye ZIP y extraídos).
    """
    cfg_f = cargar_config()["fuentes"]
    por_fuente: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in manifest["archivos"]:
        por_fuente[e["fuente"]].append(e)
    movs: dict[str, list[Resultado]] = defaultdict(list)
    for x in resultados:
        movs[x.recurso.fuente].append(x)

    out = []
    for fid in sorted(set(por_fuente) | set(movs)):
        ents, rs = por_fuente.get(fid, []), movs.get(fid, [])
        fechas = [e.get("fecha_descarga") for e in ents if e.get("fecha_descarga")]
        out.append({
            "capa": "bronze",
            "fuente": fid,
            "tabla": cfg_f.get(fid, {}).get("carpeta_bronze", fid),
            "archivos": len(ents),
            "filas": int(sum(e.get("filas") or 0 for e in ents)),
            "bytes": int(sum(e.get("bytes") or 0 for e in ents)),
            "fecha_datos": max(fechas) if fechas else None,     # última descarga vigente de la fuente
            "recursos": len(rs),
            "descargados": sum(x.estado in ("descargado", "actualizado", "manual_registrado") for x in rs),
            "sin_cambios": sum(x.estado == "sin_cambios" for x in rs),
            "errores": sum(x.estado in ("error", "manual_faltante") for x in rs),
            "bytes_descargados": int(sum(x.bytes_descargados for x in rs)),
        })
    return out
