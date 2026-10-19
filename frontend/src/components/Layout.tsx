/**
 * Layout principal del sistema LIS con menú lateral izquierdo desplegable.
 * PROMPT_FASE_3_6_UX.md §6.1, docs/UX_GUIDE.md §2.
 */

import React, { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../features/auth/AuthProvider";
import { obtenerResumenOrdenesApi } from "../api/ordenes";

// Iconos SVG en línea (sin dependencias externas ni emojis)
const IconHome = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
    <polyline points="9 22 9 12 15 12 15 22" />
  </svg>
);

const IconPlusCircle = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <circle cx="12" cy="12" r="10" />
    <line x1="12" y1="8" x2="12" y2="16" />
    <line x1="8" y1="12" x2="16" y2="12" />
  </svg>
);

const IconUsers = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
    <circle cx="9" cy="7" r="4" />
    <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
    <path d="M16 3.13a4 4 0 0 1 0 7.75" />
  </svg>
);

const IconClipboardList = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
    <rect x="8" y="2" width="8" height="4" rx="1" ry="1" />
    <path d="M9 12h6" />
    <path d="M9 16h6" />
    <path d="M9 8h6" />
  </svg>
);

const IconUserCheck = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
    <circle cx="8.5" cy="7" r="4" />
    <polyline points="17 11 19 13 23 9" />
  </svg>
);

const IconSliders = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <line x1="4" y1="21" x2="4" y2="14" />
    <line x1="4" y1="10" x2="4" y2="3" />
    <line x1="12" y1="21" x2="12" y2="12" />
    <line x1="12" y1="8" x2="12" y2="3" />
    <line x1="20" y1="21" x2="20" y2="16" />
    <line x1="20" y1="12" x2="20" y2="3" />
    <line x1="1" y1="14" x2="7" y2="14" />
    <line x1="9" y1="8" x2="15" y2="8" />
    <line x1="17" y1="16" x2="23" y2="16" />
  </svg>
);

const IconMenu = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <line x1="3" y1="12" x2="21" y2="12" />
    <line x1="3" y1="6" x2="21" y2="6" />
    <line x1="3" y1="18" x2="21" y2="18" />
  </svg>
);

const IconKey = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M21 2l-2 2m-1.5 1.5L14 9l-1.5-1.5L10 10l2 2-6 6H2v-4l6-6 2 2 2.5-2.5L11 8l3.5-3.5L16 6l2-2 3-2z" />
  </svg>
);

const IconLogOut = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
    <polyline points="16 17 21 12 16 7" />
    <line x1="21" y1="12" x2="9" y2="12" />
  </svg>
);

function obtenerTituloPantalla(pathname: string): string {
  if (pathname === "/") return "Inicio";
  if (pathname === "/ordenes/nueva") return "Nueva orden";
  if (pathname.startsWith("/ordenes/") && pathname.endsWith("/captura")) return "Captura de resultados";
  if (pathname.startsWith("/ordenes/") && pathname !== "/ordenes") return "Detalle de orden";
  if (pathname === "/ordenes") return "Órdenes y Pendientes";
  if (pathname.startsWith("/pacientes/") && pathname !== "/pacientes") return "Ficha de paciente";
  if (pathname === "/pacientes") return "Pacientes";
  if (pathname === "/admin/usuarios") return "Administración de usuarios";
  if (pathname === "/admin/configuracion") return "Configuración de sesión";
  if (pathname === "/cambiar-password") return "Cambiar contraseña";
  return "LIS Laboratorio Clínico";
}

export const Layout: React.FC = () => {
  const { usuario, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  // Estado del menú desplegable en memoria (sin storage, D36-04)
  const [sidebarExpandido, setSidebarExpandido] = useState<boolean>(() => {
    return typeof window !== "undefined" && window.innerWidth >= 1280;
  });

  const [pendientesCount, setPendientesCount] = useState<number | null>(null);

  const esAdmin = usuario?.rol === "ADMIN";

  // Cargar contador de pendientes de B3 para BIOQUIMICO
  useEffect(() => {
    let montado = true;
    async function cargarResumen() {
      try {
        const resumen = await obtenerResumenOrdenesApi();
        if (montado) {
          setPendientesCount(resumen.pendientes);
        }
      } catch {
        // En caso de error de red, mantener el último valor
      }
    }

    cargarResumen();
    const interval = setInterval(cargarResumen, 30000);
    return () => {
      montado = false;
      clearInterval(interval);
    };
  }, [location.pathname]);

  const handleCerrarSesion = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  const toggleSidebar = () => {
    setSidebarExpandido((prev) => !prev);
  };

  const tituloPantalla = obtenerTituloPantalla(location.pathname);

  return (
    <div className="lis-app-container">
      {/* Menú lateral izquierdo desplegable */}
      <aside
        className={`lis-sidebar ${sidebarExpandido ? "lis-sidebar-expanded" : "lis-sidebar-collapsed"}`}
        aria-label="Menú principal"
      >
        <div className="lis-sidebar-header">
          <Link to="/" className="lis-sidebar-brand" title="LIS Laboratorio Clínico">
            <span className="lis-sidebar-logo">LIS</span>
            {sidebarExpandido && <span className="lis-sidebar-title">Laboratorio Metodista</span>}
          </Link>
          <button
            type="button"
            onClick={toggleSidebar}
            className="lis-sidebar-toggle-btn"
            title={sidebarExpandido ? "Colapsar menú" : "Expandir menú"}
            aria-label={sidebarExpandido ? "Colapsar menú" : "Expandir menú"}
          >
            <IconMenu />
          </button>
        </div>

        <nav className="lis-sidebar-nav">
          {/* 1. Inicio */}
          <NavLink
            to="/"
            end
            className={({ isActive }) => `lis-sidebar-link ${isActive ? "active" : ""}`}
            title="Inicio"
          >
            <span className="lis-sidebar-icon">
              <IconHome />
            </span>
            {sidebarExpandido && <span className="lis-sidebar-text">Inicio</span>}
          </NavLink>

          {/* 2. Menú de BIOQUIMICO */}
          {!esAdmin && (
            <>
              <NavLink
                to="/ordenes/nueva"
                className={({ isActive }) =>
                  `lis-sidebar-link lis-sidebar-link-featured ${isActive ? "active" : ""}`
                }
                title="Nueva orden"
              >
                <span className="lis-sidebar-icon">
                  <IconPlusCircle />
                </span>
                {sidebarExpandido && <span className="lis-sidebar-text">Nueva orden</span>}
              </NavLink>

              <NavLink
                to="/pacientes"
                className={({ isActive }) => `lis-sidebar-link ${isActive ? "active" : ""}`}
                title="Pacientes"
              >
                <span className="lis-sidebar-icon">
                  <IconUsers />
                </span>
                {sidebarExpandido && <span className="lis-sidebar-text">Pacientes</span>}
              </NavLink>

              <NavLink
                to="/ordenes"
                className={({ isActive }) => `lis-sidebar-link ${isActive ? "active" : ""}`}
                title="Pendientes"
              >
                <span className="lis-sidebar-icon">
                  <IconClipboardList />
                </span>
                {sidebarExpandido && (
                  <>
                    <span className="lis-sidebar-text">Pendientes</span>
                    {pendientesCount !== null && (
                      <span className="lis-sidebar-badge" title={`${pendientesCount} órdenes pendientes`}>
                        {pendientesCount}
                      </span>
                    )}
                  </>
                )}
                {!sidebarExpandido && pendientesCount !== null && pendientesCount > 0 && (
                  <span className="lis-sidebar-badge-dot" title={`${pendientesCount} pendientes`} />
                )}
              </NavLink>
            </>
          )}

          {/* 3. Menú de ADMIN */}
          {esAdmin && (
            <>
              <NavLink
                to="/pacientes"
                className={({ isActive }) => `lis-sidebar-link ${isActive ? "active" : ""}`}
                title="Pacientes"
              >
                <span className="lis-sidebar-icon">
                  <IconUsers />
                </span>
                {sidebarExpandido && <span className="lis-sidebar-text">Pacientes</span>}
              </NavLink>

              <NavLink
                to="/ordenes"
                className={({ isActive }) => `lis-sidebar-link ${isActive ? "active" : ""}`}
                title="Órdenes"
              >
                <span className="lis-sidebar-icon">
                  <IconClipboardList />
                </span>
                {sidebarExpandido && <span className="lis-sidebar-text">Órdenes</span>}
              </NavLink>

              <div className="lis-sidebar-section-divider" />
              {sidebarExpandido && (
                <span className="lis-sidebar-section-title">Administración</span>
              )}

              <NavLink
                to="/admin/usuarios"
                className={({ isActive }) => `lis-sidebar-link ${isActive ? "active" : ""}`}
                title="Usuarios"
              >
                <span className="lis-sidebar-icon">
                  <IconUserCheck />
                </span>
                {sidebarExpandido && <span className="lis-sidebar-text">Usuarios</span>}
              </NavLink>

              <NavLink
                to="/admin/configuracion"
                className={({ isActive }) => `lis-sidebar-link ${isActive ? "active" : ""}`}
                title="Configuración de sesión"
              >
                <span className="lis-sidebar-icon">
                  <IconSliders />
                </span>
                {sidebarExpandido && <span className="lis-sidebar-text">Configuración</span>}
              </NavLink>
            </>
          )}
        </nav>

        {/* Pie del menú */}
        <div className="lis-sidebar-footer">
          <div className="lis-sidebar-user-block">
            {sidebarExpandido ? (
              <>
                <div className="lis-sidebar-user-name">
                  {usuario?.nombres} {usuario?.apellido_paterno}
                </div>
                <div className="lis-sidebar-user-role">
                  <span className={`lis-role-badge lis-role-${usuario?.rol?.toLowerCase()}`}>
                    {usuario?.rol}
                  </span>
                </div>
              </>
            ) : (
              <span className={`lis-role-badge-mini lis-role-${usuario?.rol?.toLowerCase()}`} title={`${usuario?.nombres} (${usuario?.rol})`}>
                {usuario?.rol?.charAt(0)}
              </span>
            )}
          </div>

          <div className="lis-sidebar-actions">
            <NavLink
              to="/cambiar-password"
              className="lis-sidebar-action-btn"
              title="Cambiar Contraseña"
            >
              <IconKey />
              {sidebarExpandido && <span>Clave</span>}
            </NavLink>
            <button
              type="button"
              onClick={handleCerrarSesion}
              className="lis-sidebar-action-btn lis-sidebar-logout-btn"
              title="Cerrar Sesión Activa"
            >
              <IconLogOut />
              {sidebarExpandido && <span>Salir</span>}
            </button>
          </div>
        </div>
      </aside>

      {/* Contenido principal con barra superior mínima */}
      <div className="lis-main-wrapper">
        <header className="lis-topbar">
          <div className="lis-topbar-left">
            <h1 className="lis-topbar-title">{tituloPantalla}</h1>
          </div>
          <div className="lis-topbar-right">
            <span className="lis-topbar-system-name">LIS Laboratorio Metodista</span>
          </div>
        </header>

        <main className="lis-content-area">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
