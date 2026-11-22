"""Utilidades del RENAMU: lectura de los diccionarios PDF como tablas (catálogo de variables).

Nota: la descripción por *campo* (`descripcion_campo`) es confiable; la de la *pregunta* puede
desalinearse en los bordes de bloque del PDF, por eso la clasificación usa ambas.

Los diccionarios del INEI son tablas con columnas:
    Nº PREGUNTA | DESCRIPCIÓN | NOMBRE DEL CAMPO | DESCRIPCIÓN DEL CAMPO | VALORES
La celda "Nº / DESCRIPCIÓN" está combinada en vertical, así que el número aparece en la fila
central del bloque, no en la primera. Por eso el número de pregunta se deduce del **código
del campo** (P13_5 -> 13, C96_1_1 -> 96, VFI_P31 -> 31) y la descripción de la pregunta se toma
de las filas que sí traen el número.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from pathlib import Path

import pandas as pd

logging.getLogger("pdfminer").setLevel(logging.ERROR)

RE_CAMPO = re.compile(r"^(VFI_)?[A-Za-z]{1,6}\d{1,3}[A-Za-z0-9_]*$|^(Tipomuni|Ubigeo|idmunici|ccdd|ccpp|ccdi)$", re.I)
RE_NRO = re.compile(r"^(?:VFI_)?([A-Za-z]+?)(\d{1,3})")
RE_MODULO = re.compile(r"M[ÓO]DULO\s+([IVXL]+)\s*[:.\-]?\s*([^\n]{0,120})", re.I)


def normalizar(t: str | None) -> str:
    """Minúsculas, sin tildes y con espacios simples (para buscar palabras clave)."""
    if not isinstance(t, str) or not t:
        return ""
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t).strip().lower()


def _limpio(c) -> str:
    return re.sub(r"\s+", " ", (c or "").replace("\n", " ")).strip()


def nro_pregunta(campo: str) -> str | None:
    """'P13_5' -> 'P13', 'C96_1_1' -> 'C96', 'VFI_P31' -> 'P31' (los cuadros C y las preguntas P no se mezclan)."""
    m = RE_NRO.match(campo or "")
    return f"{m.group(1).upper()}{int(m.group(2)):02d}" if m else None


def extraer_diccionario(pdf: Path) -> pd.DataFrame:
    """Una fila por campo: modulo, nro_pregunta, pregunta, campo, descripcion_campo, valores, pagina, pdf."""
    import pdfplumber

    filas, preguntas, modulo, actual = [], {}, None, None
    with pdfplumber.open(pdf) as doc:
        for i, pag in enumerate(doc.pages, 1):
            m = RE_MODULO.search(pag.extract_text() or "")
            if m:
                modulo = f"MÓDULO {m.group(1).upper()}: {m.group(2).strip()}".strip(": ")
            for tabla in pag.extract_tables():
                for r in tabla:
                    r = ([_limpio(c) for c in r] + [""] * 5)[:5]
                    if r[0].upper().startswith("Nº") or r[2].upper().startswith("NOMBRE DEL CAMPO"):
                        continue
                    if re.fullmatch(r"\d{1,3}[A-Z]?", r[0]) and r[1]:
                        n = re.match(r"\d+", r[0]).group(0)
                        preguntas[n] = (preguntas.get(n, "") + " " + r[1]).strip()
                    if r[2] and RE_CAMPO.match(r[2]):
                        actual = {"modulo": modulo, "campo": r[2], "descripcion_campo": r[3], "valores": r[4], "pagina": i, "pdf": pdf.name}
                        filas.append(actual)
                    elif actual is not None and not r[2]:
                        if r[4]:
                            actual["valores"] = (actual["valores"] + " | " + r[4]).strip(" |")
                        if r[3]:
                            actual["descripcion_campo"] = (actual["descripcion_campo"] + " " + r[3]).strip()
    df = pd.DataFrame(filas)
    if df.empty:
        return df
    df["nro_pregunta"] = df["campo"].map(nro_pregunta)
    # la descripción de la fila numerada corresponde a la pregunta P; los cuadros C se describen por su primer campo
    num = df["nro_pregunta"].str.extract(r"(\d+)$")[0].map(lambda n: str(int(n)) if isinstance(n, str) else n)
    es_p = df["nro_pregunta"].str.startswith("P")
    df["pregunta"] = num.map({str(int(k)): v for k, v in preguntas.items() if k.isdigit()}).where(es_p, None)
    # cuadros C: descripción del campo principal (C96 = "Total de ingresos ejecutados…"), no la de VFI_ ("Municipalidad informante")
    principal = df[df["campo"].str.upper() == df["nro_pregunta"].str.upper()].set_index("nro_pregunta")["descripcion_campo"]
    raiz = df["nro_pregunta"].map(principal).fillna(df.groupby("nro_pregunta")["descripcion_campo"].transform("last")).str.split(" / ").str[0]
    df["pregunta"] = df["pregunta"].fillna(raiz).fillna("")
    return df[["modulo", "nro_pregunta", "pregunta", "campo", "descripcion_campo", "valores", "pagina", "pdf"]]


def cargar_mapeo(ruta_yaml: Path) -> dict:
    """Lee data/silver/renamu_mapeo.yaml (claves de edición como int)."""
    import yaml

    with open(ruta_yaml, encoding="utf-8") as f:
        m = yaml.safe_load(f)
    m["ediciones"] = {int(k): v for k, v in m["ediciones"].items()}
    return m


# --- Estructura del diccionario (módulos y secciones), leída del texto: funciona en todas las ediciones 2009–2026 ---

RE_CODIGO_LINEA = re.compile(r"(?<![A-Za-z0-9_])((?:VFI_)?[A-Z]{1,4}\d{1,3}[A-Z0-9_]*)\s+(.*)")
_NO_TITULO = re.compile(r"^(TABLA|CUADRO|Nº|N°|DESCRIPCI|PREGUNTA|CAMPO|NOMBRE|REGISTRO NACIONAL|FORMULARIO|DICCIONARIO|DEL CAMPO|A CAMPO)")


def _es_titulo(linea: str, siguiente: str = "") -> bool:
    """Título de sección: línea en mayúsculas, sin números. Una sola palabra solo si la sigue el encabezado de la tabla (p. ej. SALUD)."""
    s = linea.strip()
    if len(s) < 5 or s[0] == "(" or _NO_TITULO.match(s) or re.search(r"\d", s):
        return False
    letras = [c for c in s if c.isalpha()]
    if len(letras) < 5 or sum(c.isupper() for c in letras) / len(letras) < 0.9:
        return False
    return len(s.split()) >= 2 or siguiente.strip().startswith(("Nº", "N°", "TABLA"))


def seccion_canonica(modulo: str | None, seccion: str | None) -> str:
    """Nombre comparable entre ediciones. Sin sección, se usa el título del módulo."""
    t = seccion or re.sub(r"^M[ÓO]DULO\s+[IVX]+\s*:?\s*", "", modulo or "") or "SIN MÓDULO"
    n = normalizar(t)
    if "defensoria" in n or "demuna" in n:
        return "DEMUNA"
    if n.startswith("proteccion y conservacion"):
        return "PROTECCIÓN Y CONSERVACIÓN DEL MEDIO AMBIENTE"
    if n.startswith("ingresos y gastos") or n == "finanzas municipales":
        return "FINANZAS MUNICIPALES"
    if n.startswith("recursos humanos"):
        return "RECURSOS HUMANOS"
    return t.upper().strip()


def estructura_diccionario(pdfs) -> pd.DataFrame:
    """Una fila por campo: módulo, sección, texto de su línea y `texto_extra` (las líneas sin código que le siguen,
    donde suele continuar la descripción de la pregunta). Sirve para buscar conceptos por pregunta en todas las ediciones."""
    import pdfplumber

    filas = []
    for pdf in pdfs:
        modulo = seccion = None
        actual = None
        with pdfplumber.open(pdf) as doc:
            for i, pag in enumerate(doc.pages, 1):
                lineas = (pag.extract_text() or "").split("\n")
                for j, linea in enumerate(lineas):
                    s = linea.strip()
                    if s.startswith("DEFINICIÓN DE VARIABLES"):
                        modulo, seccion = "VARIABLES GLOBALES", None
                        continue
                    if re.match(r"^M[ÓO]DULO\s+[IVX]+", s):
                        modulo, seccion = s, None
                        continue
                    if _es_titulo(s, lineas[j + 1] if j + 1 < len(lineas) else ""):
                        # en 2009–2014 el título del módulo viene en la línea siguiente a "MÓDULO I"
                        if modulo and re.fullmatch(r"M[ÓO]DULO\s+[IVX]+", modulo):
                            modulo = f"{modulo}: {s}"
                        else:
                            seccion = s
                        continue
                    m = RE_CODIGO_LINEA.search(s)
                    if m:
                        actual = {"campo": m.group(1).upper(), "nro_pregunta": nro_pregunta(m.group(1)), "modulo": modulo,
                                  "seccion": seccion, "seccion_canonica": seccion_canonica(modulo, seccion),
                                  "texto": m.group(2), "texto_extra": s[: m.start()].strip(), "pagina": i, "pdf": Path(pdf).name}
                        filas.append(actual)
                    elif actual is not None and s and not _NO_TITULO.match(s):
                        actual["texto_extra"] = (actual["texto_extra"] + " " + s).strip()
    df = pd.DataFrame(filas)
    return df.drop_duplicates("campo").reset_index(drop=True) if not df.empty else df
