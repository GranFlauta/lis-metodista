/** Reduce el texto de auditoría semicuantitativa a un resultado apto para el informe. */
export function formatoResultadoInmunoserologia(codigo: string, valor: string | null | undefined): string {
  const raw = valor?.trim();
  if (!raw || (codigo !== "FR_DILUCION" && codigo !== "ASTO_DILUCION")) return raw || "";

  const resultado = raw.split(";")[0].trim();
  const noReactivo = resultado.match(/^No reactivo:\s*(.+)$/i);
  if (noReactivo) return `No reactivo · ${noReactivo[1].trim()}`;

  const reactivoSinDilucion = resultado.match(/^Reactivo sin dilución:\s*(.+)$/i);
  if (reactivoSinDilucion) return `Reactivo · ${reactivoSinDilucion[1].trim()}`;

  const reactivoDilucion = resultado.match(/^Reactivo\s+(\S+):\s*(.+)$/i);
  if (reactivoDilucion) return `Reactivo · ${reactivoDilucion[1]} · ${reactivoDilucion[2].trim()}`;

  return resultado;
}
