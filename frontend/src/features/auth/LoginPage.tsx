/**
 * Pantalla de Inicio de Sesión (Login).
 * PROMPT_FASE_1.md §9.
 */

import React, { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "./AuthProvider";
import { ApiError } from "../../api/client";

export const LoginPage: React.FC = () => {
  const { usuario, login, errorSesion, limpiarErrorSesion } = useAuth();
  const navigate = useNavigate();

  const [usuarioInput, setUsuarioInput] = useState<string>("");
  const [passwordInput, setPasswordInput] = useState<string>("");
  const [errorLocal, setErrorLocal] = useState<string | null>(null);
  const [enviando, setEnviando] = useState<boolean>(false);

  // Si ya tiene sesión activa
  if (usuario) {
    if (usuario.debe_cambiar_password) {
      return <Navigate to="/cambiar-password" replace />;
    }
    return <Navigate to="/" replace />;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorLocal(null);
    limpiarErrorSesion();

    if (!usuarioInput.trim() || !passwordInput) {
      setErrorLocal("Por favor, ingrese su usuario y contraseña.");
      return;
    }

    setEnviando(true);
    try {
      const resp = await login({
        usuario: usuarioInput.trim(),
        password: passwordInput,
      });

      if (resp.debe_cambiar_password) {
        navigate("/cambiar-password", { replace: true });
      } else {
        navigate("/", { replace: true });
      }
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setErrorLocal(err.message);
      } else {
        setErrorLocal("No fue posible comunicarse con el servidor.");
      }
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div className="lis-login-container">
      <div className="lis-login-card">
        <div className="lis-brand-header">
          <div className="lis-brand-badge">LIS</div>
          <h1>Laboratorio Clínico</h1>
          <p className="lis-brand-sub">Sistema de Gestión e Informes de Laboratorio</p>
        </div>

        {errorSesion && (
          <div className="lis-alert lis-alert-warning" role="alert">
            <span>{errorSesion}</span>
          </div>
        )}

        {errorLocal && (
          <div className="lis-alert lis-alert-error" role="alert">
            <span>{errorLocal}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="lis-form" noValidate>
          <div className="lis-form-group">
            <label htmlFor="input-usuario">Usuario (Login)</label>
            <input
              id="input-usuario"
              type="text"
              autoComplete="username"
              required
              disabled={enviando}
              value={usuarioInput}
              onChange={(e) => setUsuarioInput(e.target.value)}
              placeholder="ej. mlopez"
            />
          </div>

          <div className="lis-form-group">
            <label htmlFor="input-password">Contraseña</label>
            <input
              id="input-password"
              type="password"
              autoComplete="current-password"
              required
              disabled={enviando}
              value={passwordInput}
              onChange={(e) => setPasswordInput(e.target.value)}
              placeholder="••••••••••••"
            />
          </div>

          <button
            type="submit"
            className="lis-btn lis-btn-primary lis-btn-block"
            disabled={enviando}
          >
            {enviando ? "Verificando credenciales..." : "Iniciar Sesión"}
          </button>
        </form>

        <div className="lis-login-footer">
          <small>Acceso restringido para personal médico y bioquímico autorizado.</small>
        </div>
      </div>
    </div>
  );
};
