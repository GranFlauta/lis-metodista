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
  const [mostrarPassword, setMostrarPassword] = useState<boolean>(false);
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
          <div style={{ backgroundColor: "#ffffff", padding: "8px", borderRadius: "12px", display: "inline-block", margin: "0 auto 8px auto", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
            <img
              src="/logo-metodista.svg"
              alt="Hospital Metodista"
              style={{ maxHeight: "75px", width: "auto", objectFit: "contain", display: "block" }}
            />
          </div>
          <h1 style={{ fontFamily: "'Bernard MT Condensed', sans-serif, system-ui", letterSpacing: "0.04em", fontSize: "1.35rem", textTransform: "uppercase", color: "#1e293b", margin: "4px 0" }}>
            Hospital Metodista
          </h1>
          <p className="lis-brand-sub" style={{ fontWeight: 600, color: "var(--primary)" }}>
            Laboratorio de Análisis Clínicos · LIS
          </p>
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
            <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
              <input
                id="input-password"
                type={mostrarPassword ? "text" : "password"}
                autoComplete="current-password"
                required
                disabled={enviando}
                value={passwordInput}
                onChange={(e) => setPasswordInput(e.target.value)}
                placeholder="••••••••••••"
                style={{ paddingRight: "40px", width: "100%" }}
              />
              <button
                type="button"
                onClick={() => setMostrarPassword((prev) => !prev)}
                title={mostrarPassword ? "Ocultar contraseña" : "Ver contraseña"}
                aria-label={mostrarPassword ? "Ocultar contraseña" : "Ver contraseña"}
                style={{
                  position: "absolute",
                  right: "8px",
                  background: "transparent",
                  border: "none",
                  cursor: "pointer",
                  color: mostrarPassword ? "var(--primary)" : "#94a3b8",
                  padding: "4px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  borderRadius: "4px",
                }}
              >
                {mostrarPassword ? (
                  /* Ojo visible */
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                    <circle cx="12" cy="12" r="3" fill="#E51900" />
                  </svg>
                ) : (
                  /* Ojo tachado */
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                    <line x1="1" y1="1" x2="23" y2="23" />
                  </svg>
                )}
              </button>
            </div>
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
