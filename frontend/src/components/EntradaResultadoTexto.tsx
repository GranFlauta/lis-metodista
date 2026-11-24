import React from "react";

type Props = Omit<React.TextareaHTMLAttributes<HTMLTextAreaElement>, "value" | "onChange"> & {
  value: string;
  onValueChange: (valor: string) => void;
};

function ajustarAltura(campo: HTMLTextAreaElement | null) {
  if (!campo) return;
  campo.style.height = "auto";
  campo.style.height = `${campo.scrollHeight}px`;
}

/** Texto clínico libre: mismo control para listas y resultados por muestra. */
export function EntradaResultadoTexto({ value, onValueChange, className = "", ...props }: Props) {
  return <textarea {...props} className={`lis-captura-input lis-texto-libre ${className}`} rows={1}
    ref={ajustarAltura} value={value} onChange={(evento) => onValueChange(evento.currentTarget.value)}
    onInput={(evento) => ajustarAltura(evento.currentTarget)} />;
}
