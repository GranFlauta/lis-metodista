/**
 * Bandeja de Órdenes Clínicas.
 * PROMPT_FASE_2.md §8.3, §9:
 * - BIOQUIMICO: solo sus órdenes (por defecto INCOMPLETO y COMPLETO).
 * - ADMIN: todas las órdenes (auditado por backend). Oculta botones de crear/editar/descartar.
 * - Filtros por estado y texto q (debounce 300 ms).
 * - Descarte de borrador (DELETE /api/ordenes/:id) con diálogo de confirmación.
 */

import React, { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  descartarOrdenApi,
  listarOrdenesApi,
  OrdenListItem,
} from "../../api/ordenes";
import { ApiError } from "../../api/client";
import { useAuth } from "../auth/AuthProvider";

export const OrdenesPage: React.FC = () => {
  const { usuario } = useAuth();
  const esAdmin = usuario?.rol === "ADMIN";
  const navigate = useNavigate();

  const [ordenes, setOrdenes] = useState<OrdenListItem[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [limit, setLimit] = useState<number>(25);
  const [offset, setOffset] = useState<number>(0);

  // Filtros
  const [filtroEstado, setFiltroEstado] = useState<string>("");
  const [busqueda, setBusqueda] = useState<string>("");
  const [busquedaDebounced, setBusquedaDebounced] = useState<string>("");

  const [cargando, setCargando] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [mensajeExito, setMensajeExito] = useState<string | null>(null);

  // Modal de confirmación de descarte
  const [ordenADescartar, setOrdenADescartar] = useState<OrdenListItem | null>(null);
  const [descartando, setDescartando] = useState<boolean>(false);

  // Debounce en buscador (300 ms)
  useEffect(() => {
    const timer = setTimeout(() => {
      setBusquedaDebounced(busqueda);
      setOffset(0);
    }, 300);
    return () => clearTimeout(timer);
  }, [busqueda]);

  // Cargar órdenes
  const cargarOrdenes = useCallback(async () => {
    setCargando(true);
    setError(null);
    try {
      const resp = await listarOrdenesApi({
        estado: filtroEstado || undefined,
        q: busquedaDebounced || undefined,
        limit,
        offset,
      });
      setOrdenes(resp.items);
      setTotal(resp.total);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Error al cargar la lista de órdenes.");
      }
    } finally {
      setCargando(false);
    }
  }, [filtroEstado, busquedaDebounced, limit, offset]);

  useEffect(() => {
    cargarOrdenes();
  }, [cargarOrdenes]);

  // Ejecutar descarte de borrador (DELETE / 204)
  const handleConfirmarDescarte = async () => {
    if (!ordenADescartar) return;
    setDescartando(true);
    setError(null);
    try {
      await descartarOrdenApi(ordenADescartar.id);
      setMensajeExito(`Borrador de la Orden #${ordenADescartar.numero_orden_paciente} descartado exitosamente.`);
      setOrdenADescartar(null);
      cargarOrdenes();
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Error al descartar la orden.");
      }
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

  return (
    <div className="lis-page-container">
      {/* Cabecera */}
      <div className="lis-page-header">
        <div>
          <h2>Bandeja de Órdenes Clínicas</h2>
          <p className="lis-page-sub">
            {esAdmin
              ? "Supervisión institucional de órdenes clínicas (Acceso auditado ADMIN_VE_PRIVADO)."
              : "Gestión de solicitudes analíticas en borrador y seguimiento de determinaciones."}
          </p>
        </div>

        {!esAdmin && (
          <Link to="/ordenes/nueva" className="lis-btn lis-btn-primary">
            + Nueva Orden
          </Link>
        )}
      </div>

      {mensajeExito && (
        <div className="lis-alert lis-alert-success" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span>{mensajeExito}</span>
          <button type="button" className="lis-btn lis-btn-text" onClick={() => setMensajeExito(null)}>
            ✕
          </button>
        </div>
      )}

      {error && <div className="lis-alert lis-alert-error">{error}</div>}

      {/* Barra de Filtros */}
      <div className="lis-filter-bar">
        <div className="lis-filter-group lis-search-input">
          <label htmlFor="input-busqueda-ordenes">Buscar por Paciente (CI o Nombre)</label>
          <input
            id="input-busqueda-ordenes"
            type="search"
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
            placeholder="Escriba documento o nombre del paciente..."
          />
        </div>

        <div className="lis-filter-group">
          <label htmlFor="select-estado-ordenes">Estado de Trabajo</label>
          <select
            id="select-estado-ordenes"
            value={filtroEstado}
            onChange={(e) => {
              setFiltroEstado(e.target.value);
              setOffset(0);
            }}
          >
            <option value="">{esAdmin ? "Todos los estados" : "Pendientes (INCOMPLETO / COMPLETO)"}</option>
            <option value="INCOMPLETO">INCOMPLETO</option>
            <option value="COMPLETO">COMPLETO</option>
            <option value="PUBLICADA">PUBLICADA</option>
          </select>
        </div>

        {(busqueda || filtroEstado) && (
          <button
            type="button"
            className="lis-btn lis-btn-text"
            onClick={() => {
              setBusqueda("");
              setFiltroEstado("");
              setOffset(0);
            }}
            style={{ alignSelf: "flex-end" }}
          >
            Limpiar filtros
          </button>
        )}
      </div>

      {/* Tabla de Órdenes */}
      <div className="lis-table-card">
        <div className="lis-table-responsive">
          <table className="lis-table">
            <thead>
              <tr>
                <th style={{ width: "120px" }}>N° Orden</th>
                <th>Paciente</th>
                <th style={{ width: "160px" }}>Estado</th>
                <th>Estudios Solicitados</th>
                <th style={{ width: "130px" }}>Fecha Solicitud</th>
                <th style={{ width: "170px", textAlign: "right" }}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {cargando ? (
                <tr>
                  <td colSpan={6} className="lis-table-loading">
                    <div className="lis-spinner" style={{ margin: "0 auto 0.5rem" }} />
                    <p>Consultando órdenes clínicas...</p>
                  </td>
                </tr>
              ) : ordenes.length === 0 ? (
                <tr>
                  <td colSpan={6} className="lis-table-empty">
                    <p style={{ fontWeight: 600, fontSize: "1rem" }}>No se encontraron órdenes registradas.</p>
                    <p className="lis-text-muted" style={{ marginTop: "0.25rem" }}>
                      {!esAdmin && "Utilice el botón '+ Nueva Orden' para solicitar análisis clínicos."}
                    </p>
                  </td>
                </tr>
              ) : (
                ordenes.map((o) => (
                  <tr key={o.id}>
                    <td>
                      <span className="lis-cell-bold" style={{ fontSize: "0.95rem" }}>
                        Orden #{o.numero_orden_paciente}
                      </span>
                    </td>
                    <td>
                      <div className="lis-cell-bold">
                        {o.paciente.apellido_paterno} {o.paciente.apellido_materno || ""}, {o.paciente.nombres}
                      </div>
                      <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                        {o.paciente.ci ? `CI: ${o.paciente.ci}` : "Sin CI"}
                      </span>
                    </td>
                    <td>
                      <div style={{ display: "flex", gap: "0.3rem", alignItems: "center", flexWrap: "wrap" }}>
                        <span className={`lis-status-badge ${obtenerClaseEstado(o.estado_trabajo)}`}>
                          {o.estado_trabajo}
                        </span>
                        {o.bloqueada && (
                          <span className="lis-status-badge lis-status-bloqueada" title="Bloqueada por concurrencia clínica">
                            🔒 Bloqueada
                          </span>
                        )}
                      </div>
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
                      <div className="lis-actions-cell">
                        <button
                          type="button"
                          className="lis-btn lis-btn-primary lis-btn-sm"
                          onClick={() => navigate(`/ordenes/${o.id}/captura`)}
                          title="Capturar y calcular resultados analíticos"
                        >
                          {esAdmin ? "Ver Captura" : "Capturar"}
                        </button>

                        <button
                          type="button"
                          className="lis-btn lis-btn-outline lis-btn-sm"
                          onClick={() => navigate(`/ordenes/${o.id}`)}
                          title="Ver detalle completo de la orden"
                        >
                          Detalle
                        </button>

                        {!esAdmin && o.estado_trabajo !== "PUBLICADA" && (
                          <button
                            type="button"
                            className="lis-btn lis-btn-danger lis-btn-sm"
                            onClick={() => setOrdenADescartar(o)}
                            title="Descartar este borrador de orden"
                          >
                            Descartar
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

        {/* Paginación */}
        {!cargando && total > 0 && (
          <div className="lis-pagination-bar">
            <div className="lis-pagination-info">
              Mostrando <strong>{offset + 1}</strong> a{" "}
              <strong>{Math.min(offset + limit, total)}</strong> de <strong>{total}</strong> órdenes
            </div>

            <div className="lis-pagination-controls">
              <label htmlFor="select-limit-ordenes" style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                Por pág.:
              </label>
              <select
                id="select-limit-ordenes"
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

      {/* Modal de Confirmación de Descarte */}
      {ordenADescartar && (
        <div className="lis-modal-overlay" role="dialog" aria-modal="true" aria-labelledby="modal-descarte-title">
          <div className="lis-modal-card lis-modal-alert">
            <div className="lis-modal-header">
              <h3 id="modal-descarte-title">Confirmar Descarte de Borrador</h3>
              <button
                type="button"
                className="lis-modal-close"
                onClick={() => setOrdenADescartar(null)}
                disabled={descartando}
              >
                ✕
              </button>
            </div>

            <div className="lis-modal-body">
              <p>
                ¿Está seguro de descartar la <strong>Orden #{ordenADescartar.numero_orden_paciente}</strong> de{" "}
                <strong>
                  {ordenADescartar.paciente.apellido_paterno} {ordenADescartar.paciente.nombres}
                </strong>?
              </p>
              <p style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                Esta acción eliminará físicamente la orden y registrará un evento de trazabilidad legal en el histórico
                de borradores descartados. No podrá recuperarse.
              </p>
            </div>

            <div className="lis-modal-footer">
              <button
                type="button"
                className="lis-btn lis-btn-secondary"
                onClick={() => setOrdenADescartar(null)}
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
