/**
 * Utilidades para el formateo numérico clínico.
 * Garantiza la regla canónica de separador de miles y decimales:
 * - Si separador_decimal es ',': miles con '.' y decimales con ',' (ej: 1092324 -> 1.092.324, 14.5 -> 14,5).
 * - Si separador_decimal es '.': miles con ',' y decimales con '.' (ej: 1092324 -> 1,092,324, 14.5 -> 14.5).
 */

/**
 * Formatea un valor numérico o cadena clínica aplicando la agrupación de miles y decimales configurada.
 * Si el valor no es un número puro (ej: "Negativo", "No reactivo", "1/16"), lo devuelve sin alterar.
 */
export function formatearResultadoClinico(
  valor: string | number | null | undefined,
  separadorDecimal: string = ",",
  decimalesMax?: number
): string {
  if (valor === null || valor === undefined || valor === "") {
    return "—";
  }

  const strValor = String(valor).trim();
  if (strValor === "" || strValor === "—") {
    return "—";
  }

  // Normalizar coma a punto para verificar si es numérico
  const valorEstandar = strValor.replace(",", ".");
  const num = Number(valorEstandar);

  // Si no es un número válido o tiene caracteres alfabéticos/fracciones (ej: "1/16"), retornar tal cual
  if (isNaN(num) || !/^[-+]?\d+(\.\d+)?$/.test(valorEstandar)) {
    return strValor;
  }

  const separadorMiles = separadorDecimal === "," ? "." : ",";

  // Dividir parte entera y decimal
  const partes = valorEstandar.split(".");
  let parteEntera = partes[0];
  let parteDecimal = partes[1] !== undefined ? partes[1] : null;

  // Si se solicita limitar decimales
  if (decimalesMax !== undefined && parteDecimal !== null) {
    if (decimalesMax === 0) {
      parteDecimal = null;
    } else if (parteDecimal.length > decimalesMax) {
      parteDecimal = parteDecimal.slice(0, decimalesMax);
    }
  }

  // Agrupar miles en la parte entera (con signo)
  const esNegativo = parteEntera.startsWith("-");
  const enterosSinSigno = esNegativo ? parteEntera.slice(1) : parteEntera;
  const enterosConMiles = enterosSinSigno.replace(/\B(?=(\d{3})+(?!\d))/g, separadorMiles);
  const resultadoEntero = (esNegativo ? "-" : "") + enterosConMiles;

  if (parteDecimal !== null && parteDecimal !== "") {
    return `${resultadoEntero}${separadorDecimal}${parteDecimal}`;
  }

  return resultadoEntero;
}

/**
 * Formatea en tiempo real mientras el usuario escribe números enteros grandes (ej: Plaquetas 123456 -> 123.456).
 * Elimina caracteres no numéricos y agrupa con punto de miles.
 */
export function formatearMilesEntero(valor: string | number | null | undefined): string {
  if (valor === null || valor === undefined || valor === "") return "";
  const str = String(valor);
  const digitos = str.replace(/\D/g, "");
  if (!digitos) return "";
  return digitos.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

