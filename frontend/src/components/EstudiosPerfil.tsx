import React from "react";
import type { EstudioCatalogo, GrupoEstudioCatalogo, PerfilEstudioItem } from "../api/catalogo";

function etiquetaGrupo(codigo: string): string {
  return codigo === "PARASITOLOGIA" ? "SEROLOGIA" : codigo.replace(/_/g, " ");
}

/** El label completo activa la casilla una sola vez, también con teclado. */
export function SeleccionSubestudios({ grupos, seleccionados, onToggle }: {
  grupos: GrupoEstudioCatalogo[]; seleccionados: ReadonlySet<string>; onToggle: (codigo: string) => void;
}) {
  return <div className="lis-inmunosero-grid">{grupos.map((grupo) => <label key={grupo.codigo}
    className={`lis-inmunosero-item ${seleccionados.has(grupo.codigo) ? "selected" : ""}`}>
    <input type="checkbox" checked={seleccionados.has(grupo.codigo)} onChange={() => onToggle(grupo.codigo)} />
    <span><strong>{etiquetaGrupo(grupo.codigo)}</strong><small>{grupo.parametros.map((p) => p.nombre).join(", ")}</small></span>
  </label>)}</div>;
}

export function resumenEstudiosPerfil(items: PerfilEstudioItem[], catalogo: EstudioCatalogo[]): string {
  return items.map((item) => {
    const nombre = catalogo.find((estudio) => estudio.codigo === item.codigo)?.nombre || item.codigo;
    return `${nombre}${item.grupos?.length ? ` (${item.grupos.map(etiquetaGrupo).join(", ")})` : ""}`;
  }).join(" · ");
}

export function EstudiosPerfil({ items, catalogo }: { items: PerfilEstudioItem[]; catalogo: EstudioCatalogo[] }) {
  return <div className="lis-table-responsive lis-profile-contents"><table className="lis-table lis-table-dense" aria-label="Estudios incluidos">
    <thead><tr><th scope="col">Estudio</th><th scope="col">Grupos</th></tr></thead>
    <tbody>{items.map((item) => {
      const estudio = catalogo.find((candidate) => candidate.codigo === item.codigo);
      const grupos = estudio?.grupos?.filter((grupo) => !item.grupos?.length || item.grupos.includes(grupo.codigo)) || [];
      const campos = grupos.length ? grupos.flatMap((grupo) => grupo.parametros) : estudio?.parametros || [];
      return <tr key={item.codigo}>
        <td>{estudio?.nombre || item.codigo}</td>
        <td><details className="lis-catalog-study-fields">
          <summary>{item.grupos?.length ? item.grupos.map(etiquetaGrupo).join(" · ") : `Ver campos (${campos.length})`}</summary>
          {grupos.length ? <div className="lis-catalog-groups">{grupos.map((grupo) => <details key={grupo.codigo}>
            <summary>{etiquetaGrupo(grupo.codigo)}</summary>
            <ul>{grupo.parametros.map((parametro) => <li key={parametro.codigo}>{parametro.nombre}</li>)}</ul>
          </details>)}</div> : <ul className="lis-catalog-field-list">{campos.map((parametro) => <li key={parametro.codigo}>{parametro.nombre}</li>)}</ul>}
        </details></td>
      </tr>;
    })}</tbody>
  </table></div>;
}
