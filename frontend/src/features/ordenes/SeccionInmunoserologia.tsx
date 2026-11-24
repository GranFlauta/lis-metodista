import React, { useState } from "react";
import { EntradaSerologia, ParametroCaptura, SeccionCaptura } from "../../api/resultados";
import { EntradaResultadoNumerico } from "../../components/EntradaResultadoNumerico";
import { Icono } from "../../components/Icono";
import { formatearResultadoClinico } from "../../utils/formatoNumerico";

interface Props {
  seccion: SeccionCaptura;
  valores: Record<string, string>;
  soloLectura: boolean;
  separadorDecimal: string;
  onChange: (codigo: string, valor: string) => void;
  onKeyDown: (event: React.KeyboardEvent<HTMLElement>) => void;
}

function entradaActual(parametro: ParametroCaptura, valor: string): EntradaSerologia {
  try {
    const entrada = JSON.parse(valor);
    if (entrada && typeof entrada.reactividad === "string") return entrada;
  } catch { /* Los resultados anteriores siguen siendo texto. */ }
  return parametro.serologia?.entrada || {
    reactividad: "", dilucion: "", reactivo: parametro.captura_serologia?.reactivos?.[0]?.nombre || "",
    sensibilidad: "", unidad: "",
  };
}

function requiereColumnaReactivo(parametro: ParametroCaptura): boolean {
  const config = parametro.captura_serologia;
  return config?.modo === "CALCULO" && (config.personalizable || (config.reactivos?.length || 0) > 1);
}

export function SeccionInmunoserologia({ seccion, valores, soloLectura, separadorDecimal, onChange, onKeyDown }: Props) {
  const [otraDilucion, setOtraDilucion] = useState<Record<string, boolean>>({});
  const columnas = seccion.columnas || { unidad: false, referencia: false };
  const columnasExtra = Number(columnas.unidad) + Number(columnas.referencia);
  const mostrarMuestraMetodo = seccion.grupo === "PARASITOLOGIA";
  const mostrarColumnaReactivo = seccion.parametros.some(requiereColumnaReactivo);
  const nombreSeccion = mostrarMuestraMetodo ? "SEROLOGIA" : seccion.grupo?.replace(/_/g, " ");
  const anchoResultadoReactivo = `${100 - 19 - 25 - 24 - (columnas.unidad ? 8 : 0) - (columnas.referencia ? 14 : 0)}%`;
  return <section className="lis-serologia-section">
    <h4 className="lis-sheet-section-title">{nombreSeccion}</h4>
    <div className="lis-sheet-scroll"><table className="lis-captura-tabla lis-serologia-table"
      style={{ minWidth: mostrarColumnaReactivo ? "640px" : undefined }}
      aria-label={nombreSeccion || "Inmunoserología"}>
      <colgroup>
        <col style={{ width: mostrarMuestraMetodo ? "23%" : mostrarColumnaReactivo ? "19%" : columnasExtra === 2 ? "23%" : columnasExtra === 1 ? "26%" : "30%" }} />
        {mostrarMuestraMetodo && <col style={{ width: "12%" }} />}
        {mostrarMuestraMetodo && <col style={{ width: "19%" }} />}
        {mostrarColumnaReactivo && <col style={{ width: "25%" }} />}
        <col style={{ width: mostrarMuestraMetodo ? "30%" : mostrarColumnaReactivo ? "24%" : columnasExtra === 2 ? "39%" : columnasExtra === 1 ? "40%" : "45%" }} />
        {columnas.unidad && <col style={{ width: mostrarColumnaReactivo ? "8%" : columnasExtra === 2 ? "10%" : "14%" }} />}
        {columnas.referencia && <col style={{ width: mostrarColumnaReactivo ? "14%" : columnasExtra === 2 ? "15%" : "14%" }} />}
        <col style={{ width: mostrarMuestraMetodo ? "16%" : mostrarColumnaReactivo ? anchoResultadoReactivo : columnasExtra === 2 ? "13%" : columnasExtra === 1 ? "20%" : "25%" }} />
      </colgroup>
      <thead><tr><th scope="col">Prueba</th>
        {mostrarMuestraMetodo && <><th scope="col">Muestra</th><th scope="col">Método</th></>}
        {mostrarColumnaReactivo && <th scope="col">Reactivo</th>}
        <th scope="col" className="lis-serologia-captura lis-sheet-entry-heading">Captura</th>
        {columnas.unidad && <th scope="col">Unidad</th>}{columnas.referencia && <th scope="col">V. Ref.</th>}
        <th scope="col" className="lis-serologia-resultado">Resultado</th>
      </tr></thead>
      <tbody>{seccion.parametros.map((parametro) => {
        const valor = valores[parametro.codigo] ?? parametro.valor ?? "";
        const config = parametro.captura_serologia;
        const esSeleccion = parametro.codigo === "VDRL_DILUCION" || parametro.tipo_campo === "SELECCION";
        const opciones = parametro.codigo === "VDRL_DILUCION" ? ["Negativo", "Positivo"] : parametro.opciones;
        const entrada = entradaActual(parametro, valor);
        const permiteReactivo = requiereColumnaReactivo(parametro);
        const actualizar = (cambios: Partial<EntradaSerologia>) => {
          const nueva = { ...entrada, ...cambios };
          if (nueva.reactividad !== "Positivo") nueva.dilucion = "";
          onChange(parametro.codigo, cambios.reactividad === "" ? "" : JSON.stringify(nueva));
        };
        const seleccionarReactivo = (nombre: string) => {
          const estandar = config?.reactivos?.find((r) => r.nombre === nombre);
          const personalizado = nombre === "PERSONALIZADO";
          actualizar({
            reactivo: nombre,
            sensibilidad: "",
            unidad: estandar?.unidad || (personalizado ? config?.unidades?.[0] || "" : ""),
          });
        };
        const reactivo = config?.reactivos?.find((r) => r.nombre === entrada.reactivo) || (entrada.reactivo !== "PERSONALIZADO" ? config?.reactivos?.[0] : undefined);
        const propia = otraDilucion[parametro.codigo] || Boolean(entrada.dilucion && !config?.diluciones.includes(entrada.dilucion));
        const presentacion = parametro.serologia;
        const coincide = presentacion && Object.keys(entrada).every((key) => entrada[key as keyof EntradaSerologia] === presentacion.entrada[key as keyof EntradaSerologia]);
        const resultado = config
          ? coincide ? (presentacion.resultado ?? "Esperando datos") : valor ? "Actualizando…" : "Esperando datos"
          : parametro.tipo_campo === "NUMERICO" ? formatearResultadoClinico(valor, separadorDecimal) : valor;
        const unidad = config ? (reactivo?.unidad || entrada.unidad) : parametro.unidad;
        const referencia = coincide && presentacion.referencia ? presentacion.referencia
          : reactivo ? `${reactivo.nombre} <${reactivo.sensibilidad} ${reactivo.unidad}` : "";
        const nombreVisible = parametro.codigo === "SANGRE_OCULTA_HECES_INMUNO"
          ? "SANGRE OCULTA EN HECES"
          : parametro.nombre;
        return <tr key={parametro.codigo}>
          <td className="lis-sheet-parameter"><strong>{nombreVisible}</strong>{parametro.obligatorio && <span className="lis-serologia-required" aria-label="Obligatorio"> *</span>}</td>
          {mostrarMuestraMetodo && <><td>{parametro.muestra || ""}</td><td>{parametro.metodo || ""}</td></>}
          {mostrarColumnaReactivo && <td className="lis-serologia-reactivo-cell">
            {permiteReactivo && config && (entrada.reactivo === "PERSONALIZADO" ? <div className="lis-serologia-inline-control">
              <EntradaResultadoNumerico className="lis-captura-input" value={entrada.sensibilidad}
                separadorDecimal={separadorDecimal} onValueChange={(sensibilidad) => actualizar({ sensibilidad })}
                aria-label={`${nombreVisible}: sensibilidad propia`} disabled={soloLectura} onKeyDown={onKeyDown} />
              {(config.unidades?.length || 0) === 1 && <span className="lis-serologia-unit-suffix">{config.unidades?.[0]}</span>}
              {(config.unidades?.length || 0) > 1 && <select className="lis-captura-input" value={entrada.unidad}
                onChange={(event) => actualizar({ unidad: event.target.value })}
                aria-label={`${nombreVisible}: unidad propia`} disabled={soloLectura} onKeyDown={onKeyDown}>
                <option value="">--</option>{config.unidades?.map((unidad) => <option key={unidad}>{unidad}</option>)}
              </select>}
              <button type="button" className="lis-sheet-icon-btn" title="Volver al reactivo estándar"
                aria-label={`${nombreVisible}: volver al reactivo estándar`} disabled={soloLectura}
                onClick={() => {
                  const estandar = config.reactivos?.[0];
                  actualizar({ reactivo: estandar?.nombre || "", sensibilidad: "", unidad: estandar?.unidad || config.unidades?.[0] || "" });
                }}>
                <Icono nombre="ajustes" size={15} />
              </button>
            </div> : <select className="lis-captura-input"
              value={entrada.reactivo || config.reactivos?.[0]?.nombre || ""}
              onChange={(event) => seleccionarReactivo(event.target.value)}
              aria-label={`${nombreVisible}: reactivo`} disabled={soloLectura} onKeyDown={onKeyDown}>
              {config.reactivos?.map((r) => <option key={r.nombre} value={r.nombre}>{r.nombre} · {r.sensibilidad} {r.unidad}</option>)}
              {config.personalizable && <option value="PERSONALIZADO">Valor propio</option>}
            </select>)}
          </td>}
          <td className="lis-sheet-entry">{config ? <div className="lis-serologia-controls">
            <label>Reactividad<select id={`input-${parametro.codigo}`} className="lis-captura-input" value={entrada.reactividad}
              onChange={(event) => actualizar({ reactividad: event.target.value as EntradaSerologia["reactividad"] })}
              disabled={soloLectura} onKeyDown={onKeyDown} aria-label={`${parametro.nombre}: reactividad`}>
              <option value="">--</option><option>Negativo</option><option>Positivo</option>
            </select></label>
            {entrada.reactividad === "Positivo" && <>
              {propia ? <div className="lis-serologia-control">
                <span>Dilución</span>
                <div className="lis-serologia-inline-control">
                  <input className="lis-captura-input" value={entrada.dilucion} maxLength={40} placeholder="1/n"
                    onChange={(event) => actualizar({ dilucion: event.target.value })}
                    aria-label={`${parametro.nombre}: otra dilución`} disabled={soloLectura} onKeyDown={onKeyDown} />
                  <button type="button" className="lis-sheet-icon-btn" title="Seleccionar dilución estándar"
                    aria-label={`${parametro.nombre}: seleccionar dilución estándar`} disabled={soloLectura}
                    onClick={() => {
                      setOtraDilucion((prev) => ({ ...prev, [parametro.codigo]: false }));
                      actualizar({ dilucion: "" });
                    }}>
                    <Icono nombre="ajustes" size={15} />
                  </button>
                </div>
              </div> : <label>Dilución<select className="lis-captura-input" value={entrada.dilucion}
                onChange={(event) => {
                  const otra = event.target.value === "OTRA";
                  setOtraDilucion((prev) => ({ ...prev, [parametro.codigo]: otra }));
                  actualizar({ dilucion: otra ? "" : event.target.value });
                }}
                aria-label={`${parametro.nombre}: dilución`} disabled={soloLectura} onKeyDown={onKeyDown}>
                <option value="">{config.sin_dilucion ? "Sin dilución" : "Seleccione…"}</option>
                {config.diluciones.map((dilucion) => <option key={dilucion}>{dilucion}</option>)}<option value="OTRA">Otro</option>
              </select></label>}
            </>}
          </div> : esSeleccion ? <select id={`input-${parametro.codigo}`} className="lis-captura-input"
            aria-label={parametro.nombre} value={valor} onChange={(event) => onChange(parametro.codigo, event.target.value)} disabled={soloLectura} onKeyDown={onKeyDown}>
            <option value="">--</option>{opciones?.map((opcion) => <option key={opcion}>{opcion}</option>)}
          </select> : parametro.tipo_campo === "NUMERICO" ? <EntradaResultadoNumerico id={`input-${parametro.codigo}`} className="lis-captura-input"
            value={valor} separadorDecimal={separadorDecimal} onValueChange={(numero) => onChange(parametro.codigo, numero)} aria-label={parametro.nombre}
            disabled={soloLectura} onKeyDown={onKeyDown} /> : <input id={`input-${parametro.codigo}`} className="lis-captura-input"
            type={parametro.tipo_campo === "FECHA" ? "date" : "text"} value={valor} aria-label={parametro.nombre}
            onChange={(event) => onChange(parametro.codigo, event.target.value)} disabled={soloLectura} onKeyDown={onKeyDown} />}</td>
          {columnas.unidad && <td>{unidad && unidad !== "dilución" ? unidad : ""}</td>}
          {columnas.referencia && <td>{referencia}</td>}
          <td className="lis-serologia-resultado lis-sheet-output"><output title={coincide ? presentacion.motivo || undefined : undefined}>
            {config && coincide && presentacion.resultado && /^\d+(?:\.\d+)?$/.test(presentacion.resultado)
              ? formatearResultadoClinico(presentacion.resultado, separadorDecimal) : resultado}
          </output></td>
        </tr>;
      })}</tbody>
    </table></div>
  </section>;
}
