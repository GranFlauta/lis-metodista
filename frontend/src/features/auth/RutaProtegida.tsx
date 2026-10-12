/**
 * Componente de protección de rutas según rol y estado de contraseña.
 * PROMPT_FASE_1.md §9.
 */

import React from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "./AuthProvider";

interface RutaProtegidaProps {
  children: React.ReactNode;
  rolRequerido?: "ADMIN" | "BIOQUIMICO";
}

export const RutaProtegida: React.FC<RutaProtegidaProps> = ({ children, rolRequerido }) => {
  const { usuario, cargando } = useAuth();
  const location = useLocation();

  if (cargando) {
    return (
      <div className="lis-loading-screen">
        <div className="lis-spinner" />
        <p>Cargando sesión clínica...</p>
      </div>
    );
  }

  // 1. Sin autenticación -> ir a login
  if (!usuario) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // 2. Si debe cambiar contraseña y no está ya en la pantalla de cambio -> forzar cambio
  if (usuario.debe_cambiar_password && location.pathname !== "/cambiar-password") {
    return <Navigate to="/cambiar-password" replace />;
  }

  // 3. Control de rol (ej. ADMIN para /admin/usuarios)
  if (rolRequerido && usuario.rol !== rolRequerido) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
};
