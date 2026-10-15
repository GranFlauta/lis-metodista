/**
 * Vista de Detalle de Orden Clínica.
 * - Muestra cabecera completa, datos del paciente, estudios solicitados y grupos.
 * - Edición de cabecera (PATCH /api/ordenes/:id) con control de concurrencia optimista (fila_version).
 * - Descarte de borrador (DELETE /api/ordenes/:id / 204) con diálogo de confirmación.
 * - Control estricto de roles: ADMIN solo supervisa (auditoría ADMIN_VE_PRIVADO en backend),
 *   ocultando botones de edición y descarte.
 */

import React, { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  actualizarOrdenApi,
  descartarOrdenApi,
  obtenerOrdenApi,
  OrdenDetalle,
  OrdenUpdatePayload,
} from "../../api/ordenes";
import { ApiError } from "../../api/client";
import { useAuth } from "../auth/AuthProvider";

export const OrdenDetallePage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { usuario } = useAuth();
  const esAdmin = usuario?.rol === "ADMIN";

  const [orden, setOrden] = useState<OrdenDetalle | null>(null);
  const [cargando, setCargando] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [mensajeExito, setMensajeExito] = useState<string | null>(null);

  // Modal de edición de cabecera
  const [modalEditarAbierto, setModalEditarAbierto] = useState<boolean>(false);
  const [editOrigen, setEditOrigen] = useState<string>("");
  const [editMedico, setEditMedico] = useState<string>("");
  const [editPieza, setEditPieza] = useState<string>("");
  const [editTomaMuestra, setEditTomaMuestra] = useState<string>("");
  const [editEdadAnios, setEditEdadAnios] = useState<string>("");
  const [editEdadMeses, setEditEdadMeses] = useState<string>("0");
  const [guardandoEdicion, setGuardandoEdicion] = useState<boolean>(false);
  const [errorEdicion, setErrorEdicion] = useState<string | null>(null);

  // Modal de confirmación de descarte
  const [modalDescartarAbierto, setModalDescartarAbierto] = useState<boolean>(false);
  const [descartando, setDescartando] = useState<boolean>(false);

  // Cargar orden desde el backend
  const cargarOrden = useCallback(async () => {
    if (!id) return;
    setCargando(true);
    setError(null);
    try {
      const data = await obtenerOrdenApi(Number(id));
      setOrden(data);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        if (err.status === 404) {
          setError(
            esAdmin
              ? `No se encontró ninguna orden clínica con el identificador #${id}.`
              : "La orden no existe o pertenece a otro profesional bioquímico."
          );
        } else {
          setError(err.message);
        }
      } else {
        setError("Error al cargar la orden clínica.");
      }
    } finally {
      setCargando(false);
    }
  }, [id, esAdmin]);

  useEffect(() => {
    cargarOrden();
  }, [cargarOrden]);

  // Abrir modal de edición poblando valores iniciales
  const handleAbrirEdicion = () => {
    if (!orden) return;
    setEditOrigen(orden.origen_solicitud || "");
    setEditMedico(orden.medico_solicitante || "");
    setEditPieza(orden.pieza || "");
    // Formatear fecha y hora para datetime-local si existe
    if (orden.fecha_hora_toma_muestra) {
      const dt = new Date(orden.fecha_hora_toma_muestra);
      const iso = new Date(dt.getTime() - dt.getTimezoneOffset() * 60000)
        .toISOString()
        .slice(0, 16);
      setEditTomaMuestra(iso);
    } else {
      setEditTomaMuestra("");
    }
    setEditEdadAnios(orden.edad_anios !== null ? String(orden.edad_anios) : "");
    setEditEdadMeses(orden.edad_meses !== null ? String(orden.edad_meses) : "0");
    setErrorEdicion(null);
    setModalEditarAbierto(true);
  };

  // Guardar cambios de cabecera vía PATCH
  const handleGuardarEdicion = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!orden) return;

    setGuardandoEdicion(true);
    setErrorEdicion(null);

    const payload: OrdenUpdatePayload = {
      fila_version: orden.fila_version,
      origen_solicitud: editOrigen.trim() || null,
      medico_solicitante: editMedico.trim() || null,
      pieza: editPieza.trim() || null,
      fecha_hora_toma_muestra: editTomaMuestra || null,
    };

    // Solo actualizar edad si el paciente no tiene fecha de nacimiento registrada
    if (!orden.paciente.fecha_nacimiento && editEdadAnios !== "") {
      const aniosNum = parseInt(editEdadAnios, 10);
      if (!isNaN(aniosNum) && aniosNum >= 0 && aniosNum <= 130) {
        payload.edad_anios = aniosNum;
        payload.edad_meses = parseInt(editEdadMeses, 10) || 0;
      }
    }

    try {
      const ordenActualizada = await actualizarOrdenApi(orden.id, payload);
      setOrden(ordenActualizada);
      setModalEditarAbierto(false);
      setMensajeExito("Cabecera de la orden actualizada exitosamente.");
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        if (err.status === 409 && err.codigo === "CONFLICTO_VERSION") {
          setErrorEdicion(
            "Conflicto de concurrencia: la orden fue modificada por otro proceso. Por favor, recargue para ver la última versión."
          );
        } else {
          setErrorEdicion(err.message);
        }
      } else {
        setErrorEdicion("Error inesperado al guardar los cambios de la cabecera.");
      }
    } finally {
      setGuardandoEdicion(false);
    }
  };

  // Confirmar y ejecutar descarte de borrador vía DELETE (204)
  const handleConfirmarDescarte = async () => {
    if (!orden) return;
    setDescartando(true);
    setError(null);
    try {
      await descartarOrdenApi(orden.id);
      navigate("/ordenes", { replace: true });
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Error al descartar la orden.");
      }
      setModalDescartarAbierto(false);
    } finally {
      setDescartando(false);
    }
  };

  const obtenerClaseEstado = (estado: string) => {
    switch (estado) {
      case "INCOMPLETO":
        return "lis-status-incompleto";
      case "COMPLETO":
        return "lis-status-completo";
      case "PUBLICADA":
        return "lis-status-publicada";
      default:
        return "";
    }
  };

  if (cargando) {
    return (
      <div className="lis-page-container">
        <div className="lis-table-loading">
          <div className="lis-spinner" style={{ margin: "0 auto 0.5rem" }} />
          <p>Cargando información de la orden clínica...</p>
        </div>
      </div>
    );
  }

  if (error || !orden) {
    return (
      <div className="lis-page-container">
        <div className="lis-alert lis-alert-error" style={{ marginBottom: "1rem" }}>
          {error || "Orden no encontrada."}
        </div>
        <Link to="/ordenes" className="lis-btn lis-btn-primary">
          ← Volver a la bandeja de órdenes
        </Link>
      </div>
    );
  }

  return (
    <div className="lis-page-container">
      {/* Cabecera y Acciones */}
      <div className="lis-patient-header">
        <div>
          <Link
            to="/ordenes"
            className="lis-btn lis-btn-text"
            style={{ paddingLeft: 0, marginBottom: "0.25rem", display: "inline-block" }}
          >
            ← Volver a Órdenes
          </Link>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" }}>
            <h2>Orden #{orden.numero_orden_paciente}</h2>
            <span className={`lis-status-badge ${obtenerClaseEstado(orden.estado_trabajo)}`}>
              {orden.estado_trabajo}
            </span>
            {orden.bloqueada && (
              <span className="lis-status-badge lis-status-bloqueada">
                Bloqueada por concurrencia
              </span>
            )}
            <span
              className="lis-chip"
              title="Versión de control de concurrencia optimista (D2-07)"
              style={{ fontSize: "0.75rem" }}
            >
              v{orden.fila_version}
            </span>
          </div>
          <p className="lis-page-sub">
            Fecha de Solicitud: <strong>{orden.fecha_solicitud}</strong> — Creada el{" "}
            {new Date(orden.creado_en).toLocaleString()}
          </p>
        </div>

        {/* Acciones de la Orden */}
        <div style={{ display: "flex", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
          <Link
            to={`/ordenes/${orden.id}/captura`}
            className="lis-btn lis-btn-primary"
            title="Ingresar a la pantalla de captura analítica de resultados"
          >
            {esAdmin ? "Ver captura de resultados" : "Capturar resultados"}
          </Link>

          {!esAdmin && orden.estado_trabajo !== "PUBLICADA" && !orden.bloqueada && (
            <>
              <button
                type="button"
                className="lis-btn lis-btn-outline"
                onClick={handleAbrirEdicion}
                title="Editar datos de cabecera (origen, médico, toma de muestra)"
              >
                Editar cabecera
              </button>

              <button
                type="button"
                className="lis-btn lis-btn-danger"
                onClick={() => setModalDescartarAbierto(true)}
                title="Descartar permanentemente este borrador"
              >
                Descartar borrador
              </button>
            </>
          )}

          {esAdmin && (
            <span
              className="lis-chip"
              style={{
                backgroundColor: "#fef3c7",
                color: "#92400e",
                borderColor: "#fde68a",
                padding: "0.4rem 0.75rem",
              }}
            >
              Modo Auditoría Institucional (Solo Lectura)
            </span>
          )}
        </div>
      </div>

      {/* Mensaje de Éxito */}
      {mensajeExito && (
        <div
          className="lis-alert lis-alert-success"
          style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}
        >
          <span>{mensajeExito}</span>
          <button type="button" className="lis-btn lis-btn-text" onClick={() => setMensajeExito(null)}>
            ✕
          </button>
        </div>
      )}

      {/* Resumen del Paciente */}
      <div className="lis-table-card" style={{ marginBottom: "1.25rem" }}>
        <div
          style={{
            padding: "1rem 1.5rem",
            borderBottom: "1px solid var(--border-color)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <div>
            <h3 style={{ fontSize: "1.05rem", fontWeight: 700, margin: 0 }}>
              Paciente: {orden.paciente.apellido_paterno}{" "}
              {orden.paciente.apellido_materno ? `${orden.paciente.apellido_materno} ` : ""}
              {orden.paciente.nombres}
            </h3>
            <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
              {orden.paciente.ci
                ? `CI: ${orden.paciente.ci}${
                    orden.paciente.ci_complemento ? `-${orden.paciente.ci_complemento}` : ""
                  }`
                : "Sin CI registrado"}
            </span>
          </div>

          <Link
            to={`/pacientes/${orden.paciente.id}`}
            className="lis-btn lis-btn-text lis-btn-sm"
            style={{ fontWeight: 600 }}
          >
            Ver Ficha Completa →
          </Link>
        </div>

        <div className="lis-patient-summary" style={{ padding: "1.25rem 1.5rem" }}>
          <div className="lis-info-field">
            <span className="lis-info-label">Sexo Biológico</span>
            <span className="lis-info-value">
              {orden.paciente.sexo === "M" ? "Masculino (M)" : "Femenino (F)"}
            </span>
          </div>
          <div className="lis-info-field">
            <span className="lis-info-label">Fecha de Nacimiento</span>
            <span className="lis-info-value">
              {orden.paciente.fecha_nacimiento || "No registrada"}
            </span>
          </div>
          <div className="lis-info-field">
            <span className="lis-info-label">Edad en la Orden</span>
            <span className="lis-info-value">
              {orden.edad_anios !== null
                ? `${orden.edad_anios} años${
                    orden.edad_meses !== null && orden.edad_meses > 0
                      ? `, ${orden.edad_meses} meses`
                      : ""
                  }`
                : "No calculada"}
            </span>
          </div>
          <div className="lis-info-field">
            <span className="lis-info-label">Bioquímico Responsable</span>
            <span className="lis-info-value">
              {orden.autor.nombres} {orden.autor.apellido_paterno}
            </span>
          </div>
        </div>
      </div>

      {/* Datos Clínicos de Cabecera */}
      <div className="lis-table-card" style={{ marginBottom: "1.25rem" }}>
        <div style={{ padding: "1rem 1.5rem", borderBottom: "1px solid var(--border-color)" }}>
          <h3 style={{ fontSize: "1.05rem", fontWeight: 700, margin: 0 }}>
            Datos de la Orden y Muestra
          </h3>
        </div>

        <div className="lis-patient-summary" style={{ padding: "1.25rem 1.5rem" }}>
          <div className="lis-info-field">
            <span className="lis-info-label">Perfil de Catálogo</span>
            <span className="lis-info-value">
              {orden.perfil ? (
                <span className="lis-chip lis-chip-primary">
                  {orden.perfil.nombre} ({orden.perfil.codigo})
                </span>
              ) : (
                <span style={{ color: "var(--text-muted)" }}>Selección personalizada de estudios</span>
              )}
            </span>
          </div>

          <div className="lis-info-field">
            <span className="lis-info-label">Origen de la Solicitud</span>
            <span className="lis-info-value">{orden.origen_solicitud || "No especificado"}</span>
          </div>

          <div className="lis-info-field">
            <span className="lis-info-label">Médico Solicitante</span>
            <span className="lis-info-value">{orden.medico_solicitante || "No especificado"}</span>
          </div>

          <div className="lis-info-field">
            <span className="lis-info-label">Pieza / Sala / Cama</span>
            <span className="lis-info-value">{orden.pieza || "No especificada"}</span>
          </div>

          <div className="lis-info-field">
            <span className="lis-info-label">Toma de Muestra</span>
            <span className="lis-info-value">
              {orden.fecha_hora_toma_muestra
                ? new Date(orden.fecha_hora_toma_muestra).toLocaleString()
                : "Pendiente de registro"}
            </span>
          </div>

          <div className="lis-info-field">
            <span className="lis-info-label">Última Modificación</span>
            <span className="lis-info-value">
              {new Date(orden.actualizado_en).toLocaleString()}
            </span>
          </div>
        </div>
      </div>

      {/* Determinaciones y Estudios Solicitados */}
      <div className="lis-table-card" style={{ marginBottom: "1.5rem" }}>
        <div style={{ padding: "1rem 1.5rem", borderBottom: "1px solid var(--border-color)" }}>
          <h3 style={{ fontSize: "1.05rem", fontWeight: 700, margin: 0 }}>
            Estudios Solicitados ({orden.estudios.length})
          </h3>
          <p className="lis-page-sub" style={{ marginTop: "0.25rem" }}>
            Determinaciones congeladas según la versión del catálogo al momento de crear la orden.
          </p>
        </div>

        <div style={{ padding: "1.25rem 1.5rem" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.85rem" }}>
            {orden.estudios.map((est) => (
              <div
                key={est.codigo}
                style={{
                  padding: "0.85rem 1rem",
                  backgroundColor: "#f8fafc",
                  border: "1px solid var(--border-color)",
                  borderRadius: "8px",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "flex-start",
                  flexWrap: "wrap",
                  gap: "0.75rem",
                }}
              >
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    <span className="lis-chip lis-chip-primary" style={{ fontWeight: 800 }}>
                      {est.codigo}
                    </span>
                    <strong style={{ fontSize: "0.95rem" }}>{est.nombre}</strong>
                  </div>

                  {/* Grupos de Inmunoserología seleccionados */}
                  {est.grupos && est.grupos.length > 0 && (
                    <div style={{ marginTop: "0.5rem", paddingLeft: "0.25rem" }}>
                      <span
                        style={{
                          fontSize: "0.75rem",
                          fontWeight: 700,
                          color: "var(--text-muted)",
                          display: "block",
                          marginBottom: "0.25rem",
                        }}
                      >
                        Grupos Solicitados:
                      </span>
                      <div className="lis-chips-container">
                        {est.grupos.map((grp) => (
                          <span key={grp} className="lis-chip lis-chip-group">
                            {grp.replace(/_/g, " ")}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                <span
                  className="lis-status-badge lis-status-incompleto"
                  style={{ fontSize: "0.75rem" }}
                >
                  Pendiente de Análisis
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Tarjeta de Acceso a Captura de Resultados */}
      <div className="lis-table-card" style={{ padding: "1.25rem 1.5rem", marginBottom: "1.5rem", display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "1rem", backgroundColor: "#f0fdf4", border: "1px solid #bbf7d0" }}>
        <div>
          <h4 style={{ fontSize: "1.05rem", fontWeight: 700, color: "#166534", marginBottom: "0.25rem" }}>
            Captura de Determinaciones, Fórmulas Clínicas y Banderas
          </h4>
          <p style={{ margin: 0, fontSize: "0.9rem", color: "#15803d" }}>
            Ingrese resultados numéricos, cualitativos, cálculo síncrono en vivo, banderas biológicas por rango y control de completitud.
          </p>
        </div>
        <Link
          to={`/ordenes/${orden.id}/captura`}
          className="lis-btn lis-btn-primary"
          style={{ whiteSpace: "nowrap" }}
        >
          {esAdmin ? "Ver Captura de Resultados →" : "Ingresar a Captura de Resultados →"}
        </Link>
      </div>

      {/* Modal de Edición de Cabecera (PATCH) */}
      {modalEditarAbierto && (
        <div className="lis-modal-overlay" role="dialog" aria-modal="true" aria-labelledby="modal-editar-cabecera">
          <div className="lis-modal-card">
            <div className="lis-modal-header">
              <h3 id="modal-editar-cabecera">Editar Cabecera de la Orden</h3>
              <button
                type="button"
                className="lis-modal-close"
                onClick={() => setModalEditarAbierto(false)}
                disabled={guardandoEdicion}
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleGuardarEdicion}>
              <div className="lis-modal-body">
                {errorEdicion && <div className="lis-alert lis-alert-error">{errorEdicion}</div>}

                <div className="lis-form-group">
                  <label htmlFor="edit-origen">Origen de la Solicitud</label>
                  <input
                    id="edit-origen"
                    type="text"
                    value={editOrigen}
                    onChange={(e) => setEditOrigen(e.target.value)}
                    placeholder="Ej. Consulta Externa, Emergencias"
                    maxLength={100}
                  />
                </div>

                <div className="lis-form-group">
                  <label htmlFor="edit-medico">Médico Solicitante</label>
                  <input
                    id="edit-medico"
                    type="text"
                    value={editMedico}
                    onChange={(e) => setEditMedico(e.target.value)}
                    placeholder="Ej. Dra. Carmen Morales"
                    maxLength={150}
                  />
                </div>

                <div className="lis-form-group">
                  <label htmlFor="edit-pieza">Pieza / Cama / Sala</label>
                  <input
                    id="edit-pieza"
                    type="text"
                    value={editPieza}
                    onChange={(e) => setEditPieza(e.target.value)}
                    placeholder="Ej. Sala 4 - Cama 12"
                    maxLength={50}
                  />
                </div>

                <div className="lis-form-group">
                  <label htmlFor="edit-toma-muestra">Fecha y Hora de Toma de Muestra</label>
                  <input
                    id="edit-toma-muestra"
                    type="datetime-local"
                    value={editTomaMuestra}
                    onChange={(e) => setEditTomaMuestra(e.target.value)}
                  />
                </div>

                {/* Si el paciente no tiene fecha de nacimiento, se permite editar la edad */}
                {!orden.paciente.fecha_nacimiento && (
                  <div className="lis-form-row">
                    <div className="lis-form-group">
                      <label htmlFor="edit-edad-anios">Edad en Años *</label>
                      <input
                        id="edit-edad-anios"
                        type="number"
                        min="0"
                        max="130"
                        value={editEdadAnios}
                        onChange={(e) => setEditEdadAnios(e.target.value)}
                      />
                    </div>
                    <div className="lis-form-group">
                      <label htmlFor="edit-edad-meses">Edad en Meses</label>
                      <input
                        id="edit-edad-meses"
                        type="number"
                        min="0"
                        max="11"
                        value={editEdadMeses}
                        onChange={(e) => setEditEdadMeses(e.target.value)}
                      />
                    </div>
                  </div>
                )}
              </div>

              <div className="lis-modal-footer">
                <button
                  type="button"
                  className="lis-btn lis-btn-secondary"
                  onClick={() => setModalEditarAbierto(false)}
                  disabled={guardandoEdicion}
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="lis-btn lis-btn-primary"
                  disabled={guardandoEdicion}
                >
                  {guardandoEdicion ? "Guardando..." : "Guardar Cambios"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal de Confirmación de Descarte (DELETE / 204) */}
      {modalDescartarAbierto && (
        <div
          className="lis-modal-overlay"
          role="dialog"
          aria-modal="true"
          aria-labelledby="modal-descartar-detalle-title"
        >
          <div className="lis-modal-card lis-modal-alert">
            <div className="lis-modal-header">
              <h3 id="modal-descartar-detalle-title">Confirmar Descarte de Borrador</h3>
              <button
                type="button"
                className="lis-modal-close"
                onClick={() => setModalDescartarAbierto(false)}
                disabled={descartando}
              >
                ✕
              </button>
            </div>

            <div className="lis-modal-body">
              <p>
                ¿Está seguro de descartar la <strong>Orden #{orden.numero_orden_paciente}</strong> de{" "}
                <strong>
                  {orden.paciente.apellido_paterno} {orden.paciente.nombres}
                </strong>?
              </p>
              <p style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                Esta acción eliminará físicamente la orden y registrará un evento de trazabilidad legal
                en la tabla de borradores descartados. No podrá recuperarse.
              </p>
            </div>

            <div className="lis-modal-footer">
              <button
                type="button"
                className="lis-btn lis-btn-secondary"
                onClick={() => setModalDescartarAbierto(false)}
                disabled={descartando}
              >
                Cancelar
              </button>
              <button
                type="button"
                className="lis-btn lis-btn-danger"
                onClick={handleConfirmarDescarte}
                disabled={descartando}
              >
                {descartando ? "Descartando..." : "Sí, Descartar Borrador"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
