/**
 * Cliente de API para captura de resultados, cálculo en vivo y configuración.
 * - GET /api/ordenes/{id}/captura
 * - POST /api/ordenes/{id}/calcular
 * - PUT /api/ordenes/{id}/resultados
 * - POST /api/ordenes/{id}/resultados/confirmar-defectos
 * - GET /api/configuracion/laboratorio
 *
 * Utiliza estrictamente apiClient en memoria sin storage.
 */

import { apiClient } from "./client";

export interface CapturaOrdenInfo {
  id: number;
  estado_trabajo: "INCOMPLETO" | "COMPLETO" | "PUBLICADA";
  bloqueada: boolean;
  paciente: {
    id: number;
    sexo: string;
  };
  edad_anios: number | null;
  edad_meses: number | null;
  observaciones?: string | null;
}

export interface RangoReferenciaInfo {
  texto: string | null;
  inferior: string | null;
  superior: string | null;
  modificada?: boolean;
}

export interface RangoOverrideItem {
  limite_inferior?: number | string | null;
  limite_superior?: number | string | null;
  texto?: string | null;
  reestablecer?: boolean;
}

export interface ParametroCaptura {
  codigo: string;
  nombre: string;
  tipo_campo: "NUMERICO" | "SELECCION" | "TEXTO" | "RECUENTO" | "FECHA" | "CALCULADO";
  unidad: string | null;
  decimales: number | null;
  opciones: string[] | null;
  obligatorio: boolean;
  requiere_confirmacion: boolean;
  metodo: string | null;
  muestra: string | null;
  valor: string | null;
  es_calculado: boolean;
  calculable: boolean;
  motivo_no_calculable: string | null;
  confirmado: boolean;
  es_defecto: boolean;
  valor_defecto: string | null;
  referencia: RangoReferenciaInfo | null;
  bandera: "BAJO" | "NORMAL" | "ALTO" | null;
}

export interface SeccionCaptura {
  grupo: string | null;
  parametros: ParametroCaptura[];
}

export interface ValidacionEstudio {
  severidad: "ERROR" | "ADVERTENCIA";
  mensaje: string;
  parametros: string[];
}

export interface EstudioCaptura {
  id_orden_estudio?: number;
  id_estudio?: number;
  codigo: string;
  nombre: string;
  observaciones?: string | null;
  grupos_seleccionados: string[] | null;
  secciones: SeccionCaptura[];
  validaciones: ValidacionEstudio[];
}

export interface CompletitudCaptura {
  completo: boolean;
  pendientes: string[];
  sin_confirmar: string[];
  errores: string[];
}

export interface CapturaOrdenResponse {
  orden: CapturaOrdenInfo;
  estudios: EstudioCaptura[];
  completitud: CompletitudCaptura;
}

export interface ConfiguracionLaboratorio {
  nombre_laboratorio: string;
  separador_decimal: string;
}

/**
 * Obtener captura completa con valores persistidos y virtuales.
 * BIOQUIMICO ajeno -> 404. ADMIN -> 200 y audita ADMIN_VE_PRIVADO.
 */
export async function getCapturaOrdenApi(id: number): Promise<CapturaOrdenResponse> {
  return apiClient<CapturaOrdenResponse>(`/api/ordenes/${id}/captura`);
}

/**
 * Vista previa síncrona sin persistencia en BD.
 * Envía todos los valores actuales del formulario y overrides simulados.
 */
export async function calcularResultadosApi(
  id: number,
  valores: Record<string, string | null>,
  rangos_override?: Record<string, RangoOverrideItem>
): Promise<CapturaOrdenResponse> {
  return apiClient<CapturaOrdenResponse>(`/api/ordenes/${id}/calcular`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ valores, rangos_override }),
  });
}

/**
 * Persistencia parcial de cambios y recálculo integral de calculados.
 * Clave ausente = sin cambio; null = borrar fila.
 */
export async function guardarResultadosApi(
  id: number,
  valores: Record<string, string | null>,
  rangos_override?: Record<string, RangoOverrideItem>,
  observaciones_estudios?: Record<string, string | null>,
  observaciones_orden?: string | null
): Promise<CapturaOrdenResponse> {
  return apiClient<CapturaOrdenResponse>(`/api/ordenes/${id}/resultados`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      valores,
      rangos_override,
      observaciones_estudios,
      observaciones_orden,
    }),
  });
}

/**
 * Persistir valores por defecto virtuales con confirmado = TRUE.
 */
export async function confirmarDefectosApi(
  id: number,
  parametros?: string[]
): Promise<CapturaOrdenResponse> {
  const body = parametros && parametros.length > 0 ? { parametros } : {};
  return apiClient<CapturaOrdenResponse>(`/api/ordenes/${id}/resultados/confirmar-defectos`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

/**
 * Obtener configuración del laboratorio (nombre y separador decimal).
 */
export async function getConfiguracionLaboratorioApi(): Promise<ConfiguracionLaboratorio> {
  return apiClient<ConfiguracionLaboratorio>(`/api/configuracion/laboratorio`);
}
