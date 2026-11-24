/**
 * Pantalla de Inicio de Sesión (Login).
 * PROMPT_FASE_1.md §9.
 */

import React, { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "./AuthProvider";
import { ApiError } from "../../api/client";
import { MarcaLaboratorio, CargaLaboratorio } from "../../components/MarcaLaboratorio";
import { BotonTema } from "../../components/TemaProvider";
import { Icono } from "../../components/Icono";

export const LoginPage: React.FC = () => {
  const { usuario, login, cargando, errorSesion, limpiarErrorSesion } = useAuth();
  const navigate = useNavigate();

  const [usuarioInput, setUsuarioInput] = useState<string>("");
  const [passwordInput, setPasswordInput] = useState<string>("");
  const [mostrarPassword, setMostrarPassword] = useState<boolean>(false);
  const [errorLocal, setErrorLocal] = useState<string | null>(null);
  const [enviando, setEnviando] = useState<boolean>(false);

  if (cargando) return <CargaLaboratorio pantalla mensaje="Preparando el acceso al laboratorio…" />;

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
    <div className="lis-login-container lis-login-screen">
      <header className="lis-login-topline lis-login-topline-icon"><BotonTema soloIcono /></header>
      <div className="lis-login-background" aria-hidden="true"><MarcaLaboratorio apariencia="tema" /></div>
      <div className="lis-login-card">
        <div className="lis-brand-header">
          <h1>BIENVENIDO AL LABORATORIO CLINICO</h1>
          <img className="lis-hospital-login-logo" src="/branding/logo-metodista.svg" alt="Hospital Metodista" />
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

        <form onSubmit={handleSubmit} className="lis-form" noValidate aria-busy={enviando}>
          <div className="lis-form-group">
            <label htmlFor="input-usuario"><Icono nombre="usuario" size={14} /> Usuario</label>
            <input
              id="input-usuario"
              type="text"
              autoComplete="username"
              required
              disabled={enviando}
              value={usuarioInput}
              onChange={(e) => setUsuarioInput(e.target.value)}
              placeholder="Ingresa tu usuario"
            />
          </div>

          <div className="lis-form-group">
            <label htmlFor="input-password"><Icono nombre="candado" size={14} /> Contraseña</label>
            <div className="lis-password-field">
              <input
                id="input-password"
                type={mostrarPassword ? "text" : "password"}
                autoComplete="current-password"
                required
                disabled={enviando}
                value={passwordInput}
                onChange={(e) => setPasswordInput(e.target.value)}
                placeholder="••••••••••••"
              />
              <button
                type="button"
                onClick={() => setMostrarPassword((prev) => !prev)}
                title={mostrarPassword ? "Ocultar contraseña" : "Ver contraseña"}
                aria-label={mostrarPassword ? "Ocultar contraseña" : "Ver contraseña"}
                aria-pressed={mostrarPassword}
                disabled={enviando}
                className="lis-password-toggle"
              >
                <Icono nombre={mostrarPassword ? "ojo" : "ojoCerrado"} />
              </button>
            </div>
          </div>

          <button
            type="submit"
            className="lis-btn lis-btn-primary lis-btn-block"
            disabled={enviando}
          >
            {enviando ? "Verificando acceso…" : "Iniciar sesión"}<Icono nombre="flecha" size={16} />
          </button>
        </form>

        {enviando && <CargaLaboratorio compacta mensaje="Verificando acceso…" />}

        <div className="lis-login-footer">
          <Icono nombre="candado" size={14} /><small>Acceso para personal autorizado del laboratorio</small>
        </div>
      </div>
    </div>
  );
};
