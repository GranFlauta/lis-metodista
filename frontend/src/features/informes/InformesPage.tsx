/**
 * Vista de Informes Oficiales Emitidos (Fase 4).
 * Permite buscar, filtrar y gestionar informes oficiales con folios inmutables.
 */
import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getInformes, moverAPapelera, crearNuevaVersion, InformeItem } from "../../api/informes";
import { useAuth } from "../auth/AuthProvider";

export const InformesPage: React.FC = () => {
  const { usuario } = useAuth();
  const navigate = useNavigate();

  const [informes, setInformes] = useState<InformeItem[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filtros
  const [busqueda, setBusqueda] = useState("");
  const [filtroEstado, setFiltroEstado] = useState("VIGENTE");

  // Modal para Justificativo (Papelera o Nueva Versión)
  const [modalAccion, setModalAccion] = useState<"papelera" | "version" | null>(null);
  const [informeSeleccionado, setInformeSeleccionado] = useState<InformeItem | null>(null);
  const [justificativoInput, setJustificativoInput] = useState("");
  const [guardandoAccion, setGuardandoAccion] = useState(false);
  const [errorModal, setErrorModal] = useState<string | null>(null);

  const cargarInformes = async () => {
    setCargando(true);
    setError(null);
    try {
      const data = await getInformes({
        q: busqueda.trim() || undefined,
        estado: filtroEstado || undefined,
      });
      setInformes(data);
    } catch (err: any) {
      setError(err?.mensaje || "Error al cargar los informes oficiales.");
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => {
    cargarInformes();
  }, [filtroEstado]);

  const handleBuscar = (e: React.FormEvent) => {
    e.preventDefault();
    cargarInformes();
  };

  const handleAbrirModal = (informe: InformeItem, accion: "papelera" | "version") => {
    setInformeSeleccionado(informe);
    setModalAccion(accion);
    setJustificativoInput("");
    setErrorModal(null);
  };

  const handleEjecutarAccion = async () => {
    if (!informeSeleccionado || !modalAccion) return;
    if (justificativoInput.trim().length < 5) {
      setErrorModal("El justificativo debe tener al menos 5 caracteres.");
      return;
    }

    setGuardandoAccion(true);
    setErrorModal(null);
    try {
      if (modalAccion === "papelera") {
        await moverAPapelera(informeSeleccionado.folio, justificativoInput.trim());
      } else if (modalAccion === "version") {
        await crearNuevaVersion(informeSeleccionado.folio, justificativoInput.trim());
      }
      setModalAccion(null);
      setInformeSeleccionado(null);
      cargarInformes();
    } catch (err: any) {
      setErrorModal(err?.mensaje || "Error al procesar la acción.");
    } finally {
      setGuardandoAccion(false);
    }
  };

  const renderBadgeEstado = (estado: string) => {
    switch (estado) {
      case "VIGENTE":
        return <span className="lis-badge" style={{ backgroundColor: "#dcfce7", color: "#166534" }}>Vigente</span>;
      case "DESPLAZADO":
        return <span className="lis-badge" style={{ backgroundColor: "#f1f5f9", color: "#475569" }}>Desplazado</span>;
      case "RECICLAJE":
        return <span className="lis-badge" style={{ backgroundColor: "#fef3c7", color: "#92400e" }}>En Reciclaje</span>;
      case "PAPELERA":
        return <span className="lis-badge" style={{ backgroundColor: "#fee2e2", color: "#991b1b" }}>En Papelera</span>;
      default:
        return <span className="lis-badge">{estado}</span>;
    }
  };

  return (
    <div className="lis-page-container">
      <div className="lis-page-header">
        <div>
          <h1 className="lis-page-title">Informes Clínicos Oficiales</h1>
          <p className="lis-page-subtitle">
            Documentos médicos emitidos con folio correlativo inmutable y trazabilidad criptográfica SHA-256.
          </p>
        </div>
      </div>

      {/* Barra de Filtros y Búsqueda */}
      <div className="lis-card" style={{ marginBottom: "16px", padding: "12px 16px" }}>
        <form onSubmit={handleBuscar} style={{ display: "flex", gap: "12px", alignItems: "center", flexWrap: "wrap" }}>
          <div style={{ flex: "1 1 280px" }}>
            <input
              type="text"
              className="lis-input"
              placeholder="Buscar por Folio (ej. 2026-000001), CI o nombre de paciente…"
              value={busqueda}
              onChange={(e) => setBusqueda(e.target.value)}
            />
          </div>

          <div style={{ width: "160px" }}>
            <select
              className="lis-select"
              value={filtroEstado}
              onChange={(e) => setFiltroEstado(e.target.value)}
            >
              <option value="VIGENTE">Solo Vigentes</option>
              <option value="RECICLAJE">En Reciclaje</option>
              <option value="DESPLAZADO">Desplazados</option>
              <option value="">Todos los Estados</option>
            </select>
          </div>

          <button type="submit" className="lis-btn lis-btn-primary">
            Buscar
          </button>
          <button
            type="button"
            className="lis-btn lis-btn-outline"
            onClick={() => {
              setBusqueda("");
              setFiltroEstado("VIGENTE");
            }}
          >
            Limpiar
          </button>
        </form>
      </div>

      {error && (
        <div className="lis-alert lis-alert-error" style={{ marginBottom: "16px" }}>
          {error}
        </div>
      )}

      {/* Tabla de Informes */}
      <div className="lis-card" style={{ padding: 0, overflow: "hidden" }}>
        {cargando ? (
          <div style={{ padding: "40px", textAlign: "center", color: "var(--text-muted)" }}>
            Cargando informes oficiales…
          </div>
        ) : informes.length === 0 ? (
          <div style={{ padding: "40px", textAlign: "center", color: "var(--text-muted)" }}>
            No se encontraron informes oficiales con los criterios seleccionados.
          </div>
        ) : (
          <table className="lis-table">
            <thead>
              <tr>
                <th>Folio Oficial</th>
                <th>Versión</th>
                <th>Paciente</th>
                <th>CI</th>
                <th>Fecha Emisión</th>
                <th>Firmante Responsable</th>
                <th>Estado</th>
                <th style={{ textAlign: "right" }}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {informes.map((inf) => {
                return (
                  <tr key={inf.id_informe}>
                    <td style={{ fontWeight: 700, fontFamily: "monospace", color: "var(--primary)" }}>
                      {inf.folio}
                    </td>
                    <td>
                      <span className="lis-chip" style={{ fontSize: "11px", fontWeight: 600 }}>
                        V{inf.numero_version}
                      </span>
                    </td>
                    <td style={{ fontWeight: 600 }}>{inf.paciente_nombre}</td>
                    <td style={{ color: "var(--text-muted)", fontSize: "12px" }}>{inf.paciente_ci || "S/CI"}</td>
                    <td style={{ fontSize: "12.5px" }}>
                      {new Date(inf.publicado_en).toLocaleDateString("es-BO", {
                        day: "2-digit",
                        month: "2-digit",
                        year: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </td>
                    <td style={{ fontSize: "12.5px" }}>{inf.firmante_nombre}</td>
                    <td>{renderBadgeEstado(inf.estado)}</td>
                    <td style={{ textAlign: "right" }}>
                      <div style={{ display: "inline-flex", gap: "6px" }}>
                        <Link
                          to={`/informes/${inf.folio}`}
                          className="lis-btn lis-btn-sm lis-btn-outline"
                          title="Ver informe oficial listo para imprimir"
                        >
                          👁️ Ver
                        </Link>

                        {inf.estado === "VIGENTE" && inf.numero_version < 3 && (
                          <button
                            type="button"
                            className="lis-btn lis-btn-sm lis-btn-outline"
                            onClick={() => handleAbrirModal(inf, "version")}
                            title="Emitir nueva versión corregida (V2/V3)"
                          >
                            ➕ V{inf.numero_version + 1}
                          </button>
                        )}

                        {inf.estado === "VIGENTE" && (
                          <button
                            type="button"
                            className="lis-btn lis-btn-sm lis-btn-outline"
                            style={{ color: "var(--error)", borderColor: "#fca5a5" }}
                            onClick={() => handleAbrirModal(inf, "papelera")}
                            title="Enviar a papelera con justificación auditada"
                          >
                            🗑️
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Modal de Justificación Auditada (Papelera / Nueva Versión) */}
      {modalAccion && informeSeleccionado && (
        <div className="lis-modal-overlay">
          <div className="lis-modal-card" style={{ maxWidth: "520px" }}>
            <div className="lis-modal-header">
              <h3 className="lis-modal-title">
                {modalAccion === "papelera"
                  ? `Enviar Informe ${informeSeleccionado.folio} a la Papelera`
                  : `Emitir Nueva Versión V${informeSeleccionado.numero_version + 1} para Folio ${informeSeleccionado.folio}`}
              </h3>
              <button
                type="button"
                className="lis-btn-icon"
                onClick={() => setModalAccion(null)}
                disabled={guardandoAccion}
              >
                ✕
              </button>
            </div>

            <div className="lis-modal-body">
              <p style={{ fontSize: "13px", color: "var(--text-muted)", marginBottom: "12px" }}>
                {modalAccion === "papelera"
                  ? "El informe pasará a la papelera lógica conservando su folio oficial. El motivo registrado quedará asentado permanentemente en la traza de auditoría."
                  : `Se generará la versión V${informeSeleccionado.numero_version + 1}. La versión actual quedará marcada como DESPLAZADA y se preservará el historial.`}
              </p>

              {errorModal && (
                <div className="lis-alert lis-alert-error" style={{ marginBottom: "12px", fontSize: "12.5px" }}>
                  {errorModal}
                </div>
              )}

              <div className="lis-form-group">
                <label className="lis-label" htmlFor="justificativo-input">
                  Motivo o justificación auditada <span style={{ color: "var(--error)" }}>*</span>:
                </label>
                <textarea
                  id="justificativo-input"
                  className="lis-textarea"
                  rows={4}
                  placeholder="Detalle de forma clara el motivo clínico o administrativo (mínimo 5 caracteres)…"
                  value={justificativoInput}
                  onChange={(e) => setJustificativoInput(e.target.value)}
                  disabled={guardandoAccion}
                />
              </div>
            </div>

            <div className="lis-modal-footer">
              <button
                type="button"
                className="lis-btn lis-btn-outline"
                onClick={() => setModalAccion(null)}
                disabled={guardandoAccion}
              >
                Cancelar
              </button>
              <button
                type="button"
                className={`lis-btn ${modalAccion === "papelera" ? "lis-btn-danger" : "lis-btn-primary"}`}
                onClick={handleEjecutarAccion}
                disabled={guardandoAccion || justificativoInput.trim().length < 5}
              >
                {guardandoAccion ? "Procesando…" : modalAccion === "papelera" ? "Confirmar Papelera" : "Emitir Versión"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
