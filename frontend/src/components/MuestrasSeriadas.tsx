import React, { useMemo } from "react";
import type { MuestraSeriada, ParametroCaptura } from "../api/resultados";
import { EntradaResultadoTexto } from "./EntradaResultadoTexto";
import { Icono } from "./Icono";

type Props = {
  parametro: ParametroCaptura;
  valor: string;
  soloLectura: boolean;
  onChange: (codigo: string, valor: string) => void;
  onKeyDown: (evento: React.KeyboardEvent<HTMLElement>) => void;
};

const TURNOS = ["MAÑANA", "TARDE", "NOCHE"] as const;

function vacia(numero: number): MuestraSeriada {
  return { numero, fecha: null, hora: null, turno: null, resultado: null };
}

export function MuestrasSeriadas({ parametro, valor, soloLectura, onChange, onKeyDown }: Props) {
  const config = parametro.captura_muestras!;
  const { muestras, anterior } = useMemo(() => {
    let entradas: MuestraSeriada[] = [];
    let anterior: string | null = null;
    if (valor.trim()) {
      try {
        const datos = JSON.parse(valor);
        if (datos && Array.isArray(datos.muestras)) entradas = datos.muestras;
        else anterior = valor;
      } catch { anterior = valor; }
    }
    const muestras: MuestraSeriada[] = entradas.map((muestra, indice) => ({
      numero: indice + 1,
      fecha: muestra.fecha || null,
      hora: muestra.hora || null,
      turno: muestra.turno || null,
      resultado: muestra.resultado ?? null,
    }));
    while (muestras.length < config.muestras_iniciales) muestras.push(vacia(muestras.length + 1));
    return { muestras, anterior };
  }, [valor, config.muestras_iniciales]);
  const enviar = (nuevas: MuestraSeriada[]) => onChange(parametro.codigo, JSON.stringify({
    muestras: nuevas.map((muestra, indice) => ({ ...muestra, numero: indice + 1 })),
  }));
  const cambiar = (indice: number, campo: "fecha" | "hora" | "turno" | "resultado", nuevo: string) => {
    enviar(muestras.map((muestra, posicion) => posicion === indice ? { ...muestra, [campo]: nuevo || null } : muestra));
  };
  const quitar = (indice: number) => enviar(muestras.filter((_, posicion) => posicion !== indice));

  if (anterior !== null) return <div className="lis-samples-legacy">
    <p>Resultado anterior sin fecha: <strong>{anterior}</strong></p>
    {!soloLectura && <button type="button" className="lis-btn lis-btn-secondary lis-btn-sm" onClick={() => enviar(muestras)}>
      Reemplazar por captura de muestras
    </button>}
  </div>;

  return <>
    <table className="lis-captura-tabla lis-muestras-seriadas" aria-label={parametro.nombre}>
      <thead><tr>
        <th scope="col">Muestra</th>
        <th scope="col">Fecha</th>
        <th scope="col">Hora</th>
        <th scope="col">Turno</th>
        <th scope="col">Resultado</th>
        <th scope="col"><span className="lis-sr-only">Quitar</span></th>
      </tr></thead>
      <tbody>{muestras.map((muestra, indice) => <tr key={muestra.numero}>
        <th scope="row">{muestra.numero}.ª MUESTRA</th>
        <td className="lis-sheet-entry"><input type="date" className="lis-captura-input"
          aria-label={`Fecha de la ${muestra.numero}.ª muestra`} value={muestra.fecha || ""} disabled={soloLectura}
          onChange={(evento) => cambiar(indice, "fecha", evento.currentTarget.value)} onKeyDown={onKeyDown} /></td>
        <td className="lis-sheet-entry"><input type="time" className="lis-captura-input"
          aria-label={`Hora de la ${muestra.numero}.ª muestra`} value={muestra.hora || ""} disabled={soloLectura} step={60}
          onChange={(evento) => cambiar(indice, "hora", evento.currentTarget.value)} onKeyDown={onKeyDown} /></td>
        <td className="lis-sheet-entry"><select className="lis-captura-input"
          aria-label={`Turno de la ${muestra.numero}.ª muestra`} value={muestra.turno || ""} disabled={soloLectura}
          onChange={(evento) => cambiar(indice, "turno", evento.currentTarget.value)} onKeyDown={onKeyDown}>
          <option value="">—</option>
          {TURNOS.map((turno) => <option key={turno} value={turno}>{turno}</option>)}
        </select></td>
        <td className="lis-sheet-entry"><div className="lis-sample-result">
          <EntradaResultadoTexto aria-label={`Resultado de la ${muestra.numero}.ª muestra`}
            placeholder={config.sugerencia} value={muestra.resultado || ""} disabled={soloLectura}
            onValueChange={(nuevo) => cambiar(indice, "resultado", nuevo)} onKeyDown={onKeyDown} />
          {!soloLectura && !muestra.resultado?.trim() && <button type="button" className="lis-sheet-icon-btn lis-sample-accept"
            aria-label={`Aceptar sugerencia para la ${muestra.numero}.ª muestra`} title={`Usar: ${config.sugerencia}`}
            onClick={() => cambiar(indice, "resultado", config.sugerencia)}><Icono nombre="correcto" size={16} /></button>}
        </div></td>
        <td>{!soloLectura && indice >= config.muestras_iniciales && <button type="button"
          className="lis-sheet-icon-btn" aria-label={`Eliminar la ${muestra.numero}.ª muestra`}
          title="Eliminar esta muestra" onClick={() => quitar(indice)}><Icono nombre="eliminar" size={15} /></button>}</td>
      </tr>)}</tbody>
    </table>
    {!soloLectura && <button type="button" className="lis-btn lis-btn-secondary lis-btn-sm lis-add-sample"
      onClick={() => enviar([...muestras, vacia(muestras.length + 1)])}>
      <Icono nombre="mas" size={15} /> Añadir muestra
    </button>}
  </>;
}
