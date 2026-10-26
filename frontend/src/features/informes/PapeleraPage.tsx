/**
 * Vista de Papelera y Reciclaje de Informes Oficiales (Fase 4).
 * Permite auditar qué informes fueron descartados, quién lo hizo, cuándo y por qué motivo.
 * Permite restaurar a estado 'RECICLAJE' con justificación obligatoria.
 */
import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getPapelera, restaurarDePapelera, PapeleraItem } from "../../api/informes";

export const PapeleraPage: React.FC = () => {
  const [items, setItems] = useState<PapeleraItem[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Búsqueda
  const [busqueda, setBusqueda] = useState("");

  // Modal Restauración
  const [itemRestaurar, setItemRestaurar] = useState<PapeleraItem | null>(null);
  const [motivoRestauracion, setMotivoRestauracion] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [errorModal, setErrorModal] = useState<string | null>(null);

  const cargarPapelera = async () => {
    setCargando(true);
    setError(null);
    try {
      const data = await getPapelera({ q: busqueda.trim() || undefined });
      setItems(data);
    } catch (err: any) {
      setError(err?.mensaje || "Error al cargar la papelera.");
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => {
    cargarPapelera();
  }, []);

  const handleBuscar = (e: React.FormEvent) => {
    e.preventDefault();
    cargarPapelera();
  };

  const handleAbrirRestaurar = (item: PapeleraItem) => {
    setItemRestaurar(item);
    setMotivoRestauracion("");
    setErrorModal(null);
  };

  const handleEjecutarRestaurar = async () => {
    if (!itemRestaurar) return;
    if (motivoRestauracion.trim().length < 5) {
      setErrorModal("El justificativo de restauración debe tener al menos 5 caracteres.");
      return;
    }

    setGuardando(true);
    setErrorModal(null);
    try {
      await restaurarDePapelera(itemRestaurar.folio, motivoRestauracion.trim());
      setItemRestaurar(null);
      cargarPapelera();
    } catch (err: any) {
      setErrorModal(err?.mensaje || "Error al restaurar el informe.");
    } finally {
      setGuardando(false);
    }
  };

  return (
    <div className="lis-page-container">
      <div className="lis-page-header">
        <div>
          <h1 className="lis-page-title">Papelera y Reciclaje de Informes</h1>
          <p className="lis-page-subtitle">
            Auditoría de informes oficiales desplazados o enviados a papelera con justificación registrada.
          </p>
        </div>
      </div>

      {/* Alerta explicativa de inmutabilidad */}
      <div
        className="lis-alert lis-alert-info"
        style={{ marginBottom: "16px", display: "flex", alignItems: "flex-start", gap: "10px" }}
      >
        <span style={{ fontSize: "18px" }}>ℹ️</span>
        <div style={{ fontSize: "13px", lineHeight: "1.5" }}>
          <strong>Política de Trazabilidad e Inmutabilidad (D-73 / D-74):</strong> Los informes médicos con folio oficial <strong>nunca se eliminan físicamente</strong> de la base de datos.
          Al enviarse a la papelera, conservan su folio y su huella SHA-256. La restauración cambia su estado a <code>RECICLAJE</code> (permitiendo su visualización pero bloqueando la reimpresión oficial).
        </div>
      </div>

      {/* Barra de Búsqueda */}
      <div className="lis-card" style={{ marginBottom: "16px", padding: "12px 16px" }}>
        <form onSubmit={handleBuscar} style={{ display: "flex", gap: "12px", alignItems: "center" }}>
          <input
            type="text"
            className="lis-input"
            style={{ flex: 1 }}
            placeholder="Filtrar papelera por Folio, CI o nombre de paciente…"
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
          />
          <button type="submit" className="lis-btn lis-btn-primary">
            Buscar
          </button>
        </form>
      </div>

      {error && (
        <div className="lis-alert lis-alert-error" style={{ marginBottom: "16px" }}>
          {error}
        </div>
      )}

      {/* Tabla de Papelera */}
      <div className="lis-card" style={{ padding: 0, overflow: "hidden" }}>
        {cargando ? (
          <div style={{ padding: "40px", textAlign: "center", color: "var(--text-muted)" }}>
            Cargando papelera…
          </div>
        ) : items.length === 0 ? (
          <div style={{ padding: "40px", textAlign: "center", color: "var(--text-muted)" }}>
            No hay informes en papelera ni en reciclaje actualmente.
          </div>
        ) : (
          <table className="lis-table">
            <thead>
              <tr>
                <th>Folio</th>
                <th>Versión</th>
                <th>Paciente</th>
                <th>CI</th>
                <th>Fecha Modificación</th>
                <th>Firmante Original</th>
                <th>Motivo Auditado (Justificación)</th>
                <th>Estado</th>
                <th style={{ textAlign: "right" }}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {items.map((it) => (
                <tr key={it.id_informe}>
                  <td style={{ fontWeight: 700, fontFamily: "monospace", color: "var(--primary)" }}>
                    {it.folio}
                  </td>
                  <td>
                    <span className="lis-chip" style={{ fontSize: "11px" }}>
                      V{it.numero_version}
                    </span>
                  </td>
                  <td style={{ fontWeight: 600 }}>{it.paciente_nombre}</td>
                  <td style={{ color: "var(--text-muted)", fontSize: "12px" }}>{it.paciente_ci || "S/CI"}</td>
                  <td style={{ fontSize: "12px" }}>
                    {new Date(it.fecha_papelera).toLocaleDateString("es-BO", {
                      day: "2-digit",
                      month: "2-digit",
                      year: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </td>
                  <td style={{ fontSize: "12.5px" }}>{it.firmante_nombre}</td>
                  <td style={{ maxWidth: "260px", fontSize: "12.5px", color: "#334155" }}>
                    <div style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }} title={it.motivo_papelera || ""}>
                      {it.motivo_papelera || "Sin justificación registrada"}
                    </div>
                  </td>
                  <td>
                    {it.estado === "PAPELERA" ? (
                      <span className="lis-badge" style={{ backgroundColor: "#fee2e2", color: "#991b1b" }}>
                        Papelera
                      </span>
                    ) : (
                      <span className="lis-badge" style={{ backgroundColor: "#fef3c7", color: "#92400e" }}>
                        Reciclaje
                      </span>
                    )}
                  </td>
                  <td style={{ textAlign: "right" }}>
                    <div style={{ display: "inline-flex", gap: "6px" }}>
                      <Link
                        to={`/informes/${it.folio}`}
                        className="lis-btn lis-btn-sm lis-btn-outline"
                        title="Ver detalle del informe"
                      >
                        👁️ Ver
                      </Link>

                      {it.estado === "PAPELERA" && (
                        <button
                          type="button"
                          className="lis-btn lis-btn-sm lis-btn-outline"
                          style={{ color: "var(--success)", borderColor: "#86efac" }}
                          onClick={() => handleAbrirRestaurar(it)}
                          title="Restaurar a estado Reciclaje con justificativo"
                        >
                          ♻️ Restaurar
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Modal Restaurar */}
      {itemRestaurar && (
        <div className="lis-modal-overlay">
          <div className="lis-modal-card" style={{ maxWidth: "500px" }}>
            <div className="lis-modal-header">
              <h3 className="lis-modal-title">
                Restaurar Informe {itemRestaurar.folio} a RECICLAJE
              </h3>
              <button
                type="button"
                className="lis-btn-icon"
                onClick={() => setItemRestaurar(null)}
                disabled={guardando}
              >
                ✕
              </button>
            </div>

            <div className="lis-modal-body">
              <p style={{ fontSize: "13px", color: "var(--text-muted)", marginBottom: "12px" }}>
                El informe pasará al estado <code>RECICLAJE</code>. Podrá ser consultado en pantalla pero la reimpresión oficial quedará bloqueada según la norma clínica D-74.
              </p>

              {errorModal && (
                <div className="lis-alert lis-alert-error" style={{ marginBottom: "12px", fontSize: "12.5px" }}>
                  {errorModal}
                </div>
              )}

              <div className="lis-form-group">
                <label className="lis-label" htmlFor="motivo-restauracion-input">
                  Motivo de restauración obligatoria <span style={{ color: "var(--error)" }}>*</span>:
                </label>
                <textarea
                  id="motivo-restauracion-input"
                  className="lis-textarea"
                  rows={4}
                  placeholder="Explique el motivo por el cual se recupera este informe clínico (mínimo 5 caracteres)…"
                  value={motivoRestauracion}
                  onChange={(e) => setMotivoRestauracion(e.target.value)}
                  disabled={guardando}
                />
              </div>
            </div>

            <div className="lis-modal-footer">
              <button
                type="button"
                className="lis-btn lis-btn-outline"
                onClick={() => setItemRestaurar(null)}
                disabled={guardando}
              >
                Cancelar
              </button>
              <button
                type="button"
                className="lis-btn lis-btn-primary"
                onClick={handleEjecutarRestaurar}
                disabled={guardando || motivoRestauracion.trim().length < 5}
              >
                {guardando ? "Restaurando…" : "Confirmar Restauración"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
