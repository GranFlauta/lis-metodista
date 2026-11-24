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
  tipo_campo: "NUMERICO" | "SELECCION" | "TEXTO" | "TEXTO_LIBRE" | "RECUENTO" | "FECHA" | "CALCULADO";
  texto_sin_limite?: boolean;
  captura_muestras?: { muestras_iniciales: number; sugerencia: string } | null;
  muestras_seriadas?: { muestras: MuestraSeriada[]; resultado_anterior: string | null; pendientes: number[] } | null;
  unidad: string | null;
  unidad_editable?: boolean;
  unidad_modificada?: boolean;
  decimales: number | null;
  opciones: string[] | null;
  obligatorio: boolean;
  requiere_confirmacion: boolean;
  metodo: string | null;
  muestra: string | null;
  valor: string | null;
  valor_informe?: string;
  es_calculado: boolean;
  calculable: boolean;
  motivo_no_calculable: string | null;
  codigo_motivo_no_calculable?: string | null;
  confirmado: boolean;
  es_defecto: boolean;
  valor_defecto: string | null;
  referencia: RangoReferenciaInfo | null;
  bandera: "BAJO" | "NORMAL" | "ALTO" | null;
  captura_serologia?: ConfigCapturaSerologia | null;
  serologia?: PresentacionSerologia | null;
}

export interface EntradaSerologia {
  reactividad: "" | "Negativo" | "Positivo";
  dilucion: string;
  reactivo: string;
  sensibilidad: string;
  unidad: string;
}

export interface ConfigCapturaSerologia {
  modo: "CALCULO" | "TITULO";
  diluciones: string[];
  reactivos?: { nombre: string; sensibilidad: string; unidad: string }[];
  personalizable?: boolean;
  unidades?: string[];
  sin_dilucion?: boolean;
}

export interface PresentacionSerologia {
  entrada: EntradaSerologia;
  resultado: string | null;
  unidad: string;
  referencia: string;
  completo: boolean;
  motivo: string | null;
}

export interface SeccionCaptura {
  grupo: string | null;
  formato?: "LISTA_TEXTO" | "MUESTRAS_SERIADAS" | "SELECCION_SIMPLE" | null;
  parametros: ParametroCaptura[];
  columnas?: { unidad: boolean; referencia: boolean; bandera: boolean; muestra?: boolean; metodo?: boolean } | null;
}

export interface MuestraSeriada {
  numero: number;
  fecha: string | null;
  hora?: string | null;
  turno?: string | null;
  resultado: string | null;
}

export interface ValidacionEstudio {
  severidad: "ERROR" | "ADVERTENCIA";
  mensaje: string;
  parametros: string[];
}

export interface CurvaToleranciaFila {
  id: string;
  etiqueta: string;
  hora: string;
  glucosa: string;
  fecha: string;
}

export interface CurvaToleranciaCaptura {
  configuracion: {
    titulo: string;
    unidad: string;
    filas: CurvaToleranciaFila[];
  };
  fecha_estudio: string | null;
  filas: Array<CurvaToleranciaFila & {
    hora_valor: string | null;
    glucosa_valor: string | null;
    fecha_valor: string | null;
    fecha_explicita: boolean;
    instante: string | null;
    minutos_desde_basal: string | null;
    utilizada: boolean;
    error: string | null;
  }>;
}

export interface EstudioCaptura {
  id_orden_estudio?: number;
  id_estudio?: number;
  codigo: string;
  nombre: string;
  observaciones?: string | null;
  etiqueta_cayados?: string | null;
  grupos_seleccionados: string[] | null;
  secciones: SeccionCaptura[];
  validaciones: ValidacionEstudio[];
  sumas?: { parametros: string[]; valor: string | null; esperado: string; tolerancia: string; valida: boolean }[];
  curva_tolerancia?: CurvaToleranciaCaptura | null;
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
  rangos_override?: Record<string, RangoOverrideItem>,
  unidades_override?: Record<string, string | null>
): Promise<CapturaOrdenResponse> {
  return apiClient<CapturaOrdenResponse>(`/api/ordenes/${id}/calcular`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ valores, rangos_override, unidades_override }),
  });
}

export interface PaginaVistaPrevia {
  numero: number;
  ancho: number;
  alto: number;
  imagen: string;
}

export interface VistaPreviaInforme {
  formato: "Carta";
  paginas: PaginaVistaPrevia[];
}

export interface VistaPreviaPayload {
  valores: Record<string, string | null>;
  rangos_override?: Record<string, RangoOverrideItem>;
  observaciones_estudios?: Record<string, string | null>;
  observaciones_orden?: string | null;
  etiqueta_cayados?: string;
  unidades_override?: Record<string, string | null>;
}

export async function generarVistaPreviaApi(
  idOrden: number,
  payload: VistaPreviaPayload,
  signal?: AbortSignal,
): Promise<VistaPreviaInforme> {
  return apiClient<VistaPreviaInforme>(`/api/ordenes/${idOrden}/vista-previa`, {
    method: "POST",
    body: JSON.stringify(payload),
    signal,
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
  observaciones_orden?: string | null,
  etiquetas_estudios?: Record<string, string | null>,
  unidades_override?: Record<string, string | null>
): Promise<CapturaOrdenResponse> {
  return apiClient<CapturaOrdenResponse>(`/api/ordenes/${id}/resultados`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      valores,
      rangos_override,
      observaciones_estudios,
      observaciones_orden,
      etiquetas_estudios,
      unidades_override,
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
