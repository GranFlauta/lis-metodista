/**
 * Vista Principal de Pacientes (Búsqueda debounce 300ms, tabla paginada y gestión).
 * PROMPT_FASE_2.md §8.2, §9:
 * - Buscador q con debounce de 300 ms (busca en CI, nombres y apellidos).
 * - Paginación con límite y desplazamiento (limit / offset).
 * - Para ADMIN se ocultan los botones de crear y editar.
 * - Acceso a consulta del catálogo clínico.
 */

import React, { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listarPacientesApi, PacienteDetalle } from "../../api/pacientes";
import { ApiError } from "../../api/client";
import { useAuth } from "../auth/AuthProvider";
import { PacienteFormModal } from "./PacienteFormModal";
import { CatalogoModal } from "./CatalogoModal";

export const PacientesPage: React.FC = () => {
  const { usuario } = useAuth();
  const esAdmin = usuario?.rol === "ADMIN";
  const navigate = useNavigate();

  const [pacientes, setPacientes] = useState<PacienteDetalle[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [limit, setLimit] = useState<number>(25);
  const [offset, setOffset] = useState<number>(0);

  const [busqueda, setBusqueda] = useState<string>("");
  const [busquedaDebounced, setBusquedaDebounced] = useState<string>("");

  const [cargando, setCargando] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Modales
  const [modalFormAbierto, setModalFormAbierto] = useState<boolean>(false);
  const [pacienteEditando, setPacienteEditando] = useState<PacienteDetalle | null>(null);
  const [modalCatalogoAbierto, setModalCatalogoAbierto] = useState<boolean>(false);

  // Debounce de 300 ms en el buscador (§9)
  useEffect(() => {
    const timer = setTimeout(() => {
      setBusquedaDebounced(busqueda);
      setOffset(0);
    }, 300);
    return () => clearTimeout(timer);
  }, [busqueda]);

  // Cargar lista de pacientes
  const cargarPacientes = useCallback(async () => {
    setCargando(true);
    setError(null);
    try {
      const data = await listarPacientesApi({
        q: busquedaDebounced,
        limit,
        offset,
      });
      setPacientes(data.items);
      setTotal(data.total);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Error al cargar la lista de pacientes.");
      }
    } finally {
      setCargando(false);
    }
  }, [busquedaDebounced, limit, offset]);

  useEffect(() => {
    cargarPacientes();
  }, [cargarPacientes]);

  const handleAbrirCrear = () => {
    setPacienteEditando(null);
    setModalFormAbierto(true);
  };

  const handleAbrirEditar = (paciente: PacienteDetalle) => {
    setPacienteEditando(paciente);
    setModalFormAbierto(true);
  };

  const handleGuardado = (pacienteGuardado: PacienteDetalle) => {
    setModalFormAbierto(false);
    cargarPacientes();
    navigate(`/pacientes/${pacienteGuardado.id}`);
  };

  const handleNavegarExistente = (idPacienteExistente: number) => {
    setModalFormAbierto(false);
    navigate(`/pacientes/${idPacienteExistente}`);
  };

  const calcularEdadTexto = (fn: string | null): string => {
    if (!fn) return "No registrada";
    const fecha = new Date(fn + "T00:00:00");
    const hoy = new Date();
    let anios = hoy.getFullYear() - fecha.getFullYear();
    const m = hoy.getMonth() - fecha.getMonth();
    if (m < 0 || (m === 0 && hoy.getDate() < fecha.getDate())) {
      anios--;
    }
    return `${Math.max(0, anios)} años`;
  };

  return (
    <div className="lis-page-container">
      {/* Cabecera */}
      <div className="lis-page-header">
        <div>
          <h2>Gestión de Pacientes</h2>
          <p className="lis-page-sub">
            Registro clínico oficial de pacientes, documentos de identidad y fichas médicas.
          </p>
        </div>

        <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
          <button
            type="button"
            className="lis-btn lis-btn-outline"
            onClick={() => setModalCatalogoAbierto(true)}
            title="Ver catálogo de estudios y perfiles clínicos"
          >
            📋 Ver Catálogo
          </button>

          {!esAdmin && (
            <button
              type="button"
              className="lis-btn lis-btn-primary"
              onClick={handleAbrirCrear}
              title="Registrar un nuevo paciente clínico"
            >
              + Nuevo Paciente
            </button>
          )}
        </div>
      </div>

      {/* Alerta de error */}
      {error && <div className="lis-alert lis-alert-error">{error}</div>}

      {/* Barra de Filtros y Búsqueda */}
      <div className="lis-filter-bar">
        <div className="lis-filter-group lis-search-input">
          <label htmlFor="input-busqueda-pacientes">Buscar Paciente (CI o Apellidos / Nombres)</label>
          <input
            id="input-busqueda-pacientes"
            type="search"
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
            placeholder="Escriba número de carnet, apellido o nombre..."
            aria-label="Buscar pacientes por carnet o nombre"
          />
        </div>

        {busqueda && (
          <button
            type="button"
            className="lis-btn lis-btn-text"
            onClick={() => setBusqueda("")}
            style={{ alignSelf: "flex-end" }}
          >
            Limpiar búsqueda
          </button>
        )}
      </div>

      {/* Tabla Paginada de Pacientes */}
      <div className="lis-table-card">
        <div className="lis-table-responsive">
          <table className="lis-table">
            <thead>
              <tr>
                <th style={{ width: "160px" }}>Documento (CI)</th>
                <th>Apellidos y Nombres</th>
                <th style={{ width: "110px" }}>Sexo</th>
                <th>Fecha Nac. / Edad</th>
                <th>Teléfono</th>
                <th style={{ width: "180px", textAlign: "right" }}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {cargando ? (
                <tr>
                  <td colSpan={6} className="lis-table-loading">
                    <div className="lis-spinner" style={{ margin: "0 auto 0.5rem" }} />
                    <p>Consultando base de pacientes...</p>
                  </td>
                </tr>
              ) : pacientes.length === 0 ? (
                <tr>
                  <td colSpan={6} className="lis-table-empty">
                    <p style={{ fontWeight: 600, fontSize: "1rem" }}>No se encontraron pacientes registrados.</p>
                    <p className="lis-text-muted" style={{ marginTop: "0.25rem" }}>
                      {busqueda ? "Intente con otro término de búsqueda." : "Haga clic en '+ Nuevo Paciente' para dar de alta al primero."}
                    </p>
                  </td>
                </tr>
              ) : (
                pacientes.map((p) => (
                  <tr key={p.id}>
                    <td>
                      {p.sin_ci ? (
                        <span className="lis-badge-sin-ci">Sin CI</span>
                      ) : (
                        <span className="lis-cell-bold" style={{ letterSpacing: "0.03em" }}>
                          {p.ci}
                          {p.ci_complemento && (
                            <span style={{ color: "var(--primary)", marginLeft: "2px" }}>
                              -{p.ci_complemento}
                            </span>
                          )}
                        </span>
                      )}
                    </td>
                    <td>
                      <span className="lis-cell-bold">
                        {p.apellido_paterno} {p.apellido_materno || ""},
                      </span>{" "}
                      <span>{p.nombres}</span>
                    </td>
                    <td>
                      <span
                        className="lis-status-badge"
                        style={{
                          backgroundColor: p.sexo === "M" ? "#e0f2fe" : "#fce7f3",
                          color: p.sexo === "M" ? "#0369a1" : "#be185d",
                        }}
                      >
                        {p.sexo === "M" ? "Masculino" : "Femenino"}
                      </span>
                    </td>
                    <td>
                      <div>{p.fecha_nacimiento || "—"}</div>
                      {p.fecha_nacimiento && (
                        <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                          ({calcularEdadTexto(p.fecha_nacimiento)})
                        </span>
                      )}
                    </td>
                    <td>{p.telefono || "—"}</td>
                    <td className="lis-text-right">
                      <div className="lis-actions-cell">
                        <button
                          type="button"
                          className="lis-btn lis-btn-outline lis-btn-sm"
                          onClick={() => navigate(`/pacientes/${p.id}`)}
                          title="Ver Ficha Clínica del Paciente"
                        >
                          Ficha
                        </button>
                        {!esAdmin && (
                          <button
                            type="button"
                            className="lis-btn lis-btn-secondary lis-btn-sm"
                            onClick={() => handleAbrirEditar(p)}
                            title="Editar Datos del Paciente"
                          >
                            Editar
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Barra de Paginación */}
        {!cargando && total > 0 && (
          <div className="lis-pagination-bar">
            <div className="lis-pagination-info">
              Mostrando <strong>{offset + 1}</strong> a{" "}
              <strong>{Math.min(offset + limit, total)}</strong> de <strong>{total}</strong> pacientes
            </div>

            <div className="lis-pagination-controls">
              <label htmlFor="select-limit-pacientes" style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                Por pág.:
              </label>
              <select
                id="select-limit-pacientes"
                className="lis-pagination-select"
                value={limit}
                onChange={(e) => {
                  setLimit(Number(e.target.value));
                  setOffset(0);
                }}
              >
                <option value={10}>10</option>
                <option value={25}>25</option>
                <option value={50}>50</option>
              </select>

              <button
                type="button"
                className="lis-btn lis-btn-outline lis-btn-sm"
                onClick={() => setOffset(Math.max(0, offset - limit))}
                disabled={offset === 0}
              >
                ← Anterior
              </button>

              <button
                type="button"
                className="lis-btn lis-btn-outline lis-btn-sm"
                onClick={() => setOffset(offset + limit)}
                disabled={offset + limit >= total}
              >
                Siguiente →
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Modal de Alta / Edición de Paciente */}
      <PacienteFormModal
        abierto={modalFormAbierto}
        pacienteEditando={pacienteEditando}
        onCerrar={() => setModalFormAbierto(false)}
        onGuardado={handleGuardado}
        onVerPacienteExistente={handleNavegarExistente}
      />

      {/* Modal de Catálogo Clínico */}
      <CatalogoModal
        abierto={modalCatalogoAbierto}
        onCerrar={() => setModalCatalogoAbierto(false)}
      />
    </div>
  );
};
