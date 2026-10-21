/**
 * Almacén en memoria volátil de estudios agregados dinámicamente a una orden en sesión activa (SPA).
 * Cumple estrictamente docs/UX_GUIDE.md §7 (sin localStorage ni sessionStorage).
 */
import { EstudioCatalogo } from "../api/catalogo";

const estudiosAgregadosPorOrden = new Map<number, EstudioCatalogo[]>();

export function obtenerEstudiosAgregados(ordenId: number): EstudioCatalogo[] {
  return estudiosAgregadosPorOrden.get(ordenId) || [];
}

export function agregarEstudioAOrdenMemoria(ordenId: number, estudio: EstudioCatalogo): void {
  const existentes = estudiosAgregadosPorOrden.get(ordenId) || [];
  if (!existentes.some((e) => e.codigo === estudio.codigo)) {
    estudiosAgregadosPorOrden.set(ordenId, [...existentes, estudio]);
  }
}
