/**
 * Ficha Clínica Detallada del Paciente.
 * PROMPT_FASE_2.md §9:
 * - Ficha del paciente con sus datos clínicos completos.
 * - Botón "Editar" (oculto para ADMIN).
 * - Sección de órdenes clínicas asociadas y botón "Nueva Orden".
 */

import React, { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { obtenerPacienteApi, PacienteDetalle } from "../../api/pacientes";
import { listarOrdenesApi, OrdenListItem } from "../../api/ordenes";
import { ApiError } from "../../api/client";
import { useAuth } from "../auth/AuthProvider";
import { PacienteFormModal } from "./PacienteFormModal";

export const PacienteDetallePage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { usuario } = useAuth();
  const esAdmin = usuario?.rol === "ADMIN";

  const [paciente, setPaciente] = useState<PacienteDetalle | null>(null);
  const [cargando, setCargando] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Órdenes del paciente
  const [ordenes, setOrdenes] = useState<OrdenListItem[]>([]);
  const [cargandoOrdenes, setCargandoOrdenes] = useState<boolean>(false);

  const [modalEditarAbierto, setModalEditarAbierto] = useState<boolean>(false);

  const cargarPaciente = useCallback(async () => {
    if (!id) return;
    setCargando(true);
    setError(null);
    try {
      const data = await obtenerPacienteApi(Number(id));
      setPaciente(data);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        if (err.status === 404) {
          setError(`No se encontró ningún paciente con el identificador #${id}.`);
        } else {
          setError(err.message);
        }
      } else {
        setError("Error al cargar la ficha clínica del paciente.");
      }
    } finally {
      setCargando(false);
    }
  }, [id]);

  const cargarOrdenesPaciente = useCallback(async () => {
    if (!id) return;
    setCargandoOrdenes(true);
    try {
      const resp = await listarOrdenesApi({ id_paciente: Number(id) });
      setOrdenes(resp.items);
    } catch {
      // Silencioso o manejo suave
    } finally {
      setCargandoOrdenes(false);
    }
  }, [id]);

  useEffect(() => {
    cargarPaciente();
    cargarOrdenesPaciente();
  }, [cargarPaciente, cargarOrdenesPaciente]);

  const calcularEdadTexto = (fn: string | null): string => {
    if (!fn) return "No registrada";
    const fecha = new Date(fn + "T00:00:00");
    const hoy = new Date();
    let anios = hoy.getFullYear() - fecha.getFullYear();
    const m = hoy.getMonth() - fecha.getMonth();
    if (m < 0 || (m === 0 && hoy.getDate() < fecha.getDate())) {
      anios--;
    }
    return `${Math.max(0, anios)} años cumplidos`;
  };

  const handleGuardado = (pacienteActualizado: PacienteDetalle) => {
    setPaciente(pacienteActualizado);
    setModalEditarAbierto(false);
  };

  if (cargando) {
    return (
      <div className="lis-page-container">
        <div className="lis-table-loading">
          <div className="lis-spinner" style={{ margin: "0 auto 0.5rem" }} />
          <p>Cargando ficha del paciente...</p>
        </div>
      </div>
    );
  }

  if (error || !paciente) {
    return (
      <div className="lis-page-container">
        <div className="lis-alert lis-alert-error" style={{ marginBottom: "1rem" }}>
          {error || "Paciente no encontrado."}
        </div>
        <Link to="/pacientes" className="lis-btn lis-btn-primary">
          ← Volver al listado de pacientes
        </Link>
      </div>
    );
  }

  return (
    <div className="lis-page-container">
      {/* Navegación y Cabecera */}
      <div className="lis-patient-header">
        <div>
          <Link
            to="/pacientes"
            className="lis-btn lis-btn-text"
            style={{ paddingLeft: 0, marginBottom: "0.25rem", display: "inline-block" }}
          >
            ← Volver a Pacientes
          </Link>
          <h2>
            {paciente.apellido_paterno} {paciente.apellido_materno || ""}, {paciente.nombres}
          </h2>
          <p className="lis-page-sub">
            Ficha Clínica de Paciente #{paciente.id} — Registrado el{" "}
            {new Date(paciente.creado_en).toLocaleDateString()}
          </p>
        </div>

        <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
          {!esAdmin && (
            <>
              <button
                type="button"
                className="lis-btn lis-btn-outline"
                onClick={() => setModalEditarAbierto(true)}
              >
                Editar Ficha
              </button>

              <button
                type="button"
                className="lis-btn lis-btn-primary"
                onClick={() => navigate(`/ordenes/nueva?id_paciente=${paciente.id}`)}
              >
                + Nueva Orden
              </button>
            </>
          )}
        </div>
      </div>

      {/* Resumen Clínico del Paciente */}
      <div className="lis-patient-summary">
        <div className="lis-info-field">
          <span className="lis-info-label">Cédula de Identidad (CI)</span>
          <span className="lis-info-value">
            {paciente.sin_ci ? (
              <span className="lis-badge-sin-ci">Sin CI</span>
            ) : (
              `${paciente.ci}${paciente.ci_complemento ? `-${paciente.ci_complemento}` : ""}`
            )}
          </span>
        </div>

        <div className="lis-info-field">
          <span className="lis-info-label">Sexo Biológico</span>
          <span className="lis-info-value">
            <span
              className="lis-status-badge"
              style={{
                backgroundColor: paciente.sexo === "M" ? "#e0f2fe" : "#fce7f3",
                color: paciente.sexo === "M" ? "#0369a1" : "#be185d",
              }}
            >
              {paciente.sexo === "M" ? "Masculino" : "Femenino"}
            </span>
          </span>
        </div>

        <div className="lis-info-field">
          <span className="lis-info-label">Fecha de Nacimiento</span>
          <span className="lis-info-value">{paciente.fecha_nacimiento || "No especificada"}</span>
        </div>

        <div className="lis-info-field">
          <span className="lis-info-label">Edad Calculada</span>
          <span className="lis-info-value">{calcularEdadTexto(paciente.fecha_nacimiento)}</span>
        </div>

        <div className="lis-info-field">
          <span className="lis-info-label">Teléfono de Contacto</span>
          <span className="lis-info-value">{paciente.telefono || "No especificado"}</span>
        </div>

        <div className="lis-info-field">
          <span className="lis-info-label">Identificador Interno</span>
          <span className="lis-info-value">#{paciente.id}</span>
        </div>
      </div>

      {/* Historial de Órdenes del Paciente */}
      <div className="lis-table-card" style={{ marginTop: "1rem" }}>
        <div
          style={{
            padding: "1.25rem 1.5rem",
            borderBottom: "1px solid var(--border-color)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <div>
            <h3 style={{ fontSize: "1.1rem", fontWeight: 700, margin: 0 }}>Historial de Órdenes Clínicas</h3>
            <p className="lis-page-sub" style={{ margin: 0, marginTop: "0.2rem" }}>
              Órdenes analíticas y determinaciones de laboratorio solicitadas para este paciente.
            </p>
          </div>

          {!esAdmin && (
            <button
              type="button"
              className="lis-btn lis-btn-outline lis-btn-sm"
              onClick={() => navigate(`/ordenes/nueva?id_paciente=${paciente.id}`)}
            >
              + Solicitar Orden
            </button>
          )}
        </div>

        {cargandoOrdenes ? (
          <div className="lis-table-loading" style={{ padding: "2rem" }}>
            <div className="lis-spinner" style={{ margin: "0 auto 0.5rem" }} />
            <p>Cargando órdenes del paciente...</p>
          </div>
        ) : ordenes.length === 0 ? (
          <div style={{ padding: "2.5rem 1.5rem", textAlign: "center", color: "var(--text-muted)" }}>
            <p style={{ fontWeight: 600, fontSize: "1rem", color: "var(--text-main)" }}>
              No existen órdenes registradas para este paciente.
            </p>
            {!esAdmin && (
              <p style={{ fontSize: "0.875rem", marginTop: "0.35rem" }}>
                Haga clic en <strong>"+ Nueva Orden"</strong> para crear su primera solicitud analítica.
              </p>
            )}
          </div>
        ) : (
          <div className="lis-table-responsive">
            <table className="lis-table">
              <thead>
                <tr>
                  <th style={{ width: "120px" }}>N° Orden</th>
                  <th style={{ width: "150px" }}>Estado</th>
                  <th>Estudios</th>
                  <th style={{ width: "130px" }}>Fecha</th>
                  <th style={{ width: "120px", textAlign: "right" }}>Acción</th>
                </tr>
              </thead>
              <tbody>
                {ordenes.map((o) => (
                  <tr key={o.id}>
                    <td>
                      <span className="lis-cell-bold">Orden #{o.numero_orden_paciente}</span>
                    </td>
                    <td>
                      <span
                        className={`lis-status-badge ${
                          o.estado_trabajo === "INCOMPLETO"
                            ? "lis-status-incompleto"
                            : o.estado_trabajo === "COMPLETO"
                            ? "lis-status-completo"
                            : "lis-status-publicada"
                        }`}
                      >
                        {o.estado_trabajo}
                      </span>
                    </td>
                    <td>
                      <div className="lis-chips-container">
                        {o.estudios.map((cod) => (
                          <span key={cod} className="lis-chip">
                            {cod}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td>{o.fecha_solicitud}</td>
                    <td className="lis-text-right">
                      <button
                        type="button"
                        className="lis-btn lis-btn-outline lis-btn-sm"
                        onClick={() => navigate(`/ordenes/${o.id}`)}
                      >
                        Detalle
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modal de Edición */}
      <PacienteFormModal
        abierto={modalEditarAbierto}
        pacienteEditando={paciente}
        onCerrar={() => setModalEditarAbierto(false)}
        onGuardado={handleGuardado}
      />
    </div>
  );
};
