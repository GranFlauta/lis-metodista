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
