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
  // Si no es un número válido o tiene caracteres alfabéticos/fracciones (ej: "1/16"), retornar tal cual
  if (!/^[-+]?\d+(\.\d+)?$/.test(valorEstandar)) {
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

/** Formatea una entrada canónica sin perder decimales, ceros ni el separador final. */
export function formatearEntradaNumerica(valor: string, separadorDecimal = ","): string {
  if (!/^-?\d*(?:\.\d*)?$/.test(valor)) return valor;
  const [entero, fraccion] = valor.split(".");
  const miles = separadorDecimal === "," ? "." : ",";
  const agrupado = entero.replace(/\B(?=(\d{3})+(?!\d))/g, miles);
  return agrupado + (fraccion !== undefined ? separadorDecimal + fraccion : "");
}

function normalizarTextoPegado(texto: string): string {
  const limpio = texto.replace(/[\s\u00a0]/g, "");
  if (limpio.includes(".") && limpio.includes(",")) {
    const decimal = limpio.lastIndexOf(".") > limpio.lastIndexOf(",") ? "." : ",";
    const miles = decimal === "." ? "," : ".";
    return limpio.split(miles).join("").replace(decimal, ".");
  }
  // Un único punto/coma siempre es decimal: 2.200 conserva el valor 2,200.
  // Varios grupos de tres dígitos sí identifican agrupación de miles.
  if (/^-?\d{1,3}([.,])\d{3}(?:\1\d{3})+$/.test(limpio)) {
    return limpio.replace(/[.,]/g, "");
  }
  return limpio.replace(",", ".");
}

export interface EdicionNumerica {
  valor: string;
  posicion: number;
}

/** Distingue el separador que se acaba de teclear de los miles ya dibujados. */
export function procesarEdicionNumerica(
  anterior: string,
  textoNuevo: string,
  separadorDecimal = ",",
  tipoEntrada = "insertText",
  posicionCursor?: number | null,
): EdicionNumerica | null {
  const mostrado = formatearEntradaNumerica(anterior, separadorDecimal);
  let finAnterior = mostrado.length;
  let finNuevo = textoNuevo.length;
  if (posicionCursor !== null && posicionCursor !== undefined) {
    const finPrevio = mostrado.length - textoNuevo.length + posicionCursor;
    if (finPrevio >= 0 && finPrevio <= mostrado.length
      && mostrado.slice(finPrevio) === textoNuevo.slice(posicionCursor)) {
      finAnterior = finPrevio;
      finNuevo = posicionCursor;
    }
  }
  let inicio = 0;
  while (inicio < finAnterior && inicio < finNuevo && mostrado[inicio] === textoNuevo[inicio]) inicio++;
  while (finAnterior > inicio && finNuevo > inicio && mostrado[finAnterior - 1] === textoNuevo[finNuevo - 1]) {
    finAnterior--;
    finNuevo--;
  }
  const miles = separadorDecimal === "," ? "." : ",";
  const indiceCanonico = (indice: number) => mostrado.slice(0, indice).split(miles).join("").length;
  let desde = indiceCanonico(inicio);
  let hasta = indiceCanonico(finAnterior);
  const insertado = textoNuevo.slice(inicio, finNuevo);
  const insercion = tipoEntrada === "insertFromPaste" || insertado.length > 1
    ? normalizarTextoPegado(insertado)
    : insertado.replace(/[.,]/g, ".");
  if (!insertado && inicio < finAnterior && desde === hasta) {
    if (tipoEntrada === "deleteContentBackward") desde = Math.max(0, desde - 1);
    if (tipoEntrada === "deleteContentForward") hasta = Math.min(anterior.length, hasta + 1);
  }
  const valor = anterior.slice(0, desde) + insercion + anterior.slice(hasta);
  if (!/^-?\d*(?:\.\d*)?$/.test(valor)) return null;
  return { valor, posicion: desde + insercion.length };
}

export function posicionEntradaNumerica(valor: string, posicion: number, separadorDecimal = ","): number {
  if (posicion === 0) return 0;
  const mostrado = formatearEntradaNumerica(valor, separadorDecimal);
  const miles = separadorDecimal === "," ? "." : ",";
  let contados = 0;
  for (let indice = 0; indice < mostrado.length; indice++) {
    if (mostrado[indice] !== miles) contados++;
    if (contados === posicion) return indice + 1;
  }
  return mostrado.length;
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

