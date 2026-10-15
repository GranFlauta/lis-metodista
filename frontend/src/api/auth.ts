/**
 * Funciones de API para autenticación y sesiones.
 * PROMPT_FASE_1.md §6.2.
 */

import { apiClient, setAccessToken } from "./client";

export interface UsuarioResumen {
  id: number;
  usuario: string;
  nombres: string;
  apellido_paterno: string;
  apellido_materno: string | null;
  rol: "ADMIN" | "BIOQUIMICO";
}

export interface UsuarioAutenticado extends UsuarioResumen {
  debe_cambiar_password: boolean;
}

export interface ConfigSesionResumen {
  intervalo_latido_seg: number;
  inactividad_min: number;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  debe_cambiar_password: boolean;
  rol?: string;
  usuario: UsuarioResumen;
  config_sesion?: ConfigSesionResumen;
}

export interface LoginPayload {
  usuario: string;
  password: string;
}

export interface CambiarPasswordPayload {
  password_actual: string;
  password_nueva: string;
}

export interface HeartbeatResponse {
  intervalo_latido_seg: number;
  segundos_restantes_inactividad: number;
}

export interface SesionConfig {
  sesion_intervalo_latido_seg: number;
  sesion_muerta_tras_seg: number;
  sesion_inactividad_min: number;
  sesion_tope_absoluto_horas: number;
}

export async function loginApi(payload: LoginPayload): Promise<TokenResponse> {
  const data = await apiClient<TokenResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
    retryOnSessionExpired: false,
  });
  setAccessToken(data.access_token);
  return data;
}

export async function refreshApi(): Promise<TokenResponse> {
  const data = await apiClient<TokenResponse>("/api/auth/refresh", {
    method: "POST",
    retryOnSessionExpired: false,
  });
  setAccessToken(data.access_token);
  return data;
}

export async function heartbeatApi(actividad: boolean = false): Promise<HeartbeatResponse> {
  return apiClient<HeartbeatResponse>("/api/auth/heartbeat", {
    method: "POST",
    body: JSON.stringify({ actividad }),
    retryOnSessionExpired: false,
  });
}

export async function getSesionConfigApi(): Promise<SesionConfig> {
  return apiClient<SesionConfig>("/api/admin/configuracion/sesion", {
    method: "GET",
  });
}

export async function updateSesionConfigApi(payload: SesionConfig): Promise<SesionConfig> {
  return apiClient<SesionConfig>("/api/admin/configuracion/sesion", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function logoutApi(): Promise<void> {
  try {
    await apiClient<void>("/api/auth/logout", {
      method: "POST",
      retryOnSessionExpired: false,
    });
  } finally {
    setAccessToken(null);
  }
}

export async function getMeApi(): Promise<UsuarioAutenticado> {
  return apiClient<UsuarioAutenticado>("/api/auth/me", {
    method: "GET",
  });
}

export async function cambiarPasswordApi(payload: CambiarPasswordPayload): Promise<void> {
  await apiClient<void>("/api/auth/cambiar-password", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
