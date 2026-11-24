import { apiClient } from "./client";

export type FiltroRespuesta = "todas" | "hasta_60" | "de_60_a_240" | "mas_240" | "sin_hora";
export interface FiltrosEstadistica { desde: string; hasta: string; id_autor: string; respuesta: FiltroRespuesta }
export interface SerieEstadistica { codigo: string; nombre: string; cantidad: number }
export interface ActividadDiaria { fecha: string; iniciadas: number; publicadas: number }
export interface Estadistica {
  desde: string;
  hasta: string;
  generado_en: string;
  alcance: "laboratorio" | "propio";
  id_autor: number | null;
  respuesta: FiltroRespuesta;
  profesionales: { id: number; nombre: string; activo: boolean }[];
  resumen: {
    ordenes: number; publicadas: number; pendientes: number; estudios_informados: number;
    respuesta_mediana_minutos: string | null; respuestas_validas: number; publicadas_sin_hora: number;
  };
  estados: SerieEstadistica[];
  estudios: SerieEstadistica[];
  responsables: SerieEstadistica[];
  tiempos_respuesta: SerieEstadistica[];
  actividad: ActividadDiaria[];
}

export function obtenerEstadisticasApi(filtros: FiltrosEstadistica, signal?: AbortSignal): Promise<Estadistica> {
  const query = new URLSearchParams({ desde: filtros.desde, hasta: filtros.hasta, respuesta: filtros.respuesta });
  if (filtros.id_autor) query.set("id_autor", filtros.id_autor);
  return apiClient<Estadistica>(`/api/estadisticas?${query}`, { signal });
}
