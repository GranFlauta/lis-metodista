"""Render de informes inmutables y vistas previas con páginas físicas Letter."""
from __future__ import annotations

from pathlib import Path
import base64
from io import BytesIO
import re
from threading import Lock
from typing import Any
from decimal import Decimal, InvalidOperation
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pypdfium2 as pdfium
from weasyprint import HTML
from app.reports.curva import preparar_curva
from app.reports.presentation import estudios_para_informe, formatear_numero_informe, resultado_para_informe


REPORT_DIR = Path(__file__).resolve().parent
ASSETS_DIR = REPORT_DIR / "assets"
TEMPLATE_DIR = REPORT_DIR / "templates"
_PDFIUM_LOCK = Lock()  # PDFium requiere exclusión mutua incluso entre documentos.
_ZONA_LABORATORIO = ZoneInfo("America/La_Paz")


def _fecha_local(valor: Any) -> date | datetime | None:
    """No inventa horas para fechas que sólo tienen día, mes y año."""
    if not valor:
        return None
    if isinstance(valor, str):
        try:
            valor = date.fromisoformat(valor) if len(valor) == 10 else datetime.fromisoformat(valor.replace("Z", "+00:00"))
        except ValueError:
            return None
    if isinstance(valor, datetime):
        return (valor if valor.tzinfo else valor.replace(tzinfo=timezone.utc)).astimezone(_ZONA_LABORATORIO)
    return valor if isinstance(valor, date) else None


def _datos_presentacion(documento: dict[str, Any]) -> dict[str, str]:
    orden = documento.get("orden") or {}
    toma = _fecha_local(orden.get("fecha_hora_toma_muestra")) or _fecha_local(orden.get("creado_en"))
    entrega = _fecha_local(documento.get("publicado_en")) if documento.get("aprobado") else None
    fecha = entrega or toma or _fecha_local(orden.get("fecha_solicitud"))
    nombre = str((documento.get("firmante") or {}).get("nombre_completo") or "").strip()
    nombre = re.sub(r"^lic\.\s*", "", nombre, flags=re.IGNORECASE)
    return {
        "fecha": fecha.strftime("%d/%m/%Y") if fecha else "No registrada",
        "hora_toma": toma.strftime("%H:%M") if isinstance(toma, datetime) else "No registrada",
        "hora_entrega": entrega.strftime("%H:%M") if isinstance(entrega, datetime) else "No registrada" if documento.get("aprobado") else "Pendiente de publicación",
        "responsable": f"LIC. {nombre}" if nombre else "",
    }


def _resultado_clinico(parametro: dict[str, Any]) -> str | None:
    return resultado_para_informe(parametro)


def _valor_referencia(parametro: dict[str, Any]) -> str:
    referencia = parametro.get("referencia") or {}
    return str(referencia.get("texto") or "").strip()


def _preparar_estudios(estudios: list[dict[str, Any]], etiqueta_cayados: str | None = None, separador_decimal: str = ",") -> list[dict[str, Any]]:
    preparados = []
    for estudio in estudios_para_informe(estudios):
        secciones_out = []
        for seccion in estudio.get("secciones") or []:
            parametros = seccion.get("parametros") or []
            by_code = {p.get("codigo"): p for p in parametros}
            rows = []
            total_diferencial = Decimal("0")
            hay_diferencial = False
            for param in parametros:
                if seccion.get("formato") == "MUESTRAS_SERIADAS" and param.get("muestras_seriadas"):
                    serie = param["muestras_seriadas"]
                    for muestra in serie["muestras"]:
                        if muestra.get("fecha") and muestra.get("resultado"):
                            fecha = "/".join(muestra["fecha"].split("-")[::-1])
                            if muestra.get("hora"):
                                fecha = f"{fecha} {muestra['hora']}"
                            rows.append({"nombre": f"{muestra['numero']}.ª MUESTRA", "fecha": fecha,
                                         "turno": muestra.get("turno") or "", "valor": muestra["resultado"]})
                    if serie.get("resultado_anterior"):
                        rows.append({"nombre": "Resultado anterior", "fecha": "—", "turno": "", "valor": serie["resultado_anterior"]})
                    continue
                code = str(param.get("codigo") or "")
                if code.endswith("_ABS"):
                    continue
                value = _resultado_clinico(param)
                if value is None:
                    continue
                if param.get("tipo_campo") in ("NUMERICO", "CALCULADO") or param.get("serologia"):
                    value = formatear_numero_informe(value, separador_decimal)
                if estudio.get("codigo") == "HEMOGRAMA" and seccion.get("grupo") == "DIFERENCIAL" and code.endswith("_PCT"):
                    try:
                        total_diferencial += Decimal(str(param.get("valor")).replace(",", "."))
                        hay_diferencial = True
                    except (InvalidOperation, TypeError):
                        pass
                abs_param = by_code.get(f"{code[:-4]}_ABS") if code.endswith("_PCT") else None
                absolute = _resultado_clinico(abs_param) if abs_param else None
                if absolute is not None:
                    absolute = formatear_numero_informe(absolute, separador_decimal)
                name = param.get("nombre") or code
                if code == "CAYADOS_PCT" and etiqueta_cayados and etiqueta_cayados.strip():
                    name = etiqueta_cayados.strip()[:80]
                rows.append({
                    "codigo": code,
                    "nombre": name,
                    "valor": value,
                    "relativo": value if abs_param else None,
                    "absoluto": absolute,
                    "unidad": (param["serologia"]["unidad"] if param.get("serologia") else "" if code in {"FR_DILUCION", "ASTO_DILUCION"} else (param.get("unidad") or "")).replace("dilución", ""),
                    "referencia": (param["serologia"]["referencia"] if param.get("serologia") else _valor_referencia(param)),
                    "muestra": param.get("muestra") or "",
                    "metodo": param.get("metodo") or "",
                    "bandera": param.get("bandera"),
                    "compuesto": abs_param is not None,
                })
            if rows:
                total_text = format(total_diferencial, "f").rstrip("0").rstrip(".") if "." in format(total_diferencial, "f") else format(total_diferencial, "f")
                secciones_out.append({"grupo": seccion.get("grupo"), "formato": seccion.get("formato"),
                                      "filas": rows, "suma_diferencial": total_text if hay_diferencial else None,
                                      "columnas": seccion.get("columnas") or {},
                                      "tiene_turno": any(fila.get("turno") for fila in rows)})
        if secciones_out:
            preparados.append({
                "codigo": estudio.get("codigo"),
                "nombre": estudio.get("nombre") or "Estudio",
                "secciones": secciones_out,
                "curva_tolerancia": preparar_curva(estudio.get("curva_tolerancia"), separador_decimal)
                    if estudio.get("codigo") == "CURVA_TOLERANCIA" else None,
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
    prepared["presentacion"] = _datos_presentacion(documento)
    prepared["estudios"] = _preparar_estudios(
        documento.get("estudios") or [],
        documento.get("etiqueta_cayados"),
        documento.get("separador_decimal", ","),
    )
    template = jinja.get_template("informe.html")
    return template.render(**prepared)


def generar_informe_pdf(documento: dict[str, Any]) -> bytes:
    """Genera bytes PDF; todos los recursos usados son locales al paquete backend."""
    html = renderizar_html_informe(documento)
    # A URI de directorio sin la barra final resuelve las imágenes relativas
    # como hermanas de "assets" y WeasyPrint las sustituye por el texto alt.
    base_url = f"{ASSETS_DIR.resolve().as_uri()}/"
    render = HTML(string=html, base_url=base_url).render()
    # La geometría real distingue un estudio que cabe entero de otro mayor que una hoja.
    # Sólo los que necesitan varias páginas se vuelven a maquetar: el primero comienza
    # debajo de los datos del paciente; los siguientes siempre empiezan en hoja nueva.
    # Así se evitan portadas vacías al combinar keep-together con tablas muy largas.
    fragmentos: dict[str, set[int]] = {}
    for numero, pagina in enumerate(render.pages):
        for caja in pagina._page_box.descendants():
            elemento = caja.element
            if elemento is not None and elemento.get("data-study-index") is not None:
                indice = elemento.get("data-study-index")
                fragmentos.setdefault(indice, set()).add(numero)
    largos = {indice for indice, paginas in fragmentos.items() if len(paginas) > 1}
    if largos:
        for indice in largos:
            html = re.sub(
                r'(<section class="study(?: is-first)?)(" data-study-index="' + re.escape(indice) + r'")',
                r'\1 is-oversized\2', html,
            )
        render = HTML(string=html, base_url=base_url).render()
    return render.write_pdf()


def generar_vista_previa(documento: dict[str, Any]) -> dict[str, Any]:
    """Entrega páginas de pantalla; el PDF preliminar nunca se envía al cliente."""
    return generar_paginas_informe({**documento, "aprobado": False})


def generar_paginas_informe(documento: dict[str, Any]) -> dict[str, Any]:
    """Rasteriza la misma plantilla oficial para consulta sin descarga ni impresión."""
    pdf_bytes = generar_informe_pdf(documento)
    paginas = []
    with _PDFIUM_LOCK:
        pdf = pdfium.PdfDocument(pdf_bytes)
        try:
            for indice in range(len(pdf)):
                pagina = pdf[indice]
                try:
                    bitmap = pagina.render(scale=2)
                    try:
                        imagen = bitmap.to_pil()
                        try:
                            with BytesIO() as buffer:
                                imagen.save(buffer, format="PNG")
                                contenido = base64.b64encode(buffer.getvalue()).decode("ascii")
                            paginas.append({
                                "numero": indice + 1,
                                "ancho": imagen.width,
                                "alto": imagen.height,
                                "imagen": f"data:image/png;base64,{contenido}",
                            })
                        finally:
                            imagen.close()
                    finally:
                        bitmap.close()
                finally:
                    pagina.close()
        finally:
            pdf.close()
    return {"formato": "Carta", "paginas": paginas}
