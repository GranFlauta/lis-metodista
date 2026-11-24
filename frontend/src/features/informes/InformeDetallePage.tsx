/** El informe oficial utiliza exclusivamente el documento renderizado por el backend. */
import React, { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { descargarPdfInforme, getInforme, getVistaInforme, InformeDetalle } from "../../api/informes";
import { VistaPreviaInforme as PaginasInforme } from "../../api/resultados";
import { ApiError } from "../../api/client";
import { CargaLaboratorio } from "../../components/MarcaLaboratorio";
import { Icono } from "../../components/Icono";

interface CargaInforme {
  clave: string;
  informe: InformeDetalle | null;
  pdfUrl: string | null;
  paginas: PaginasInforme | null;
  cargando: boolean;
  error: string | null;
}

export const InformeDetallePage: React.FC = () => {
  const { folio } = useParams<{ folio: string }>();
  const [versionSeleccionada, setVersionSeleccionada] = useState<number>();
  const [reintento, setReintento] = useState(0);
  const [modalHistorialAbierto, setModalHistorialAbierto] = useState(false);
  const pdfFrameRef = useRef<HTMLIFrameElement>(null);
  const clave = `${folio}|${versionSeleccionada ?? "vigente"}|${reintento}`;
  const [carga, setCarga] = useState<CargaInforme>({ clave: "", informe: null, pdfUrl: null, paginas: null, cargando: true, error: null });

  useEffect(() => {
    if (!folio) return;
    const controller = new AbortController();
    let urlTemporal: string | null = null;
    const inicial: CargaInforme = { clave, informe: null, pdfUrl: null, paginas: null, cargando: true, error: null };
    setCarga(inicial);
    setModalHistorialAbierto(false);
    async function cargar() {
      try {
        const informe = await getInforme(folio!, versionSeleccionada, controller.signal);
        if (controller.signal.aborted) return;
        setCarga({ ...inicial, informe });
        // Fijar la versión resuelta evita mezclar metadatos y documentos si cambia la vigente.
        if (informe.estado === "VIGENTE") {
          const blob = await descargarPdfInforme(informe.folio, informe.numero_version, controller.signal);
          if (controller.signal.aborted) return;
          urlTemporal = URL.createObjectURL(blob);
          setCarga({ ...inicial, informe, pdfUrl: urlTemporal, cargando: false });
        } else {
          const paginas = await getVistaInforme(informe.folio, informe.numero_version, controller.signal);
          if (!controller.signal.aborted) setCarga({ ...inicial, informe, paginas, cargando: false });
        }
      } catch (err) {
        if (!controller.signal.aborted) setCarga((anterior) => ({ ...anterior, cargando: false,
          error: err instanceof ApiError ? err.message : "No se pudo cargar el documento. Intente nuevamente." }));
      }
    }
    void cargar();
    return () => {
      controller.abort();
      if (urlTemporal) URL.revokeObjectURL(urlTemporal);
    };
  }, [folio, versionSeleccionada, reintento, clave]);

  // Un cambio de folio o versión nunca muestra el documento de la consulta anterior.
  const actual = carga.clave === clave ? carga : null;
  const informe = actual?.informe;
  if (!informe) return <div className="lis-page-container">
    {actual?.error ? <div className="lis-alert lis-alert-error" role="alert">{actual.error}
      <button className="lis-btn lis-btn-outline lis-btn-sm" onClick={() => setReintento((n) => n + 1)}>Reintentar</button>
    </div> : <CargaLaboratorio mensaje="Cargando informe oficial…" />}
    <Link to="/informes" className="lis-btn lis-btn-outline">Volver a informes</Link>
  </div>;

  const puedeImprimir = informe.estado === "VIGENTE";
  return <div className="lis-page-container lis-informe-view">
    <div className="lis-informe-actions-bar lis-no-print">
      <div className="lis-informe-toolbar-group">
        <Link to="/informes" className="lis-btn lis-btn-outline lis-btn-sm">← Volver</Link>
        <strong>Folio {informe.folio}</strong>
        {informe.versiones_disponibles.length > 1 && <label className="lis-version-selector">Versión
          <select className="lis-select" value={informe.numero_version} onChange={(event) => setVersionSeleccionada(Number(event.target.value))}>
            {informe.versiones_disponibles.map((v) => <option key={v.numero_version} value={v.numero_version}>V{v.numero_version} ({v.estado})</option>)}
          </select>
        </label>}
        <span className="lis-badge lis-report-state">{informe.estado}</span>
        {informe.es_urgencia && <span className="lis-badge lis-report-urgency"><Icono nombre="alerta" size={13} /> Urgencia</span>}
      </div>
      <div className="lis-informe-toolbar-group">
        <button className="lis-btn lis-btn-outline lis-btn-sm" onClick={() => setModalHistorialAbierto(true)}>
          <Icono nombre="restaurar" size={14} /> Trazabilidad ({informe.eventos.length})
        </button>
        {puedeImprimir ? <>
          {actual?.pdfUrl && <a className="lis-btn lis-btn-outline lis-btn-sm" href={actual.pdfUrl} download={`informe-${informe.folio}.pdf`}>Descargar PDF</a>}
          <button className="lis-btn lis-btn-primary lis-btn-sm" disabled={!actual?.pdfUrl || actual.cargando}
            onClick={() => pdfFrameRef.current?.contentWindow?.print()}><Icono nombre="imprimir" size={14} /> Imprimir informe</button>
        </> : <span className="lis-input-hint">Impresión bloqueada · {informe.estado}</span>}
      </div>
    </div>

    <section className="lis-official-document lis-no-print" aria-label="Informe oficial" aria-busy={actual?.cargando}>
      {actual?.cargando && <CargaLaboratorio mensaje="Preparando el documento…" />}
      {actual?.error && <div className="lis-alert lis-alert-error" role="alert">{actual.error}
        <button className="lis-btn lis-btn-outline lis-btn-sm" onClick={() => setReintento((n) => n + 1)}>Reintentar</button>
      </div>}
      {actual?.pdfUrl && <iframe ref={pdfFrameRef} className="lis-official-pdf-frame" title={`Informe oficial ${informe.folio}`}
        src={`${actual.pdfUrl}#toolbar=0&navpanes=0&view=FitH`} />}
      {actual?.paginas && <div className="lis-official-pages">
        {actual.paginas.paginas.map((pagina) => <figure className="lis-preview-page" key={pagina.numero}>
          <img src={pagina.imagen} width={pagina.ancho} height={pagina.alto} alt={`Informe ${informe.folio}, página ${pagina.numero}`} draggable={false} />
        </figure>)}
      </div>}
    </section>

    {modalHistorialAbierto && <div className="lis-modal-overlay lis-no-print" role="dialog" aria-modal="true" aria-labelledby="historial-titulo"
      onKeyDown={(event) => { if (event.key === "Escape") setModalHistorialAbierto(false); }}>
      <div className="lis-modal-card" style={{ maxWidth: 600 }}>
        <div className="lis-modal-header"><h3 id="historial-titulo">Trazabilidad del folio {informe.folio}</h3>
          <button className="lis-modal-close" aria-label="Cerrar trazabilidad" onClick={() => setModalHistorialAbierto(false)}>✕</button>
        </div>
        <div className="lis-modal-body"><div className="lis-table-responsive">
          <table className="lis-table lis-table-dense" aria-label="Trazabilidad del informe">
            <thead><tr><th scope="col">Acción</th><th scope="col">Fecha y hora</th><th scope="col">Profesional</th><th scope="col">Versión</th><th scope="col">Justificativo</th></tr></thead>
            <tbody>{informe.eventos.map((evento) => <tr key={evento.id_evento}>
              <td className="lis-cell-bold">{evento.accion}</td>
              <td><time dateTime={evento.creado_en}>{new Date(evento.creado_en).toLocaleString("es-BO", { timeZone: "America/La_Paz" })}</time></td>
              <td>{evento.usuario_nombre}</td><td>{evento.numero_version ? `V${evento.numero_version}` : "—"}</td>
              <td>{evento.justificativo || "—"}</td>
            </tr>)}</tbody>
          </table>
        </div></div>
        <div className="lis-modal-footer"><button autoFocus className="lis-btn lis-btn-outline" onClick={() => setModalHistorialAbierto(false)}>Cerrar</button></div>
      </div>
    </div>}
  </div>;
};
