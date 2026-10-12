/**
 * Layout principal del sistema LIS con menú por rol y control de sesión.
 * PROMPT_FASE_1.md §4.2, §9.
 */

import React from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../features/auth/AuthProvider";

export const Layout: React.FC = () => {
  const { usuario, logout } = useAuth();
  const navigate = useNavigate();

  const handleCerrarSesion = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  const esAdmin = usuario?.rol === "ADMIN";

  return (
    <div className="lis-app-layout">
      <header className="lis-navbar">
        <div className="lis-navbar-brand">
          <Link to="/" className="lis-logo-link">
            <span className="lis-logo-icon">🔬</span>
            <span className="lis-logo-text">LIS Laboratorio Clínico</span>
          </Link>
        </div>

        <nav className="lis-nav-menu" aria-label="Navegación principal">
          <NavLink
            to="/"
            end
            className={({ isActive }) => `lis-nav-item ${isActive ? "active" : ""}`}
          >
            Inicio
          </NavLink>

          {/* Menú de administración: SOLO VISIBLE PARA ADMIN (§9) */}
          {esAdmin && (
            <NavLink
              to="/admin/usuarios"
              className={({ isActive }) => `lis-nav-item ${isActive ? "active" : ""}`}
            >
              Administración de Usuarios
            </NavLink>
          )}

          {/* Enlaces futuros: deshabilitados con texto 'Próximamente' (§4.2) */}
          <span className="lis-nav-item lis-nav-disabled" title="Disponible en Fase 2">
            Órdenes <span className="lis-badge-soon">Próximamente</span>
          </span>
          <span className="lis-nav-item lis-nav-disabled" title="Disponible en Fase 2">
            Pacientes <span className="lis-badge-soon">Próximamente</span>
          </span>
          <span className="lis-nav-item lis-nav-disabled" title="Disponible en Fase 3">
            Informes <span className="lis-badge-soon">Próximamente</span>
          </span>
        </nav>

        <div className="lis-navbar-user">
          <div className="lis-user-info">
            <span className="lis-user-name">
              {usuario?.nombres} {usuario?.apellido_paterno}
            </span>
            <span className={`lis-role-badge lis-role-${usuario?.rol?.toLowerCase()}`}>
              {usuario?.rol}
            </span>
          </div>

          <div className="lis-user-actions">
            <NavLink
              to="/cambiar-password"
              className="lis-btn lis-btn-text"
              title="Cambiar Contraseña"
            >
              Clave
            </NavLink>
            <button
              type="button"
              onClick={handleCerrarSesion}
              className="lis-btn lis-btn-outline lis-btn-sm"
              title="Cerrar Sesión Activa"
            >
              Salir
            </button>
          </div>
        </div>
      </header>

      <main className="lis-main-content">
        <Outlet />
      </main>

      <footer className="lis-footer">
        <div className="lis-footer-content">
          <span>LIS Laboratorio Clínico — Sistema Clínico On-Premise</span>
          <span>Sesión activa protegida con latido clínico</span>
        </div>
      </footer>
    </div>
  );
};
