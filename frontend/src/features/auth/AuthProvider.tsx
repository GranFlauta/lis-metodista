/**
 * Contexto y Proveedor de Autenticación para el sistema LIS.
 * Implementa estrictamente PROMPT_FASE_1.md §9:
 * - Token en memoria (sin storage).
 * - F5 restaura la sesión llamando a POST /api/auth/refresh.
 * - Latido cada 30 segundos; ante 401 SESION_EXPIRADA expira la sesión con mensaje descriptivo.
 * - Sin eventos de descarga (beforeunload/pagehide).
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
  login: (payload: LoginPayload) => Promise<TokenResponse>;
  logout: () => Promise<void>;
  marcarPasswordCambiado: () => void;
  limpiarErrorSesion: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [usuario, setUsuario] = useState<UsuarioAutenticado | null>(null);
  const [cargando, setCargando] = useState<boolean>(true);
  const [errorSesion, setErrorSesion] = useState<string | null>(null);

  const heartbeatIntervalRef = useRef<number | null>(null);

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
    if (mensajeExpiracion) {
      setErrorSesion(mensajeExpiracion);
    }
  }, [detenerLatido]);

  // Iniciar latido cada 30 segundos mientras haya sesión activa
  const iniciarLatido = useCallback(() => {
    detenerLatido();
    heartbeatIntervalRef.current = window.setInterval(async () => {
      try {
        await heartbeatApi();
      } catch (err: unknown) {
        if (err instanceof ApiError && err.codigo === "SESION_EXPIRADA") {
          cerrarSesionLocal("Tu sesión expiró por inactividad o cierre de la aplicación.");
        }
      }
    }, 30000);
  }, [detenerLatido, cerrarSesionLocal]);

  // 1. Al cargar la app: restaurar sesión con /api/auth/refresh (soporte para F5 sin storage)
  useEffect(() => {
    let montado = true;

    async function inicializarSesion() {
      try {
        const tokenResp = await refreshApi();
        if (!montado) return;

        // Cargar ficha completa del usuario autenticado
        try {
          const perfil = await getMeApi();
          if (montado) {
            setUsuario(perfil);
            iniciarLatido();
          }
        } catch {
          if (montado) {
            setUsuario({
              ...tokenResp.usuario,
              debe_cambiar_password: tokenResp.debe_cambiar_password,
            });
            iniciarLatido();
          }
        }
      } catch {
        // No hay cookie de refresh válida o sesión expirada -> login normal
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
  }, [iniciarLatido, detenerLatido, cerrarSesionLocal]);

  // Suscribir callbacks del interceptor del cliente HTTP
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
    const usuarioAuth: UsuarioAutenticado = {
      ...resp.usuario,
      debe_cambiar_password: resp.debe_cambiar_password,
    };
    setUsuario(usuarioAuth);
    iniciarLatido();
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

  return (
    <AuthContext.Provider
      value={{
        usuario,
        cargando,
        errorSesion,
        login,
        logout,
        marcarPasswordCambiado,
        limpiarErrorSesion,
      }}
    >
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
