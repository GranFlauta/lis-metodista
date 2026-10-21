/**
 * Utilidad de capitalización inteligente para formularios clínicos.
 * Implementa MEJORAR DISEÑO PANTALLAS.md §9:
 * - Capitaliza el primer carácter de cada palabra o después de un punto (ej: "Juan Perez", "Dr. Perez").
 * - Permite al usuario editar o borrar si desea escribir intencionalmente en minúsculas.
 */

/**
 * Capitaliza inteligentemente palabras individuales en nombres y títulos de doctores.
 * Si el usuario acaba de escribir un espacio o punto y luego una letra, pone esa letra en mayúscula.
 */
export function capitalizarNombrePropio(valorActual: string, valorPrevio = ""): string {
  if (!valorActual) return "";

  // Si el usuario está borrando texto, no forzar mayúsculas
  if (valorActual.length < valorPrevio.length) {
    return valorActual;
  }

  // Si es el primer carácter escrito, poner en mayúscula
  if (valorActual.length === 1) {
    return valorActual.toUpperCase();
  }

  // Capitalizar tras un espacio, tabulador o punto
  const ultimoChar = valorActual[valorActual.length - 1];
  const penultimoChar = valorActual[valorActual.length - 2];

  if ((penultimoChar === " " || penultimoChar === "." || penultimoChar === "\t") && /[a-zñáéíóú]/i.test(ultimoChar)) {
    return valorActual.slice(0, -1) + ultimoChar.toUpperCase();
  }

  return valorActual;
}

/**
 * Capitaliza párrafos u oraciones largas (como justificaciones):
 * Solo pone mayúscula al inicio del texto o tras un punto y espacio.
 */
export function capitalizarOracion(valorActual: string, valorPrevio = ""): string {
  if (!valorActual) return "";

  if (valorActual.length < valorPrevio.length) {
    return valorActual;
  }

  if (valorActual.length === 1) {
    return valorActual.toUpperCase();
  }

  const longitud = valorActual.length;
  // Tras ". " capitalizar siguiente letra
  if (longitud >= 3) {
    const antepenultimo = valorActual[longitud - 3];
    const penultimo = valorActual[longitud - 2];
    const ultimo = valorActual[longitud - 1];
    if (antepenultimo === "." && penultimo === " " && /[a-zñáéíóú]/i.test(ultimo)) {
      return valorActual.slice(0, -1) + ultimo.toUpperCase();
    }
  }

  return valorActual;
}
