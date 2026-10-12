/**
 * Funciones de API para Órdenes en borrador.
 * PROMPT_FASE_2.md §8.3:
 * - POST /api/ordenes
 * - GET /api/ordenes
 * - GET /api/ordenes/{id}
 * - PATCH /api/ordenes/{id}
 * - DELETE /api/ordenes/{id}
 */

import { apiClient } from "./client";
import { PacienteCreatePayload } from "./pacientes";

export interface EstudioItemCreate {
  codigo: string;
  grupos?: string[] | null;
}

export interface OrdenCreatePayload {
  id_paciente?: number | null;
  paciente?: PacienteCreatePayload | null;
  perfil?: string | null;
  estudios: EstudioItemCreate[];
  origen_solicitud?: string | null;
  medico_solicitante?: string | null;
  pieza?: string | null;
  edad_anios?: number | null;
  edad_meses?: number | null;
  fecha_hora_toma_muestra?: string | null;
}

export interface AdvertenciaSolapamiento {
  tipo: string;
  autor: {
    id?: number | null;
    nombres: string;
    apellido_paterno: string;
  };
  estudios: string[];
}

export interface OrdenEstudioItem {
  codigo: string;
  nombre: string;
  grupos: string[] | null;
}

export interface OrdenDetalle {
  id: number;
  paciente: {
    id: number;
    ci: string | null;
    ci_complemento: string | null;
    nombres: string;
    apellido_paterno: string;
    apellido_materno: string | null;
    sexo: string;
    fecha_nacimiento: string | null;
  };
  numero_orden_paciente: number;
  autor: {
    id: number | null;
    nombres: string;
    apellido_paterno: string;
  };
  perfil: {
    codigo: string;
    nombre: string;
  } | null;
  origen_solicitud: string | null;
  medico_solicitante: string | null;
  pieza: string | null;
  edad_anios: number | null;
  edad_meses: number | null;
  fecha_solicitud: string;
  fecha_hora_toma_muestra: string | null;
  estado_trabajo: string;
  bloqueada: boolean;
  fila_version: number;
  estudios: OrdenEstudioItem[];
  creado_en: string;
  actualizado_en: string;
}

export interface OrdenCreadaResponse {
  orden: OrdenDetalle;
  advertencias: AdvertenciaSolapamiento[];
}

export interface OrdenListItem {
  id: number;
  paciente: {
    id: number;
    ci: string | null;
    nombres: string;
    apellido_paterno: string;
    apellido_materno: string | null;
  };
  numero_orden_paciente: number;
  estado_trabajo: string;
  bloqueada: boolean;
  estudios: string[];
  fecha_solicitud: string;
  creado_en: string;
}

export interface OrdenListaResponse {
  items: OrdenListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface OrdenUpdatePayload {
  fila_version: number;
  origen_solicitud?: string | null;
  medico_solicitante?: string | null;
  pieza?: string | null;
  edad_anios?: number | null;
  edad_meses?: number | null;
  fecha_hora_toma_muestra?: string | null;
}

export interface ListarOrdenesParams {
  estado?: string;
  id_paciente?: number;
  q?: string;
  id_autor?: number;
  limit?: number;
  offset?: number;
}

export async function crearOrdenApi(payload: OrdenCreatePayload): Promise<OrdenCreadaResponse> {
  return apiClient<OrdenCreadaResponse>("/api/ordenes", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listarOrdenesApi(params: ListarOrdenesParams = {}): Promise<OrdenListaResponse> {
  const query = new URLSearchParams();
  if (params.estado) {
    query.set("estado", params.estado);
  }
  if (params.id_paciente !== undefined) {
    query.set("id_paciente", String(params.id_paciente));
  }
  if (params.q && params.q.trim()) {
    query.set("q", params.q.trim());
  }
  if (params.id_autor !== undefined) {
    query.set("id_autor", String(params.id_autor));
  }
  if (params.limit !== undefined) {
    query.set("limit", String(params.limit));
  }
  if (params.offset !== undefined) {
    query.set("offset", String(params.offset));
  }

  const endpoint = `/api/ordenes${query.toString() ? `?${query.toString()}` : ""}`;
  return apiClient<OrdenListaResponse>(endpoint, { method: "GET" });
}

export async function obtenerOrdenApi(id: number): Promise<OrdenDetalle> {
  return apiClient<OrdenDetalle>(`/api/ordenes/${id}`, { method: "GET" });
}

export async function actualizarOrdenApi(id: number, payload: OrdenUpdatePayload): Promise<OrdenDetalle> {
  return apiClient<OrdenDetalle>(`/api/ordenes/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function descartarOrdenApi(id: number): Promise<void> {
  await apiClient<void>(`/api/ordenes/${id}`, {
    method: "DELETE",
  });
}
