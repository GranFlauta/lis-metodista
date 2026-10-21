/**
 * Pantalla de Inicio (Acciones rápidas y panel horizontal de Recientes).
 * PROMPT_FASE_3_6_UX.md §6.2, docs/UX_GUIDE.md §2.
 */

import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listarOrdenesApi, obtenerResumenOrdenesApi, OrdenListItem } from "../../api/ordenes";
import { useAuth } from "../auth/AuthProvider";

// Iconos SVG en línea sobrios
const IconPlus = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <line x1="12" y1="5" x2="12" y2="19" />
    <line x1="5" y1="12" x2="19" y2="12" />
  </svg>
);

const IconSearch = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <circle cx="11" cy="11" r="8" />
    <line x1="21" y1="21" x2="16.65" y2="16.65" />
  </svg>
);

const IconClock = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <circle cx="12" cy="12" r="10" />
    <polyline points="12 6 12 12 16 14" />
  </svg>
);

const IconUsers = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
    <circle cx="9" cy="7" r="4" />
    <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
    <path d="M16 3.13a4 4 0 0 1 0 7.75" />
  </svg>
);

const IconList = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <line x1="8" y1="6" x2="21" y2="6" />
    <line x1="8" y1="12" x2="21" y2="12" />
    <line x1="8" y1="18" x2="21" y2="18" />
    <line x1="3" y1="6" x2="3.01" y2="6" />
    <line x1="3" y1="12" x2="3.01" y2="12" />
    <line x1="3" y1="18" x2="3.01" y2="18" />
  </svg>
);

const IconShare2 = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <circle cx="18" cy="5" r="3" />
    <circle cx="6" cy="12" r="3" />
    <circle cx="18" cy="19" r="3" />
    <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" />
    <line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
  </svg>
);

const IconHistory = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
    <path d="M3 3v5h5" />
    <path d="M12 7v5l4 2" />
  </svg>
);

const IconClipboard = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
    <rect x="8" y="2" width="8" height="4" rx="1" ry="1" />
  </svg>
);

const IconPrinter = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <polyline points="6 9 6 2 18 2 18 9" />
    <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" />
    <rect x="6" y="14" width="12" height="8" />
  </svg>
);

const IconTrash2 = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <polyline points="3 6 5 6 21 6" />
    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
    <line x1="10" y1="11" x2="10" y2="17" />
    <line x1="14" y1="11" x2="14" y2="17" />
  </svg>
);

function formatearHora(isoString: string | null | undefined): string {
  if (!isoString) return "—";
  try {
    const fecha = new Date(isoString);
    if (isNaN(fecha.getTime())) return "—";
    const horas = String(fecha.getHours()).padStart(2, "0");
    const minutos = String(fecha.getMinutes()).padStart(2, "0");
    return `${horas}:${minutos}`;
  } catch {
    return "—";
  }
}

export const HomePage: React.FC = () => {
  const { usuario } = useAuth();
  const esAdmin = usuario?.rol === "ADMIN";

  const [recientes, setRecientes] = useState<OrdenListItem[]>([]);
  const [pendientesCount, setPendientesCount] = useState<number | null>(null);
  const [cargando, setCargando] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let montado = true;

    async function cargarDatos() {
      setCargando(true);
      setError(null);
      try {
        const [ordenesResp, resumenResp] = await Promise.all([
          listarOrdenesApi({ limit: 15 }),
          obtenerResumenOrdenesApi().catch(() => null),
        ]);

        if (!montado) return;
        setRecientes(ordenesResp.items);
        if (resumenResp) {
          setPendientesCount(resumenResp.pendientes);
        }
      } catch (err: unknown) {
        if (montado) {
          setError("No se pudieron cargar los trabajos recientes.");
        }
      } finally {
        if (montado) {
          setCargando(false);
        }
      }
    }

    cargarDatos();

    return () => {
      montado = false;
    };
  }, []);

  return (
    <div className="lis-home-container">
      {/* 1. Fila de acciones rápidas (botones grandes) */}
      <div className="lis-quick-actions" role="region" aria-label="Acciones rápidas">
        {!esAdmin && (
          <Link to="/ordenes/nueva" className="lis-btn-quick lis-btn-quick-primary">
            <IconPlus />
            <span>Nueva orden</span>
          </Link>
        )}

        <Link to="/pacientes" className="lis-btn-quick">
          <IconSearch />
          <span>Buscar paciente</span>
        </Link>

        {!esAdmin && (
          <Link to="/ordenes" className="lis-btn-quick">
            <IconClock />
            <span>
              Mis pendientes {pendientesCount !== null ? `(${pendientesCount})` : ""}
            </span>
          </Link>
        )}

        {esAdmin && (
          <>
            <Link to="/ordenes" className="lis-btn-quick">
              <IconList />
              <span>Órdenes</span>
            </Link>
            <Link to="/admin/usuarios" className="lis-btn-quick">
              <IconUsers />
              <span>Usuarios</span>
            </Link>
          </>
        )}
      </div>

      {/* Menú Horizontal de Módulos Complementarios (§8) */}
      <div className="lis-modulos-futuros-bar" role="region" aria-label="Módulos complementarios">
        <button type="button" className="lis-modulo-btn" title="Módulo colaborativo en desarrollo">
          <span className="lis-modulo-btn-title">
            <IconShare2 /> Órdenes colaborativas
          </span>
          <span className="lis-modulo-btn-sub">(Próximamente)</span>
        </button>

        <button type="button" className="lis-modulo-btn" title="Histórico y recuperación de estados">
          <span className="lis-modulo-btn-title">
            <IconHistory /> Restaurados
          </span>
          <span className="lis-modulo-btn-sub">(Próximamente)</span>
        </button>

        <button type="button" className="lis-modulo-btn" title="Consolidado de historial clínico por paciente">
          <span className="lis-modulo-btn-title">
            <IconClipboard /> Historial clínico
          </span>
          <span className="lis-modulo-btn-sub">(Próximamente)</span>
        </button>

        <button type="button" className="lis-modulo-btn" title="Impresión centralizada por lotes">
          <span className="lis-modulo-btn-title">
            <IconPrinter /> Imprimir
          </span>
          <span className="lis-modulo-btn-sub">(Próximamente)</span>
        </button>

        <button type="button" className="lis-modulo-btn" title="Gestión de órdenes y descartes">
          <span className="lis-modulo-btn-title">
            <IconTrash2 /> Papelera
          </span>
          <span className="lis-modulo-btn-sub">(Próximamente)</span>
        </button>
      </div>

      {/* 2. Panel horizontal 'Recientes' a todo el ancho (últimos 15 trabajos) */}
      <section className="lis-recientes-panel" aria-label="Trabajos recientes">
        <div className="lis-recientes-header">
          <h2 className="lis-recientes-title">Recientes</h2>
          <span className="lis-text-muted" style={{ fontSize: "13px" }}>
            Últimos 15 trabajos
          </span>
        </div>

        {cargando && (
          <div className="lis-table-loading">Cargando trabajos recientes…</div>
        )}

        {error && (
          <div className="lis-alert lis-alert-error" role="alert">
            {error}
          </div>
        )}

        {!cargando && !error && recientes.length === 0 && (
          <div className="lis-empty-state">
            <p className="lis-empty-state-message">Aún no hay trabajos hoy</p>
            {!esAdmin && (
              <Link to="/ordenes/nueva" className="lis-btn lis-btn-primary">
                Nueva orden
              </Link>
            )}
          </div>
        )}

        {!cargando && !error && recientes.length > 0 && (
          <div className="lis-table-responsive">
            <table className="lis-table lis-table-dense">
              <thead>
                <tr>
                  <th style={{ minWidth: "220px" }}>Paciente</th>
                  <th>Estudios</th>
                  <th style={{ width: "120px" }}>Estado</th>
                  <th style={{ width: "110px" }}>Hora de inicio</th>
                  {esAdmin && <th style={{ width: "160px" }}>Autor</th>}
                  <th className="lis-text-right" style={{ width: "110px" }}>
                    Acción
                  </th>
                </tr>
              </thead>
              <tbody>
                {recientes.map((orden) => (
                  <tr key={orden.id}>
                    <td>
                      <div className="lis-cell-paciente">
                        <span className="lis-paciente-nombre">
                          {orden.paciente.apellido_paterno}{" "}
                          {orden.paciente.apellido_materno || ""}{" "}
                          {orden.paciente.nombres}
                        </span>
                        <span className="lis-paciente-ci">
                          {orden.paciente.ci ? `CI ${orden.paciente.ci}` : "Sin CI"}
                        </span>
                      </div>
                    </td>
                    <td>
                      <div className="lis-chips-container">
                        {orden.estudios_detalle && orden.estudios_detalle.length > 0
                          ? orden.estudios_detalle.map((ed) => (
                              <span
                                key={ed.codigo}
                                className="lis-chip"
                                title={ed.nombre}
                              >
                                {ed.codigo}
                              </span>
                            ))
                          : orden.estudios.map((cod) => (
                              <span key={cod} className="lis-chip">
                                {cod}
                              </span>
                            ))}
                      </div>
                    </td>
                    <td>
                      <span
                        className={`lis-status-badge lis-status-${orden.estado_trabajo.toLowerCase()}`}
                      >
                        {orden.estado_trabajo}
                      </span>
                    </td>
                    <td>
                      {formatearHora(orden.fecha_hora_toma_muestra || orden.creado_en)}
                    </td>
                    {esAdmin && (
                      <td>
                        {orden.autor
                          ? `${orden.autor.nombres} ${orden.autor.apellido_paterno}`
                          : "—"}
                      </td>
                    )}
                    <td className="lis-text-right">
                      <Link
                        to={`/ordenes/${orden.id}/captura`}
                        className="lis-btn lis-btn-primary lis-btn-sm"
                        title="Continuar captura de resultados"
                      >
                        Continuar
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
};
