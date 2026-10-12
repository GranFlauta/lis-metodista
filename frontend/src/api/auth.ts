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

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  debe_cambiar_password: boolean;
  usuario: UsuarioResumen;
}

export interface LoginPayload {
  usuario: string;
  password: string;
}

export interface CambiarPasswordPayload {
  password_actual: string;
  password_nueva: string;
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

export async function heartbeatApi(): Promise<void> {
  await apiClient<void>("/api/auth/heartbeat", {
    method: "POST",
    retryOnSessionExpired: false,
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
