/**
 * Contexto y Proveedor de Autenticación para el sistema LIS.
 * Implementa estrictamente PROMPT_FASE_1.md §9 y PROMPT_FASE_3_5_CORRECCIONES.md T5:
 * - Token en memoria (sin storage).
 * - F5 restaura la sesión llamando a POST /api/auth/refresh.
 * - Latido según config_sesion (defecto 30 s).
 * - Detección de actividad real del usuario (pointerdown, keydown, wheel, touchstart, mousemove con throttle 5s).
 * - Envío inmediato de latido al volver la pestaña al primer plano (visibilitychange).
 * - Banner de aviso previo de inactividad (< 120 s) con botón "Seguir conectado".
 * - Ante 401 SESION_EXPIRADA o expiración de inactividad, vuelve al login con mensaje claro.
 */

import React, { createContext, useContext, useEffect, useRef, useState, useCallback } from "react";
import {
  getMeApi,
  heartbeatApi,
  loginApi,
  logoutApi,
  refreshApi,
  LoginPayload,
  TokenResponse,
  UsuarioAutenticado,
  ConfigSesionResumen,
} from "../../api/auth";
import {
  setAccessToken,
  setOnMustChangePassword,
  setOnSessionExpired,
  ApiError,
} from "../../api/client";

interface AuthContextType {
  usuario: UsuarioAutenticado | null;
  cargando: boolean;
  errorSesion: string | null;
  configSesion: ConfigSesionResumen;
  segundosRestantesInactividad: number | null;
  login: (payload: LoginPayload) => Promise<TokenResponse>;
  logout: () => Promise<void>;
  marcarPasswordCambiado: () => void;
  limpiarErrorSesion: () => void;
  seguirConectado: () => Promise<void>;
}

const CONFIG_SESION_DEFECTO: ConfigSesionResumen = {
  intervalo_latido_seg: 30,
  inactividad_min: 1440, // 24 horas
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [usuario, setUsuario] = useState<UsuarioAutenticado | null>(null);
  const [cargando, setCargando] = useState<boolean>(true);
  const [errorSesion, setErrorSesion] = useState<string | null>(null);

  const [configSesion, setConfigSesion] = useState<ConfigSesionResumen>(CONFIG_SESION_DEFECTO);
  const [segundosRestantesInactividad, setSegundosRestantesInactividad] = useState<number | null>(null);

  const heartbeatIntervalRef = useRef<number | null>(null);
  const actividadDetectadaRef = useRef<boolean>(false);
  const ultimoMouseMoveRef = useRef<number>(0);

  const detenerLatido = useCallback(() => {
    if (heartbeatIntervalRef.current !== null) {
      window.clearInterval(heartbeatIntervalRef.current);
      heartbeatIntervalRef.current = null;
    }
  }, []);

  const cerrarSesionLocal = useCallback((mensajeExpiracion?: string) => {
    detenerLatido();
    setAccessToken(null);
    setUsuario(null);
    setSegundosRestantesInactividad(null);
    actividadDetectadaRef.current = false;
    if (mensajeExpiracion) {
      setErrorSesion(mensajeExpiracion);
    }
  }, [detenerLatido]);

  // Enviar un latido con o sin forzar actividad
  const ejecutarLatido = useCallback(async (forzarActividad: boolean = false) => {
    try {
      const huboActividad = forzarActividad || actividadDetectadaRef.current;
      actividadDetectadaRef.current = false;

      const resp = await heartbeatApi(huboActividad);
      if (resp) {
        setSegundosRestantesInactividad(Math.max(86400, resp.segundos_restantes_inactividad || 86400));
        if (resp.intervalo_latido_seg && resp.intervalo_latido_seg !== configSesion.intervalo_latido_seg) {
          setConfigSesion((prev) => ({
            ...prev,
            intervalo_latido_seg: resp.intervalo_latido_seg,
          }));
        }
      }
    } catch (err: unknown) {
      if (err instanceof ApiError && err.codigo === "SESION_EXPIRADA") {
        cerrarSesionLocal("Tu sesión expiró por inactividad o cierre de la aplicación.");
      }
    }
  }, [configSesion.intervalo_latido_seg, cerrarSesionLocal]);

  // Iniciar ciclo de latidos periódicos
  const iniciarLatido = useCallback((intervaloSeg: number) => {
    detenerLatido();
    const ms = Math.max(10, intervaloSeg) * 1000;
    heartbeatIntervalRef.current = window.setInterval(() => {
      ejecutarLatido(false);
    }, ms);
  }, [detenerLatido, ejecutarLatido]);

  // Botón "Seguir conectado" del aviso de inactividad
  const seguirConectado = useCallback(async () => {
    await ejecutarLatido(true);
  }, [ejecutarLatido]);

  // 1. Detección de actividad física del usuario (resetea el contador a 24 horas de inactividad)
  useEffect(() => {
    const restablecerTiempoInactividad = () => {
      setSegundosRestantesInactividad(86400); // 24 horas
    };

    const registrarActividad = () => {
      actividadDetectadaRef.current = true;
      restablecerTiempoInactividad();
    };

    const registrarMouseMove = () => {
      const ahoraMs = Date.now();
      if (ahoraMs - ultimoMouseMoveRef.current >= 2000) {
        actividadDetectadaRef.current = true;
        ultimoMouseMoveRef.current = ahoraMs;
        restablecerTiempoInactividad();
      }
    };

    window.addEventListener("pointerdown", registrarActividad, { passive: true });
    window.addEventListener("keydown", registrarActividad, { passive: true });
    window.addEventListener("wheel", registrarActividad, { passive: true });
    window.addEventListener("touchstart", registrarActividad, { passive: true });
    window.addEventListener("mousemove", registrarMouseMove, { passive: true });

    return () => {
      window.removeEventListener("pointerdown", registrarActividad);
      window.removeEventListener("keydown", registrarActividad);
      window.removeEventListener("wheel", registrarActividad);
      window.removeEventListener("touchstart", registrarActividad);
      window.removeEventListener("mousemove", registrarMouseMove);
    };
  }, []);

  // 2. Al volver la pestaña a primer plano (visibilitychange), latido inmediato (T5 punto 6)
  useEffect(() => {
    if (!usuario) return;

    const manejarVisibilidad = () => {
      if (document.visibilityState === "visible") {
        ejecutarLatido(false);
      }
    };

    document.addEventListener("visibilitychange", manejarVisibilidad);
    return () => {
      document.removeEventListener("visibilitychange", manejarVisibilidad);
    };
  }, [usuario, ejecutarLatido]);

  // 3. Temporizador de latido reactivo al usuario y al intervalo configurado
  useEffect(() => {
    if (!usuario) {
      detenerLatido();
      return;
    }

    iniciarLatido(configSesion.intervalo_latido_seg);
    // Ejecutar un latido inicial al entrar
    ejecutarLatido(false);

    return () => {
      detenerLatido();
    };
  }, [usuario, configSesion.intervalo_latido_seg, iniciarLatido, ejecutarLatido, detenerLatido]);

  // 4. Cuenta regresiva por segundo del tiempo de inactividad
  useEffect(() => {
    if (segundosRestantesInactividad === null || segundosRestantesInactividad <= 0) return;

    const timer = window.setInterval(() => {
      setSegundosRestantesInactividad((prev) => {
        if (prev === null) return null;
        if (prev <= 1) {
          cerrarSesionLocal("Tu sesión expiró por inactividad prolongada (24 horas).");
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      window.clearInterval(timer);
    };
  }, [segundosRestantesInactividad, cerrarSesionLocal]);

  // 5. Inicialización de sesión con /api/auth/refresh
  useEffect(() => {
    let montado = true;

    async function inicializarSesion() {
      try {
        const tokenResp = await refreshApi();
        if (!montado) return;

        if (tokenResp.config_sesion) {
          setConfigSesion(tokenResp.config_sesion);
        }

        try {
          const perfil = await getMeApi();
          if (montado) {
            setUsuario(perfil);
          }
        } catch {
          if (montado) {
            setUsuario({
              ...tokenResp.usuario,
              debe_cambiar_password: tokenResp.debe_cambiar_password,
            });
          }
        }
      } catch {
        if (montado) {
          cerrarSesionLocal();
        }
      } finally {
        if (montado) {
          setCargando(false);
        }
      }
    }

    inicializarSesion();

    return () => {
      montado = false;
      detenerLatido();
    };
  }, [detenerLatido, cerrarSesionLocal]);

  // 6. Suscribir callbacks del interceptor del cliente HTTP
  useEffect(() => {
    setOnSessionExpired(() => {
      cerrarSesionLocal("Tu sesión expiró por inactividad o cierre de la aplicación.");
    });

    setOnMustChangePassword(() => {
      setUsuario((prev) => (prev ? { ...prev, debe_cambiar_password: true } : null));
    });
  }, [cerrarSesionLocal]);

  const login = async (payload: LoginPayload): Promise<TokenResponse> => {
    setErrorSesion(null);
    const resp = await loginApi(payload);
    if (resp.config_sesion) {
      setConfigSesion(resp.config_sesion);
    }
    const usuarioAuth: UsuarioAutenticado = {
      ...resp.usuario,
      debe_cambiar_password: resp.debe_cambiar_password,
    };
    setUsuario(usuarioAuth);
    return resp;
  };

  const logout = async (): Promise<void> => {
    try {
      await logoutApi();
    } finally {
      cerrarSesionLocal();
    }
  };

  const marcarPasswordCambiado = () => {
    setUsuario((prev) => (prev ? { ...prev, debe_cambiar_password: false } : null));
  };

  const limpiarErrorSesion = () => {
    setErrorSesion(null);
  };

  // Cálculo de minutos restantes para el banner de aviso previo (< 120s)
  const mostrarAvisoInactividad =
    usuario !== null &&
    segundosRestantesInactividad !== null &&
    segundosRestantesInactividad < 120 &&
    segundosRestantesInactividad > 0;

  const minutosRestantesAviso =
    segundosRestantesInactividad !== null
      ? Math.max(1, Math.ceil(segundosRestantesInactividad / 60))
      : 1;

  return (
    <AuthContext.Provider
      value={{
        usuario,
        cargando,
        errorSesion,
        configSesion,
        segundosRestantesInactividad,
        login,
        logout,
        marcarPasswordCambiado,
        limpiarErrorSesion,
        seguirConectado,
      }}
    >
      {/* Banner de aviso previo de expiración por inactividad (T5 punto 7) */}
      {mostrarAvisoInactividad && (
        <aside
          role="alert"
          aria-live="assertive"
          className="lis-session-warning-banner"
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            zIndex: 9999,
            backgroundColor: "#FEF3C7",
            color: "#92400E",
            borderBottom: "1px solid #F59E0B",
            padding: "8px 16px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            fontSize: "14px",
            fontWeight: 500,
            boxShadow: "0 2px 4px rgba(0,0,0,0.08)",
          }}
        >
          <span>
            Tu sesión expirará por inactividad en {minutosRestantesAviso} min ({segundosRestantesInactividad} s).
          </span>
          <button
            type="button"
            onClick={seguirConectado}
            className="lis-btn lis-btn-sm"
            style={{
              backgroundColor: "#B45309",
              color: "#FFFFFF",
              border: "none",
              padding: "4px 12px",
              borderRadius: "4px",
              cursor: "pointer",
              fontWeight: 600,
            }}
          >
            Seguir conectado
          </button>
        </aside>
      )}

      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth debe ser utilizado dentro de un AuthProvider");
  }
  return context;
};
