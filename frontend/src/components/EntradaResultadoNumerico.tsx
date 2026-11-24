import React, { useLayoutEffect, useRef } from "react";
import {
  EdicionNumerica,
  formatearEntradaNumerica,
  posicionEntradaNumerica,
  procesarEdicionNumerica,
} from "../utils/formatoNumerico";

interface Props extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "value" | "onChange" | "type" | "inputMode"> {
  value: string;
  separadorDecimal: string;
  onValueChange: (valor: string) => void;
}

/** El formulario guarda texto canónico; la agrupación pertenece solo al input. */
export function EntradaResultadoNumerico({ value, separadorDecimal, onValueChange, ...props }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const seleccionRef = useRef<EdicionNumerica | null>(null);

  useLayoutEffect(() => {
    const seleccion = seleccionRef.current;
    if (!seleccion || seleccion.valor !== value || !inputRef.current) return;
    const posicion = posicionEntradaNumerica(value, seleccion.posicion, separadorDecimal);
    inputRef.current.setSelectionRange(posicion, posicion);
    seleccionRef.current = null;
  });

  return <input
    {...props}
    ref={inputRef}
    type="text"
    inputMode="decimal"
    value={formatearEntradaNumerica(value, separadorDecimal)}
    onChange={(event) => {
      const input = event.currentTarget;
      const tipo = (event.nativeEvent as InputEvent).inputType || "insertText";
      const edicion = procesarEdicionNumerica(value, input.value, separadorDecimal, tipo, input.selectionStart);
      if (!edicion) {
        input.value = formatearEntradaNumerica(value, separadorDecimal);
        return;
      }
      seleccionRef.current = edicion;
      onValueChange(edicion.valor);
    }}
  />;
}
