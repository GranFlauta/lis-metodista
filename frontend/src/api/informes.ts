/**
 * API client para Informes Oficiales, Publicación, Versiones y Papelera Lógica.
 */
import { apiClient } from './client';

export interface InformeItem {
  id_informe: number;
  folio: string;
  numero_version: number;
  id_orden: number;
  estado: 'VIGENTE' | 'DESPLAZADO' | 'PAPELERA' | 'RECICLAJE';
  es_urgencia: boolean;
  justificativo?: string | null;
  publicado_en: string;
  paciente_nombre: string;
  paciente_ci?: string | null;
  firmante_nombre: string;
  publicador_nombre: string;
  snapshot_sha256: string;
}

export interface InformeEvento {
  id_evento: number;
  folio: string;
  numero_version?: number | null;
  accion: 'PUBLICACION' | 'URGENCIA' | 'EDICION_V2' | 'EDICION_V3' | 'PAPELERA' | 'RESTAURACION' | 'IMPRESION';
  justificativo?: string | null;
  detalle?: Record<string, unknown> | null;
  id_usuario: number;
  usuario_nombre: string;
  creado_en: string;
}

export interface InformeDetalle {
  id_informe: number;
  folio: string;
  numero_version: number;
  id_orden: number;
  estado: 'VIGENTE' | 'DESPLAZADO' | 'PAPELERA' | 'RECICLAJE';
  es_urgencia: boolean;
  justificativo?: string | null;
  publicado_en: string;
  snapshot_json: Record<string, any>;
  snapshot_sha256: string;
  firmante: {
    id_usuario: number;
    usuario: string;
    nombres: string;
    apellido_paterno: string;
    matricula_profesional?: string | null;
  };
  publicador: {
    id_usuario: number;
    usuario: string;
    nombres: string;
    apellido_paterno: string;
  };
  eventos: InformeEvento[];
  versiones_disponibles: Array<{
    id_informe: number;
    numero_version: number;
    estado: string;
    publicado_en: string;
    snapshot_sha256: string;
  }>;
}

export interface PapeleraItem {
  id_informe: number;
  folio: string;
  numero_version: number;
  id_orden: number;
  estado: 'PAPELERA' | 'RECICLAJE';
  paciente_nombre: string;
  paciente_ci?: string | null;
  firmante_nombre: string;
  motivo_papelera?: string | null;
  fecha_papelera: string;
}

export interface PublicarResponse {
  mensaje: string;
  folio: string;
  numero_version: number;
  estado: string;
  publicado_en: string;
  snapshot_sha256: string;
  id_informe: number;
}

export async function publicarOrden(idOrden: number, justificativoUrgencia?: string): Promise<PublicarResponse> {
  return apiClient<PublicarResponse>(`/api/ordenes/${idOrden}/publicar`, {
    method: 'POST',
    body: JSON.stringify({ justificativo_urgencia: justificativoUrgencia || null }),
  });
}

export async function getInformes(filtros?: {
  q?: string;
  estado?: string;
  limit?: number;
  offset?: number;
}): Promise<InformeItem[]> {
  const params = new URLSearchParams();
  if (filtros?.q) params.set('q', filtros.q);
  if (filtros?.estado) params.set('estado', filtros.estado);
  if (filtros?.limit) params.set('limit', String(filtros.limit));
  if (filtros?.offset) params.set('offset', String(filtros.offset));
  const query = params.toString() ? `?${params.toString()}` : '';
  return apiClient<InformeItem[]>(`/api/informes${query}`, { method: 'GET' });
}

export async function getPapelera(filtros?: {
  q?: string;
  limit?: number;
  offset?: number;
}): Promise<PapeleraItem[]> {
  const params = new URLSearchParams();
  if (filtros?.q) params.set('q', filtros.q);
  if (filtros?.limit) params.set('limit', String(filtros.limit));
  if (filtros?.offset) params.set('offset', String(filtros.offset));
  const query = params.toString() ? `?${params.toString()}` : '';
  return apiClient<PapeleraItem[]>(`/api/informes/papelera${query}`, { method: 'GET' });
}

export async function getInforme(folio: string, version?: number): Promise<InformeDetalle> {
  const query = version ? `?version=${version}` : '';
  return apiClient<InformeDetalle>(`/api/informes/${folio}${query}`, { method: 'GET' });
}

export async function getHistorialInforme(folio: string): Promise<InformeEvento[]> {
  return apiClient<InformeEvento[]>(`/api/informes/${folio}/historial`, { method: 'GET' });
}

export async function moverAPapelera(folio: string, justificativo: string): Promise<InformeItem> {
  return apiClient<InformeItem>(`/api/informes/${folio}/papelera`, {
    method: 'POST',
    body: JSON.stringify({ justificativo }),
  });
}

export async function restaurarDePapelera(folio: string, justificativo: string): Promise<InformeItem> {
  return apiClient<InformeItem>(`/api/informes/${folio}/restaurar`, {
    method: 'POST',
    body: JSON.stringify({ justificativo }),
  });
}

export async function crearNuevaVersion(folio: string, justificativo: string): Promise<InformeItem> {
  return apiClient<InformeItem>(`/api/informes/${folio}/versiones`, {
    method: 'POST',
    body: JSON.stringify({ justificativo }),
  });
}
