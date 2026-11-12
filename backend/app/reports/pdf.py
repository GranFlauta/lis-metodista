"""Render de informes inmutables y vistas previas con páginas físicas Letter."""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any
from decimal import Decimal, InvalidOperation

from weasyprint import HTML


REPORT_DIR = Path(__file__).resolve().parent
ASSETS_DIR = REPORT_DIR / "assets"
TEMPLATE_DIR = REPORT_DIR / "templates"
def _resultado_clinico(parametro: dict[str, Any]) -> str | None:
    raw = parametro.get("valor")
    if raw is None or str(raw).strip() == "":
        return None

    value = str(raw).strip()
    code = parametro.get("codigo")
    if code in {"FR_DILUCION", "ASTO_DILUCION"}:
        first = value.split(";", 1)[0].strip()
        no_reactivo = re.match(r"^No reactivo:\s*(.+)$", first, re.IGNORECASE)
        if no_reactivo:
            return f"No reactivo · {no_reactivo.group(1).strip()}"
        sin_dilucion = re.match(r"^Reactivo sin dilución:\s*(.+)$", first, re.IGNORECASE)
        if sin_dilucion:
            return f"Reactivo · {sin_dilucion.group(1).strip()}"
        dilucion = re.match(r"^Reactivo\s+(\S+):\s*(.+)$", first, re.IGNORECASE)
        if dilucion:
            return f"Reactivo · {dilucion.group(1)} · {dilucion.group(2).strip()}"
        return first
    return value


def _valor_referencia(parametro: dict[str, Any]) -> str:
    referencia = parametro.get("referencia") or {}
    return str(referencia.get("texto") or "").strip()


def _preparar_estudios(estudios: list[dict[str, Any]], etiqueta_cayados: str | None = None) -> list[dict[str, Any]]:
    preparados = []
    for estudio in estudios:
        secciones_out = []
        for seccion in estudio.get("secciones") or []:
            parametros = seccion.get("parametros") or []
            by_code = {p.get("codigo"): p for p in parametros}
            rows = []
            total_diferencial = Decimal("0")
            hay_diferencial = False
            for param in parametros:
                code = str(param.get("codigo") or "")
                if code.endswith("_ABS"):
                    continue
                value = _resultado_clinico(param)
                if value is None:
                    continue
                if estudio.get("codigo") == "HEMOGRAMA" and seccion.get("grupo") == "DIFERENCIAL" and code.endswith("_PCT"):
                    try:
                        total_diferencial += Decimal(str(param.get("valor")).replace(",", "."))
                        hay_diferencial = True
                    except (InvalidOperation, TypeError):
                        pass
                abs_param = by_code.get(f"{code[:-4]}_ABS") if code.endswith("_PCT") else None
                absolute = _resultado_clinico(abs_param) if abs_param else None
                name = param.get("nombre") or code
                if code == "CAYADOS_PCT" and etiqueta_cayados and etiqueta_cayados.strip():
                    name = etiqueta_cayados.strip()[:80]
                rows.append({
                    "codigo": code,
                    "nombre": name,
                    "valor": value,
                    "relativo": value if abs_param else None,
                    "absoluto": absolute,
                    "unidad": "" if code in {"FR_DILUCION", "ASTO_DILUCION"} else (param.get("unidad") or ""),
                    "referencia": _valor_referencia(param),
                    "bandera": param.get("bandera"),
                    "compuesto": abs_param is not None,
                })
            if rows:
                total_text = format(total_diferencial, "f").rstrip("0").rstrip(".") if "." in format(total_diferencial, "f") else format(total_diferencial, "f")
                secciones_out.append({"grupo": seccion.get("grupo"), "filas": rows, "suma_diferencial": total_text if hay_diferencial else None})
        if secciones_out:
            preparados.append({
                "codigo": estudio.get("codigo"),
                "nombre": estudio.get("nombre") or "Estudio",
                "secciones": secciones_out,
                "observaciones": (estudio.get("observaciones") or "").strip(),
            })
    return preparados


def renderizar_html_informe(documento: dict[str, Any]) -> str:
    """Prepara una plantilla de informe segura con autoescape y datos del snapshot."""
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    jinja = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(("html", "xml")),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    prepared = dict(documento)
    prepared["estudios"] = _preparar_estudios(
        documento.get("estudios") or [],
        documento.get("etiqueta_cayados"),
    )
    template = jinja.get_template("informe.html")
    return template.render(**prepared)


def generar_informe_pdf(documento: dict[str, Any]) -> bytes:
    """Genera bytes PDF; todos los recursos usados son locales al paquete backend."""
    html = renderizar_html_informe(documento)
    # A URI de directorio sin la barra final resuelve las imágenes relativas
    # como hermanas de "assets" y WeasyPrint las sustituye por el texto alt.
    return HTML(string=html, base_url=f"{ASSETS_DIR.resolve().as_uri()}/").write_pdf()
