/**
 * Funciones de API para consulta del Catálogo Clínico de Estudios y Perfiles.
 * PROMPT_FASE_2.md §8.1.
 */

import { apiClient } from "./client";

export interface ParametroCatalogo {
  codigo: string;
  nombre: string;
}

export interface GrupoEstudioCatalogo {
  codigo: string;
  parametros: ParametroCatalogo[];
}

export interface EstudioCatalogo {
  codigo: string;
  nombre: string;
  categoria: string;
  seleccion_parcial: boolean;
  grupos?: GrupoEstudioCatalogo[] | null;
}

export interface PerfilEstudioItem {
  codigo: string;
  grupos?: string[] | null;
}

export interface PerfilCatalogo {
  codigo: string;
  nombre: string;
  estudios: PerfilEstudioItem[];
}

export interface PerfilRapido extends PerfilCatalogo { id: number }

export async function listarPerfilesRapidosApi(): Promise<PerfilRapido[]> {
  return apiClient<PerfilRapido[]>("/api/catalogo/perfiles-rapidos", { method: "GET" });
}

export async function crearPerfilRapidoApi(payload: { nombre: string; estudios: PerfilEstudioItem[] }): Promise<PerfilRapido> {
  return apiClient<PerfilRapido>("/api/catalogo/perfiles-rapidos", { method: "POST", body: JSON.stringify(payload) });
}

export async function actualizarPerfilRapidoApi(id: number, payload: { nombre: string; estudios: PerfilEstudioItem[] }): Promise<PerfilRapido> {
  return apiClient<PerfilRapido>(`/api/catalogo/perfiles-rapidos/${id}`, { method: "PUT", body: JSON.stringify(payload) });
}

export async function eliminarPerfilRapidoApi(id: number): Promise<void> {
  return apiClient<void>(`/api/catalogo/perfiles-rapidos/${id}`, { method: "DELETE" });
}

export async function obtenerEstudiosCatalogoApi(): Promise<EstudioCatalogo[]> {
  return apiClient<EstudioCatalogo[]>("/api/catalogo/estudios", { method: "GET" });
}

export async function obtenerPerfilesCatalogoApi(): Promise<PerfilCatalogo[]> {
  return apiClient<PerfilCatalogo[]>("/api/catalogo/perfiles", { method: "GET" });
}
