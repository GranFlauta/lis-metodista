/**
 * Vista Principal de Pacientes (Buscar y gestionar).
 * Implementa PROMPT_FASE_3_6_UX.md §6.6 y docs/UX_GUIDE.md:
 * - Buscador principal grande con debounce de 300 ms.
 * - Filtros en una fila: sexo, creado desde/hasta, casilla "Solo con pendientes".
 * - Tabla densa: CI, nombre completo, edad, sexo, teléfono, etiqueta "Pendiente (n)" (clic -> lista filtrada).
 * - Acciones por fila: Nueva orden (abre /ordenes/nueva?pacienteId=...), Editar y Ficha.
 * - Botón "Nuevo paciente" como secundario.
 * - ADMIN: solo lectura (sin botones de creación ni edición).
 * - Cero emojis, cero textos de desarrollo, sin almacenamiento en navegador.
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

  // Filtros
  const [busqueda, setBusqueda] = useState<string>("");
  const [busquedaDebounced, setBusquedaDebounced] = useState<string>("");
  const [filtroSexo, setFiltroSexo] = useState<string>("TODOS");
  const [creadoDesde, setCreadoDesde] = useState<string>("");
  const [creadoHasta, setCreadoHasta] = useState<string>("");
  const [soloPendientes, setSoloPendientes] = useState<boolean>(false);

  const [cargando, setCargando] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Modales
  const [modalFormAbierto, setModalFormAbierto] = useState<boolean>(false);
  const [pacienteEditando, setPacienteEditando] = useState<PacienteDetalle | null>(null);
  const [modalCatalogoAbierto, setModalCatalogoAbierto] = useState<boolean>(false);

  // Debounce de 300 ms en el buscador (§6.6)
  useEffect(() => {
    const timer = setTimeout(() => {
      setBusquedaDebounced(busqueda);
      setOffset(0);
    }, 300);
    return () => clearTimeout(timer);
  }, [busqueda]);

  // Cargar lista de pacientes con filtros B1
  const cargarPacientes = useCallback(async () => {
    setCargando(true);
    setError(null);
    try {
      const data = await listarPacientesApi({
        q: busquedaDebounced || undefined,
        limit,
        offset,
        sexo: filtroSexo !== "TODOS" ? filtroSexo : undefined,
        creado_desde: creadoDesde || undefined,
        creado_hasta: creadoHasta || undefined,
        con_pendientes: soloPendientes ? true : undefined,
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
  }, [busquedaDebounced, limit, offset, filtroSexo, creadoDesde, creadoHasta, soloPendientes]);

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

  const limpiarFiltros = () => {
    setBusqueda("");
    setFiltroSexo("TODOS");
    setCreadoDesde("");
    setCreadoHasta("");
    setSoloPendientes(false);
    setOffset(0);
  };

  const hayFiltrosActivos =
    Boolean(busqueda) || filtroSexo !== "TODOS" || Boolean(creadoDesde) || Boolean(creadoHasta) || soloPendientes;

  return (
    <div className="lis-page-container">
      {/* Cabecera */}
      <div className="lis-page-header">
        <div>
          <h2>Gestión de Pacientes</h2>
          <p className="lis-page-sub">
            Búsqueda, gestión y expedientes clínicos de pacientes.
          </p>
        </div>

        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
          <button
            type="button"
            className="lis-btn lis-btn-outline"
            onClick={() => setModalCatalogoAbierto(true)}
            title="Ver catálogo de estudios y perfiles clínicos"
          >
            Ver catálogo
          </button>

          {!esAdmin && (
            <button
              type="button"
              className="lis-btn lis-btn-secondary"
              onClick={handleAbrirCrear}
              title="Registrar paciente (acción secundaria)"
            >
              + Nuevo paciente
            </button>
          )}
        </div>
      </div>

      {/* Alerta de error */}
      {error && <div className="lis-alert lis-alert-error">{error}</div>}

      {/* Barra de Filtros y Búsqueda en una fila (§6.6) */}
      <div
        className="lis-filter-bar"
        style={{
          display: "flex",
          gap: "8px",
          alignItems: "flex-end",
          flexWrap: "wrap",
          padding: "8px 12px",
        }}
      >
        <div className="lis-filter-group" style={{ flex: "1 1 240px", minWidth: "200px" }}>
          <label htmlFor="input-busqueda-pacientes">Buscador principal</label>
          <input
            id="input-busqueda-pacientes"
            type="search"
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
            placeholder="Buscar por CI, apellidos o nombres…"
            aria-label="Buscar pacientes por documento o nombre"
            className="lis-input"
            style={{ height: "32px", fontSize: "13.5px" }}
          />
        </div>

        <div className="lis-filter-group" style={{ width: "110px" }}>
          <label htmlFor="select-filtro-sexo">Sexo</label>
          <select
            id="select-filtro-sexo"
            value={filtroSexo}
            onChange={(e) => {
              setFiltroSexo(e.target.value);
              setOffset(0);
            }}
            className="lis-input"
            style={{ height: "32px", fontSize: "13px" }}
          >
            <option value="TODOS">Todos</option>
            <option value="M">Masculino</option>
            <option value="F">Femenino</option>
          </select>
        </div>

        <div className="lis-filter-group" style={{ width: "130px" }}>
          <label htmlFor="input-creado-desde">Creado desde</label>
          <input
            id="input-creado-desde"
            type="date"
            value={creadoDesde}
            onChange={(e) => {
              setCreadoDesde(e.target.value);
              setOffset(0);
            }}
            className="lis-input"
            style={{ height: "32px", fontSize: "12.5px" }}
          />
        </div>

        <div className="lis-filter-group" style={{ width: "130px" }}>
          <label htmlFor="input-creado-hasta">Creado hasta</label>
          <input
            id="input-creado-hasta"
            type="date"
            value={creadoHasta}
            onChange={(e) => {
              setCreadoHasta(e.target.value);
              setOffset(0);
            }}
            className="lis-input"
            style={{ height: "32px", fontSize: "12.5px" }}
          />
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "6px", height: "32px", padding: "0 4px" }}>
          <label
            htmlFor="check-solo-pendientes"
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              cursor: "pointer",
              fontSize: "13px",
              fontWeight: 600,
              userSelect: "none",
            }}
          >
            <input
              id="check-solo-pendientes"
              type="checkbox"
              checked={soloPendientes}
              onChange={(e) => {
                setSoloPendientes(e.target.checked);
                setOffset(0);
              }}
            />
            Solo con pendientes
          </label>
        </div>

        {hayFiltrosActivos && (
          <button
            type="button"
            className="lis-btn lis-btn-text"
            onClick={limpiarFiltros}
            style={{ height: "32px", fontSize: "12.5px" }}
          >
            Limpiar filtros
          </button>
        )}
      </div>

      {/* Tabla Densa de Pacientes */}
      <div className="lis-table-card">
        <div className="lis-table-responsive">
          <table className="lis-table" style={{ fontSize: "13.5px" }}>
            <thead>
              <tr>
                <th style={{ width: "130px" }}>CI</th>
                <th>Nombre completo</th>
                <th style={{ width: "95px" }}>Edad</th>
                <th style={{ width: "85px" }}>Sexo</th>
                <th style={{ width: "115px" }}>Teléfono</th>
                <th style={{ width: "130px" }}>Pendientes</th>
                <th style={{ width: "210px", textAlign: "right" }}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {cargando ? (
                <tr>
                  <td colSpan={7} className="lis-table-loading">
                    <div className="lis-spinner" style={{ margin: "0 auto 0.5rem" }} />
                    <p>Consultando base de pacientes…</p>
                  </td>
                </tr>
              ) : pacientes.length === 0 ? (
                <tr>
                  <td colSpan={7} className="lis-table-empty">
                    <p style={{ fontWeight: 600, fontSize: "1rem" }}>No se encontraron pacientes registrados.</p>
                    <p className="lis-text-muted" style={{ marginTop: "0.25rem" }}>
                      {hayFiltrosActivos
                        ? "Intente ajustando los filtros de búsqueda."
                        : "Use '+ Nuevo paciente' o inicie una 'Nueva orden' para registrar."}
                    </p>
                  </td>
                </tr>
              ) : (
                pacientes.map((p) => {
                  const cantPendientes = p.pendientes || 0;
                  return (
                    <tr key={p.id}>
                      <td>
                        {p.sin_ci ? (
                          <span className="lis-badge-sin-ci">Sin CI</span>
                        ) : (
                          <span className="lis-cell-bold" style={{ letterSpacing: "0.02em" }}>
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
                          {p.apellido_paterno} {p.apellido_materno || ""},{" "}
                        </span>
                        <span>{p.nombres}</span>
                      </td>
                      <td>{calcularEdadTexto(p.fecha_nacimiento)}</td>
                      <td>
                        <span
                          className="lis-status-badge"
                          style={{
                            backgroundColor: p.sexo === "M" ? "#e0f2fe" : "#fce7f3",
                            color: p.sexo === "M" ? "#0369a1" : "#be185d",
                            fontSize: "11.5px",
                            padding: "1px 6px",
                          }}
                        >
                          {p.sexo === "M" ? "M" : "F"}
                        </span>
                      </td>
                      <td>{p.telefono || "—"}</td>
                      <td>
                        {cantPendientes > 0 ? (
                          <button
                            type="button"
                            className="lis-flag-badge lis-flag-alto"
                            onClick={() => navigate(`/ordenes?id_paciente=${p.id}&estado=INCOMPLETO`)}
                            style={{ cursor: "pointer", border: "none", textDecoration: "none" }}
                            title={`Ver ${cantPendientes} orden(es) pendiente(s) de este paciente`}
                          >
                            Pendiente ({cantPendientes})
                          </button>
                        ) : (
                          <span style={{ color: "var(--text-muted)", fontSize: "12px" }}>0 pendientes</span>
                        )}
                      </td>
                      <td className="lis-text-right">
                        <div className="lis-actions-cell" style={{ justifyContent: "flex-end", gap: "4px" }}>
                          {!esAdmin && (
                            <button
                              type="button"
                              className="lis-btn lis-btn-primary lis-btn-sm"
                              onClick={() => navigate(`/ordenes/nueva?pacienteId=${p.id}`)}
                              title="Crear nueva orden para este paciente"
                            >
                              Nueva orden
                            </button>
                          )}
                          {!esAdmin && (
                            <button
                              type="button"
                              className="lis-btn lis-btn-outline lis-btn-sm"
                              onClick={() => handleAbrirEditar(p)}
                              title="Editar datos del paciente"
                            >
                              Editar
                            </button>
                          )}
                          <button
                            type="button"
                            className="lis-btn lis-btn-secondary lis-btn-sm"
                            onClick={() => navigate(`/pacientes/${p.id}`)}
                            title="Ver ficha e historial de órdenes"
                          >
                            Ficha
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
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

export default PacientesPage;
