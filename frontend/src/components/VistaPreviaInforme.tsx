import React, { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { generarVistaPreviaApi, VistaPreviaInforme as Documento, VistaPreviaPayload } from "../api/resultados";
import { ApiError } from "../api/client";
import { CargaLaboratorio } from "./MarcaLaboratorio";
import { Icono } from "./Icono";

interface Props {
  ordenId: number;
  payload: VistaPreviaPayload;
  habilitada: boolean;
}

/** Páginas Carta de pantalla, sin visor PDF ni acciones de emisión. */
export function VistaPreviaInforme({ ordenId, payload, habilitada }: Props) {
  const [documento, setDocumento] = useState<Documento | null>(null);
  const [actualizando, setActualizando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pantallaCompleta, setPantallaCompleta] = useState(false);
  const abrirRef = useRef<HTMLButtonElement>(null);
  const cerrarRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    setDocumento(null);
    setPantallaCompleta(false);
  }, [ordenId]);

  useEffect(() => {
    if (!habilitada) {
      setDocumento(null);
      setActualizando(false);
      setPantallaCompleta(false);
      setError(null);
      return;
    }
    let vigente = true;
    const controller = new AbortController();
    setActualizando(true);
    setError(null);
    const timer = window.setTimeout(async () => {
      try {
        const respuesta = await generarVistaPreviaApi(ordenId, payload, controller.signal);
        if (vigente) setDocumento(respuesta);
      } catch (err) {
        if (vigente && !controller.signal.aborted) {
          setError(err instanceof ApiError ? err.message : "No se pudo actualizar la vista previa.");
        }
      } finally {
        if (vigente) setActualizando(false);
      }
    }, 600);
    return () => {
      vigente = false;
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [ordenId, payload, habilitada]);

  useEffect(() => {
    if (!pantallaCompleta) return;
    cerrarRef.current?.focus();
    const overflowAnterior = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const teclado = (event: KeyboardEvent) => {
      if (event.key === "Escape") setPantallaCompleta(false);
      if (event.key === "Tab") {
        event.preventDefault();
        cerrarRef.current?.focus();
      }
    };
    window.addEventListener("keydown", teclado);
    return () => {
      document.body.style.overflow = overflowAnterior;
      window.removeEventListener("keydown", teclado);
      abrirRef.current?.focus();
    };
  }, [pantallaCompleta]);

  const paginas = () => <div className="lis-preview-pages">
    {documento?.paginas.map((pagina) => <figure className="lis-preview-page" key={pagina.numero}>
      <img src={pagina.imagen} width={pagina.ancho} height={pagina.alto}
        alt={`Vista previa no aprobada, página ${pagina.numero} de ${documento.paginas.length}`} draggable={false} />
    </figure>)}
  </div>;

  const estado = <div className="lis-preview-status" role="status" aria-live="polite">
    <span className={`lis-preview-status-dot ${actualizando ? "is-working" : ""}`} aria-hidden="true" />
    {error || (actualizando ? "Actualizando vista previa…" : documento ? `Carta · ${documento.paginas.length} página(s) · No aprobado` : "Vista previa del informe")}
  </div>;

  return <>
    <section className="lis-draft-preview lis-no-print" aria-label="Vista previa del informe">
      <div className="lis-preview-header">
        <strong>Vista previa · Carta</strong>
        <button ref={abrirRef} type="button" className="lis-btn lis-btn-secondary lis-btn-sm" disabled={!documento} onClick={() => setPantallaCompleta(true)}>
          <Icono nombre="ampliar" size={14} /> Pantalla completa
        </button>
      </div>
      {estado}
      <div className="lis-preview-scroll" aria-busy={actualizando}>
        {documento ? paginas() : actualizando ? <CargaLaboratorio mensaje="Preparando el informe…" /> : <p className="lis-preview-empty">{error || (habilitada ? "El informe aparecerá aquí." : "La vista previa está disponible para órdenes en borrador.")}</p>}
      </div>
    </section>
    {pantallaCompleta && createPortal(<div className="lis-preview-dialog lis-no-print" role="dialog" aria-modal="true" aria-label="Vista previa del informe en pantalla completa">
      <div className="lis-preview-header">
        <strong>Vista previa · Carta · No aprobado</strong>
        <button ref={cerrarRef} type="button" className="lis-btn lis-btn-secondary lis-btn-sm" onClick={() => setPantallaCompleta(false)}>Cerrar (Esc)</button>
      </div>
      {estado}
      <div className="lis-preview-scroll" aria-busy={actualizando}>{paginas()}</div>
    </div>, document.body)}
  </>;
}
