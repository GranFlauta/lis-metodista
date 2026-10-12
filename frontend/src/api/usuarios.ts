/**
 * Funciones de API para administración de usuarios (solo ADMIN).
 * PROMPT_FASE_1.md §6.3.
 */

import { apiClient } from "./client";

export interface UsuarioDetalle {
  id: number;
  id_usuario?: number;
  usuario: string;
  ci: string;
  nombres: string;
  apellido_paterno: string;
  apellido_materno: string | null;
  nombre_completo: string;
  correo: string | null;
  matricula_profesional: string | null;
  rol: "ADMIN" | "BIOQUIMICO";
  debe_cambiar_password: boolean;
  activo: boolean;
  ultimo_login: string | null;
  creado_en: string;
}

export interface UsuarioCreatePayload {
  usuario: string;
  ci: string;
  nombres: string;
  apellido_paterno: string;
  apellido_materno?: string | null;
  correo?: string | null;
  matricula_profesional?: string | null;
  rol: "ADMIN" | "BIOQUIMICO";
}

export interface UsuarioUpdatePayload {
  nombres?: string;
  apellido_paterno?: string;
  apellido_materno?: string | null;
  correo?: string | null;
  matricula_profesional?: string | null;
  rol?: "ADMIN" | "BIOQUIMICO";
  ci?: string;
}

export interface UsuarioCreadoResponse extends UsuarioDetalle {
  password_temporal: string;
}

export interface ResetPasswordResponse {
  password_temporal: string;
}

export interface ListarUsuariosParams {
  activo?: boolean;
  rol?: string;
  q?: string;
}

export async function listarUsuariosApi(params: ListarUsuariosParams = {}): Promise<UsuarioDetalle[]> {
  const query = new URLSearchParams();
  if (params.activo !== undefined) {
    query.set("activo", String(params.activo));
  }
  if (params.rol) {
    query.set("rol", params.rol);
  }
  if (params.q) {
    query.set("q", params.q);
  }

  const endpoint = `/api/usuarios${query.toString() ? `?${query.toString()}` : ""}`;
  return apiClient<UsuarioDetalle[]>(endpoint, { method: "GET" });
}

export async function crearUsuarioApi(payload: UsuarioCreatePayload): Promise<UsuarioCreadoResponse> {
  return apiClient<UsuarioCreadoResponse>("/api/usuarios", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function obtenerUsuarioApi(id: number): Promise<UsuarioDetalle> {
  return apiClient<UsuarioDetalle>(`/api/usuarios/${id}`, {
    method: "GET",
  });
}

export async function editarUsuarioApi(id: number, payload: UsuarioUpdatePayload): Promise<UsuarioDetalle> {
  return apiClient<UsuarioDetalle>(`/api/usuarios/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function desactivarUsuarioApi(id: number): Promise<void> {
  await apiClient<void>(`/api/usuarios/${id}/desactivar`, {
    method: "POST",
  });
}

export async function reactivarUsuarioApi(id: number): Promise<void> {
  await apiClient<void>(`/api/usuarios/${id}/reactivar`, {
    method: "POST",
  });
}

export async function resetPasswordUsuarioApi(id: number): Promise<ResetPasswordResponse> {
  return apiClient<ResetPasswordResponse>(`/api/usuarios/${id}/reset-password`, {
    method: "POST",
  });
}
