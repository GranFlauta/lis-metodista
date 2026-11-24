import React from "react";
import { SeccionCaptura } from "../../api/resultados";

interface Props {
  seccion: SeccionCaptura;
  valores: Record<string, string>;
  soloLectura: boolean;
  onChange: (codigo: string, valor: string) => void;
  onKeyDown: (event: React.KeyboardEvent<HTMLElement>) => void;
}

export function SeccionGrupoSanguineo({ seccion, valores, soloLectura, onChange, onKeyDown }: Props) {
  return <section className="lis-serologia-section">
    <h4 className="lis-sheet-section-title">{seccion.grupo?.replace(/_/g, " ")}</h4>
    <div className="lis-sheet-scroll">
      <table className="lis-captura-tabla lis-serologia-table lis-grupo-sanguineo-table" aria-label="Grupo sanguíneo">
        <colgroup>
          <col style={{ width: "30%" }} /><col style={{ width: "45%" }} /><col style={{ width: "25%" }} />
        </colgroup>
        <thead><tr>
          <th scope="col">Parámetro</th>
          <th scope="col" className="lis-sheet-entry-heading">Captura</th>
          <th scope="col">Resultado</th>
        </tr></thead>
        <tbody>{seccion.parametros.map((parametro) => {
          const valor = valores[parametro.codigo] ?? parametro.valor ?? "";
          return <tr key={parametro.codigo}>
            <td className="lis-sheet-parameter"><strong>{parametro.nombre}</strong></td>
            <td className="lis-sheet-entry">
              <select id={`input-${parametro.codigo}`} className="lis-captura-input"
                aria-label={parametro.nombre} value={valor} disabled={soloLectura}
                onChange={(event) => onChange(parametro.codigo, event.target.value)} onKeyDown={onKeyDown}>
                <option value="">--</option>
                {parametro.opciones?.map((opcion) => <option key={opcion} value={opcion}>{opcion}</option>)}
              </select>
            </td>
            <td className="lis-sheet-output"><output aria-label={`${parametro.nombre}: resultado`}>{valor}</output></td>
          </tr>;
        })}</tbody>
      </table>
    </div>
  </section>;
}
