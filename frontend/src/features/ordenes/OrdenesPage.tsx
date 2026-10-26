/**
 * Bandeja de Órdenes y Pendientes Clínicos.
 * Implementa PROMPT_FASE_3_6_UX.md §6.7 y docs/UX_GUIDE.md:
 * - Tabla densa con filtros rápidos tipo pestaña: Todas · Incompletas · Completas · Publicadas.
 * - Buscador con debounce y paginación.
 * - Acción principal de la fila: Continuar captura (o Ver captura para ADMIN).
 * - Acción secundaria: Detalle de orden.
 * - Acción de descarte: Descartar borrador con diálogo de confirmación.
 * - Columnas: Paciente, Estudios, Estado, Hora de inicio, Creado, Autor (solo ADMIN).
 * - Cero emojis, cero textos de desarrollo, sin almacenamiento en navegador.
 */

import React, { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  descartarOrdenApi,
  listarOrdenesApi,
  OrdenListItem,
} from "../../api/ordenes";
import { ApiError } from "../../api/client";
import { useAuth } from "../auth/AuthProvider";

type EstadoPestana = "" | "INCOMPLETO" | "COMPLETO" | "PUBLICADA";

export const OrdenesPage: React.FC = () => {
  const { usuario } = useAuth();
  const esAdmin = usuario?.rol === "ADMIN";
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const idPacienteParam = searchParams.get("id_paciente")
    ? Number(searchParams.get("id_paciente"))
    : undefined;
  const estadoParam = searchParams.get("estado") as EstadoPestana | null;

  const [ordenes, setOrdenes] = useState<OrdenListItem[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [limit, setLimit] = useState<number>(25);
  const [offset, setOffset] = useState<number>(0);

  // Filtros
  const [pestanaActiva, setPestanaActiva] = useState<EstadoPestana>(
    estadoParam === "INCOMPLETO" || estadoParam === "COMPLETO" || estadoParam === "PUBLICADA"
      ? estadoParam
      : ""
  );
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
        estado: pestanaActiva || undefined,
        id_paciente: idPacienteParam,
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
  }, [pestanaActiva, idPacienteParam, busquedaDebounced, limit, offset]);

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
      setMensajeExito(`Borrador de la orden #${ordenADescartar.numero_orden_paciente} descartado.`);
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

  const formatearFechaHora = (isoStr: string | null | undefined): string => {
    if (!isoStr) return "—";
    try {
      const d = new Date(isoStr);
      if (isNaN(d.getTime())) return isoStr;
      return d.toLocaleString([], {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return isoStr;
    }
  };

  const cambiarPestana = (nuevaPestana: EstadoPestana) => {
    setPestanaActiva(nuevaPestana);
    setOffset(0);
  };

  const quitarFiltroPaciente = () => {
    const nuevosParams = new URLSearchParams(searchParams);
    nuevosParams.delete("id_paciente");
    setSearchParams(nuevosParams);
  };

  return (
    <div className="lis-page-container">
      {/* Cabecera y Acciones */}
      <div className="lis-page-header" style={{ marginBottom: "1rem" }}>
        <div>
          <p className="lis-page-sub" style={{ margin: 0, fontSize: "13.5px" }}>
            {esAdmin
              ? "Supervisión de órdenes clínicas (Acceso auditado ADMIN_VE_PRIVADO)."
              : "Control de órdenes analíticas, estado de avance y captura de resultados clínicos."}
          </p>
        </div>

        {!esAdmin && (
          <Link to="/ordenes/nueva" className="lis-btn lis-btn-primary">
            + Nueva orden
          </Link>
        )}
      </div>

      {mensajeExito && (
        <div
          className="lis-alert lis-alert-success"
          style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}
        >
          <span>{mensajeExito}</span>
          <button
            type="button"
            className="lis-btn lis-btn-text"
            onClick={() => setMensajeExito(null)}
            style={{ padding: "0 4px" }}
          >
            Cerrar
          </button>
        </div>
      )}

      {error && <div className="lis-alert lis-alert-error">{error}</div>}

      {/* Filtro por paciente si viene en URL */}
      {idPacienteParam && (
        <div
          className="lis-alert lis-alert-info"
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "8px",
            padding: "6px 12px",
            fontSize: "13px",
          }}
        >
          <span>
            Filtrando órdenes del <strong>paciente #{idPacienteParam}</strong>
          </span>
          <button
            type="button"
            className="lis-btn lis-btn-text"
            onClick={quitarFiltroPaciente}
            style={{ fontSize: "12px", padding: 0 }}
          >
            Mostrar todos los pacientes
          </button>
        </div>
      )}

      {/* Pestañas de Filtro Rápido (§6.7: Todas · Incompletas · Completas · Publicadas) */}
      <div
        style={{
          display: "flex",
          gap: "4px",
          borderBottom: "2px solid var(--border-light)",
          marginBottom: "10px",
        }}
      >
        <button
          type="button"
          onClick={() => cambiarPestana("")}
          className="lis-tab-btn"
          style={{
            background: "transparent",
            border: "none",
            borderBottom: pestanaActiva === "" ? "2px solid var(--primary)" : "2px solid transparent",
            color: pestanaActiva === "" ? "var(--primary)" : "var(--text-muted)",
            fontWeight: pestanaActiva === "" ? 700 : 500,
            padding: "8px 16px",
            fontSize: "13.5px",
            cursor: "pointer",
            marginBottom: "-2px",
          }}
        >
          Todas
        </button>
        <button
          type="button"
          onClick={() => cambiarPestana("INCOMPLETO")}
          className="lis-tab-btn"
          style={{
            background: "transparent",
            border: "none",
            borderBottom: pestanaActiva === "INCOMPLETO" ? "2px solid var(--warning)" : "2px solid transparent",
            color: pestanaActiva === "INCOMPLETO" ? "#b45309" : "var(--text-muted)",
            fontWeight: pestanaActiva === "INCOMPLETO" ? 700 : 500,
            padding: "8px 16px",
            fontSize: "13.5px",
            cursor: "pointer",
            marginBottom: "-2px",
          }}
        >
          Incompletas
        </button>
        <button
          type="button"
          onClick={() => cambiarPestana("COMPLETO")}
          className="lis-tab-btn"
          style={{
            background: "transparent",
            border: "none",
            borderBottom: pestanaActiva === "COMPLETO" ? "2px solid var(--success)" : "2px solid transparent",
            color: pestanaActiva === "COMPLETO" ? "var(--success)" : "var(--text-muted)",
            fontWeight: pestanaActiva === "COMPLETO" ? 700 : 500,
            padding: "8px 16px",
            fontSize: "13.5px",
            cursor: "pointer",
            marginBottom: "-2px",
          }}
        >
          Completas
        </button>
        <button
          type="button"
          onClick={() => cambiarPestana("PUBLICADA")}
          className="lis-tab-btn"
          style={{
            background: "transparent",
            border: "none",
            borderBottom: pestanaActiva === "PUBLICADA" ? "2px solid var(--primary-hover)" : "2px solid transparent",
            color: pestanaActiva === "PUBLICADA" ? "var(--primary-hover)" : "var(--text-muted)",
            fontWeight: pestanaActiva === "PUBLICADA" ? 700 : 500,
            padding: "8px 16px",
            fontSize: "13.5px",
            cursor: "pointer",
            marginBottom: "-2px",
          }}
        >
          Publicadas
        </button>
      </div>

      {/* Buscador secundario */}
      <div className="lis-filter-bar" style={{ padding: "6px 12px", marginBottom: "8px" }}>
        <div className="lis-filter-group lis-search-input" style={{ width: "100%", maxWidth: "420px" }}>
          <label htmlFor="input-busqueda-ordenes">Buscar por paciente o documento</label>
          <input
            id="input-busqueda-ordenes"
            type="search"
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
            placeholder="Buscar por CI, apellidos o nombres…"
            className="lis-input"
            style={{ height: "30px", fontSize: "13px" }}
          />
        </div>

        {busqueda && (
          <button
            type="button"
            className="lis-btn lis-btn-text"
            onClick={() => setBusqueda("")}
            style={{ alignSelf: "flex-end", height: "30px" }}
          >
            Limpiar búsqueda
          </button>
        )}
      </div>

      {/* Tabla Densa de Órdenes (§6.7) */}
      <div className="lis-table-card">
        <div className="lis-table-responsive">
          <table className="lis-table" style={{ fontSize: "13.5px" }}>
            <thead>
              <tr>
                <th>Paciente</th>
                <th>Estudios</th>
                <th style={{ width: "130px" }}>Estado</th>
                <th style={{ width: "135px" }}>Hora de inicio</th>
                <th style={{ width: "135px" }}>Creado</th>
                {esAdmin && <th style={{ width: "130px" }}>Autor</th>}
                <th style={{ width: "230px", textAlign: "right" }}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {cargando ? (
                <tr>
                  <td colSpan={esAdmin ? 7 : 6} className="lis-table-loading">
                    <div className="lis-spinner" style={{ margin: "0 auto 0.5rem" }} />
                    <p>Consultando órdenes clínicas…</p>
                  </td>
                </tr>
              ) : ordenes.length === 0 ? (
                <tr>
                  <td colSpan={esAdmin ? 7 : 6} className="lis-table-empty">
                    <p style={{ fontWeight: 600, fontSize: "1rem" }}>No se encontraron órdenes registradas.</p>
                    <p className="lis-text-muted" style={{ marginTop: "0.25rem" }}>
                      {!esAdmin && "Utilice el botón '+ Nueva orden' para registrar solicitudes."}
                    </p>
                  </td>
                </tr>
              ) : (
                ordenes.map((o) => (
                  <tr key={o.id}>
                    <td>
                      <div className="lis-cell-bold">
                        {o.paciente.apellido_paterno} {o.paciente.apellido_materno || ""},{" "}
                        {o.paciente.nombres}
                      </div>
                      <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                        {o.paciente.ci ? `CI: ${o.paciente.ci}` : "Sin CI"}
                        {" · "}Orden #{o.numero_orden_paciente}
                      </span>
                    </td>
                    <td>
                      <div className="lis-chips-container">
                        {o.estudios.map((cod) => (
                          <span key={cod} className="lis-chip" style={{ fontSize: "11px", padding: "1px 6px" }}>
                            {cod}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td>
                      <div style={{ display: "flex", gap: "4px", alignItems: "center", flexWrap: "wrap" }}>
                        <span
                          className={`lis-status-badge ${
                            o.estado_trabajo === "COMPLETO"
                              ? "lis-status-completo"
                              : o.estado_trabajo === "PUBLICADA"
                              ? "lis-status-publicada"
                              : "lis-status-incompleto"
                          }`}
                          style={{ fontSize: "11.5px" }}
                        >
                          {o.estado_trabajo === "COMPLETO"
                            ? "Completo"
                            : o.estado_trabajo === "PUBLICADA"
                            ? "Publicada"
                            : "Incompleto"}
                        </span>
                        {o.bloqueada && (
                          <span
                            className="lis-status-badge lis-status-bloqueada"
                            style={{ fontSize: "11px" }}
                            title="Bloqueada por concurrencia clínica"
                          >
                            Bloqueada
                          </span>
                        )}
                      </div>
                    </td>
                    <td style={{ fontSize: "12.5px" }}>
                      {formatearFechaHora(o.fecha_hora_toma_muestra || o.fecha_solicitud)}
                    </td>
                    <td style={{ fontSize: "12.5px" }}>{formatearFechaHora(o.creado_en)}</td>
                    {esAdmin && (
                      <td style={{ fontSize: "12.5px" }}>
                        {o.autor ? `${o.autor.nombres} ${o.autor.apellido_paterno}` : "—"}
                      </td>
                    )}
                    <td className="lis-text-right">
                      <div className="lis-actions-cell" style={{ justifyContent: "flex-end", gap: "4px" }}>
                        {/* Acción principal: Continuar captura */}
                        <button
                          type="button"
                          className="lis-btn lis-btn-primary lis-btn-sm"
                          onClick={() => navigate(`/ordenes/${o.id}/captura`)}
                          title="Continuar captura de resultados"
                        >
                          {esAdmin ? "Ver captura" : "Continuar captura"}
                        </button>

                        {/* Acción secundaria: Detalle */}
                        <button
                          type="button"
                          className="lis-btn lis-btn-outline lis-btn-sm"
                          onClick={() => navigate(`/ordenes/${o.id}`)}
                          title="Ver detalle de la orden"
                        >
                          Detalle
                        </button>

                        {/* Descarte con confirmación */}
                        {!esAdmin && o.estado_trabajo !== "PUBLICADA" && (
                          <button
                            type="button"
                            className="lis-btn lis-btn-danger lis-btn-sm"
                            onClick={() => setOrdenADescartar(o)}
                            title="Descartar borrador"
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

      {/* Modal de confirmación de descarte */}
      {ordenADescartar && (
        <div className="lis-modal-overlay">
          <div className="lis-modal-card" style={{ maxWidth: "440px" }}>
            <h3 style={{ margin: "0 0 8px 0" }}>Confirmar descarte de borrador</h3>
            <p style={{ margin: "0 0 12px 0", fontSize: "13.5px", color: "var(--text-muted)" }}>
              ¿Está seguro de descartar la <strong>orden #{ordenADescartar.numero_orden_paciente}</strong> de{" "}
              <strong>
                {ordenADescartar.paciente.nombres} {ordenADescartar.paciente.apellido_paterno}
              </strong>
              ? Esta acción no se puede deshacer.
            </p>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px" }}>
              <button
                type="button"
                className="lis-btn lis-btn-outline"
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
                {descartando ? "Descartando…" : "Descartar borrador"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default OrdenesPage;
