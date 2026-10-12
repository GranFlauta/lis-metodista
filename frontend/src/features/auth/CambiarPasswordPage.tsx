/**
 * Pantalla para Cambio de Contraseña (Obligatorio o Voluntario).
 * PROMPT_FASE_1.md §6.2 y §9.
 */

import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { cambiarPasswordApi } from "../../api/auth";
import { useAuth } from "./AuthProvider";
import { ApiError } from "../../api/client";

export const CambiarPasswordPage: React.FC = () => {
  const { usuario, marcarPasswordCambiado, logout } = useAuth();
  const navigate = useNavigate();

  const [passwordActual, setPasswordActual] = useState<string>("");
  const [passwordNueva, setPasswordNueva] = useState<string>("");
  const [confirmarPassword, setConfirmarPassword] = useState<string>("");
  const [errorLocal, setErrorLocal] = useState<string | null>(null);
  const [exito, setExito] = useState<boolean>(false);
  const [enviando, setEnviando] = useState<boolean>(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorLocal(null);

    if (!passwordActual) {
      setErrorLocal("Debe ingresar su contraseña actual.");
      return;
    }

    if (passwordNueva.length < 10) {
      setErrorLocal("La nueva contraseña debe tener al menos 10 caracteres.");
      return;
    }

    if (passwordNueva.length > 128) {
      setErrorLocal("La nueva contraseña no puede exceder 128 caracteres.");
      return;
    }

    if (passwordNueva === passwordActual) {
      setErrorLocal("La nueva contraseña debe ser distinta de la actual.");
      return;
    }

    if (passwordNueva !== confirmarPassword) {
      setErrorLocal("La confirmación no coincide con la nueva contraseña.");
      return;
    }

    setEnviando(true);
    try {
      await cambiarPasswordApi({
        password_actual: passwordActual,
        password_nueva: passwordNueva,
      });

      marcarPasswordCambiado();
      setExito(true);

      setTimeout(() => {
        navigate("/", { replace: true });
      }, 1500);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setErrorLocal(err.message);
      } else {
        setErrorLocal("Error al comunicarse con el servidor.");
      }
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div className="lis-login-container">
      <div className="lis-login-card">
        <div className="lis-brand-header">
          <div className="lis-brand-badge">SEGURIDAD</div>
          <h1>Actualización de Contraseña</h1>
          {usuario?.debe_cambiar_password ? (
            <p className="lis-brand-sub lis-text-warning">
              Es obligatorio cambiar su contraseña inicial para poder utilizar el sistema.
            </p>
          ) : (
            <p className="lis-brand-sub">Actualice su clave de acceso clínico.</p>
          )}
        </div>

        {errorLocal && (
          <div className="lis-alert lis-alert-error" role="alert">
            <span className="lis-alert-icon">⛔</span>
            <span>{errorLocal}</span>
          </div>
        )}

        {exito && (
          <div className="lis-alert lis-alert-success" role="alert">
            <span className="lis-alert-icon">✅</span>
            <span>Contraseña actualizada correctamente. Redirigiendo al sistema...</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="lis-form" noValidate>
          <div className="lis-form-group">
            <label htmlFor="input-pwd-actual">Contraseña Actual o Temporal</label>
            <input
              id="input-pwd-actual"
              type="password"
              autoComplete="current-password"
              required
              disabled={enviando || exito}
              value={passwordActual}
              onChange={(e) => setPasswordActual(e.target.value)}
              placeholder="••••••••••••"
            />
          </div>

          <div className="lis-form-group">
            <label htmlFor="input-pwd-nueva">Nueva Contraseña (mín. 10 caracteres)</label>
            <input
              id="input-pwd-nueva"
              type="password"
              autoComplete="new-password"
              required
              disabled={enviando || exito}
              value={passwordNueva}
              onChange={(e) => setPasswordNueva(e.target.value)}
              placeholder="••••••••••••"
            />
            <small className="lis-input-hint">
              No debe contener su nombre ni su CI, ni palabras comunes como 'admin' o '123456'.
            </small>
          </div>

          <div className="lis-form-group">
            <label htmlFor="input-pwd-confirmar">Confirmar Nueva Contraseña</label>
            <input
              id="input-pwd-confirmar"
              type="password"
              autoComplete="new-password"
              required
              disabled={enviando || exito}
              value={confirmarPassword}
              onChange={(e) => setConfirmarPassword(e.target.value)}
              placeholder="••••••••••••"
            />
          </div>

          <div className="lis-form-actions">
            <button
              type="submit"
              className="lis-btn lis-btn-primary lis-btn-block"
              disabled={enviando || exito}
            >
              {enviando ? "Guardando..." : "Guardar Nueva Contraseña"}
            </button>

            <button
              type="button"
              className="lis-btn lis-btn-secondary lis-btn-block"
              onClick={() => logout()}
              disabled={enviando}
            >
              Cancelar y Salir
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
