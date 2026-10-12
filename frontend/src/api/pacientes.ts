/**
 * Funciones de API para la gestión de Pacientes.
 * PROMPT_FASE_2.md §8.2.
 */

import { apiClient } from "./client";

export interface PacienteDetalle {
  id: number;
  ci: string | null;
  ci_complemento: string | null;
  sin_ci: boolean;
  nombres: string;
  apellido_paterno: string;
  apellido_materno: string | null;
  fecha_nacimiento: string | null;
  sexo: "M" | "F" | string;
  telefono: string | null;
  creado_en: string;
}

export interface PacienteListaResponse {
  items: PacienteDetalle[];
  total: number;
  limit: number;
  offset: number;
}

export interface PacienteCreatePayload {
  ci?: string | null;
  ci_complemento?: string | null;
  sin_ci: boolean;
  nombres: string;
  apellido_paterno: string;
  apellido_materno?: string | null;
  fecha_nacimiento?: string | null;
  sexo: string;
  telefono?: string | null;
}

export interface PacienteUpdatePayload {
  ci?: string | null;
  ci_complemento?: string | null;
  sin_ci?: boolean;
  nombres?: string;
  apellido_paterno?: string;
  apellido_materno?: string | null;
  fecha_nacimiento?: string | null;
  sexo?: string;
  telefono?: string | null;
}

export interface ListarPacientesParams {
  q?: string;
  limit?: number;
  offset?: number;
}

export async function listarPacientesApi(params: ListarPacientesParams = {}): Promise<PacienteListaResponse> {
  const query = new URLSearchParams();
  if (params.q && params.q.trim()) {
    query.set("q", params.q.trim());
  }
  if (params.limit !== undefined) {
    query.set("limit", String(params.limit));
  }
  if (params.offset !== undefined) {
    query.set("offset", String(params.offset));
  }

  const endpoint = `/api/pacientes${query.toString() ? `?${query.toString()}` : ""}`;
  return apiClient<PacienteListaResponse>(endpoint, { method: "GET" });
}

export async function obtenerPacienteApi(id: number): Promise<PacienteDetalle> {
  return apiClient<PacienteDetalle>(`/api/pacientes/${id}`, { method: "GET" });
}

export async function crearPacienteApi(payload: PacienteCreatePayload): Promise<PacienteDetalle> {
  return apiClient<PacienteDetalle>("/api/pacientes", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function editarPacienteApi(id: number, payload: PacienteUpdatePayload): Promise<PacienteDetalle> {
  return apiClient<PacienteDetalle>(`/api/pacientes/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}
