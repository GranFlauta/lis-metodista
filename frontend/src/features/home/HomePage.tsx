/**
 * Pantalla de Inicio (Dashboard de bienvenida).
 * PROMPT_FASE_1.md §9: inicio con saludo al usuario y rol.
 */

import React from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";

export const HomePage: React.FC = () => {
  const { usuario } = useAuth();

  const esAdmin = usuario?.rol === "ADMIN";

  return (
    <div className="lis-page-container">
      <div className="lis-welcome-card">
        <div className="lis-welcome-header">
          <span className="lis-welcome-icon">👋</span>
          <div>
            <h2>Bienvenido(a), {usuario?.nombres} {usuario?.apellido_paterno}</h2>
            <p className="lis-text-muted">
              Sesión iniciada como{" "}
              <strong className={`lis-role-badge lis-role-${usuario?.rol?.toLowerCase()}`}>
                {usuario?.rol}
              </strong>
            </p>
          </div>
        </div>

        <div className="lis-welcome-body">
          <p>
            El sistema de autenticación, control de sesiones por latido clínico y gestión de
            usuarios se encuentra activo y operativo.
          </p>

          <div className="lis-welcome-cards-grid">
            {esAdmin ? (
              <div className="lis-action-card">
                <h3>Administración de Usuarios</h3>
                <p>Cree nuevos usuarios, gestione permisos, realice bajas lógicas y reseteo de claves.</p>
                <Link to="/admin/usuarios" className="lis-btn lis-btn-primary">
                  Ir a Usuarios →
                </Link>
              </div>
            ) : (
              <div className="lis-action-card">
                <h3>Perfil Bioquímico</h3>
                <p>Su cuenta está habilitada para la captura, cálculo y validación de determinaciones clínicas.</p>
                <span className="lis-badge-soon">Módulo de Órdenes: Próximamente en Fase 2</span>
              </div>
            )}

            <div className="lis-action-card lis-card-muted">
              <h3>Seguridad de la Cuenta</h3>
              <p>Su sesión se mantiene activa de forma segura mediante latidos en segundo plano.</p>
              <Link to="/cambiar-password" className="lis-btn lis-btn-secondary">
                Cambiar Contraseña
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
