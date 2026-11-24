import React, { useId, useMemo, useRef, useState } from "react";
import { EntradaResultadoNumerico } from "../../components/EntradaResultadoNumerico";
import { Icono } from "../../components/Icono";
import { formatearEntradaNumerica } from "../../utils/formatoNumerico";
import type { EstudioCaptura } from "../../api/resultados";

type Props = {
  estudio: EstudioCaptura;
  valores: Record<string, string>;
  separadorDecimal: string;
  soloLectura: boolean;
  onChange: (codigo: string, valor: string) => void;
  onChangeMany: (cambios: Record<string, string>) => void;
  onKeyDown: (event: React.KeyboardEvent<HTMLElement>) => void;
};

type PuntoCurva = {
  fila: number;
  x: number;
  y: number;
  hora: string;
  glucosa: string;
  etiqueta: string;
};

const ANCHO = 720;
const ALTO = 300;
const IZQUIERDA = 54;
const DERECHA = 16;
const ARRIBA = 20;
const ABAJO = 54;
const GLUCOSA_MINIMA = 0;
const GLUCOSA_MAXIMA = 200;
const INTERVALO_GLUCOMETRICO = 20;

type DominioX = { inicio: number; fin: number };
type OrigenArrastre = {
  fila: number;
  x: number;
  y: number;
  clienteX: number;
  clienteY: number;
};

function instanteMinutos(fecha: string, hora: string): number | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(fecha) || !/^(?:[01]\d|2[0-3]):[0-5]\d$/.test(hora)) return null;
  const [anio, mes, dia] = fecha.split("-").map(Number);
  const [horas, minutos] = hora.split(":").map(Number);
  // El offset fijo de La Paz preserva los intervalos al operar con componentes locales como UTC.
  const fechaUtc = new Date(Date.UTC(anio, mes - 1, dia, horas, minutos));
  if (fechaUtc.getUTCFullYear() !== anio || fechaUtc.getUTCMonth() !== mes - 1 || fechaUtc.getUTCDate() !== dia) return null;
  return Math.floor(fechaUtc.getTime() / 60000);
}

function etiquetaHora(minutos: number): string {
  const fecha = new Date(minutos * 60000);
  return `${String(fecha.getUTCHours()).padStart(2, "0")}:${String(fecha.getUTCMinutes()).padStart(2, "0")}`;
}

function glucosaDesdeCoordenada(coordenada: number, decimales: number): string {
  const precision = Math.min(6, Math.max(0, Math.trunc(decimales)));
  const factor = 10 ** precision;
  const yMil = Math.round(Math.max(ARRIBA, Math.min(ALTO - ABAJO, coordenada)) * 1000);
  const arribaMil = ARRIBA * 1000;
  const abajoMil = (ALTO - ABAJO) * 1000;
  const denominador = abajoMil - arribaMil;
  const numerador = (abajoMil - yMil) * (GLUCOSA_MAXIMA - GLUCOSA_MINIMA) * factor;
  const unidades = Math.floor((numerador + denominador / 2) / denominador) + GLUCOSA_MINIMA * factor;
  const entero = Math.floor(unidades / factor);
  if (!precision) return String(entero);
  return `${entero}.${String(unidades % factor).padStart(precision, "0")}`;
}

export function CurvaToleranciaCaptura({
  estudio,
  valores,
  separadorDecimal,
  soloLectura,
  onChange,
  onChangeMany,
  onKeyDown,
}: Props) {
  const [puntoEnfocado, setPuntoEnfocado] = useState<number | null>(null);
  const [dominioArrastre, setDominioArrastre] = useState<DominioX | null>(null);
  const [arrastreActivo, setArrastreActivo] = useState(false);
  const [curvaModificada, setCurvaModificada] = useState(false);
  const clipId = `lis-curva-plot-${useId().replace(/:/g, "")}`;
  const filaArrastradaRef = useRef<number | null>(null);
  const origenArrastreRef = useRef<OrigenArrastre | null>(null);
  const dominioArrastreRef = useRef<DominioX | null>(null);
  const valoresAntesArrastreRef = useRef<Record<string, string> | null>(null);
  const curva = estudio.curva_tolerancia;
  const filas = curva?.configuracion.filas || [];
  const parametros = useMemo(
    () => new Map(estudio.secciones.flatMap((seccion) => seccion.parametros).map((parametro) => [parametro.codigo, parametro])),
    [estudio.secciones],
  );
  const leer = (codigo: string) => valores[codigo] ?? parametros.get(codigo)?.valor ?? "";

  const puntosPorFila = useMemo(() => {
    let tomaAnterior: number | null = null;
    let basal: number | null = null;
    return filas.map((fila, indice) => {
      const hora = leer(fila.hora);
      const fechaManual = leer(fila.fecha);
      const fecha = fechaManual || curva?.fecha_estudio || "";
      const instante = hora && fecha ? instanteMinutos(fecha, hora) : null;
      const retrocede = instante !== null && tomaAnterior !== null && instante < tomaAnterior;
      if (indice === 0 && instante !== null && !retrocede) basal = instante;
      if (instante !== null && !retrocede) tomaAnterior = instante;

      const raw = leer(fila.glucosa).trim().replace(",", ".");
      const glucosa = /^(?:\d+(?:\.\d{0,6})?|\.\d{1,6})$/.test(raw) ? Number(raw) : NaN;
      if (instante === null || retrocede || !Number.isFinite(glucosa)) {
        return { fila, indice, instante, retrocede, punto: null as PuntoCurva | null };
      }
      const minutos = basal === null ? null : instante - basal;
      const nombreToma = indice === 0 ? "Basal" : `${fila.etiqueta} toma`;
      const detalle = minutos === null ? "" : ` · ${minutos} min desde basal`;
      const glucosaVisible = formatearEntradaNumerica(leer(fila.glucosa), separadorDecimal);
      return {
        fila,
        indice,
        instante,
        retrocede,
        punto: {
          fila: indice,
          x: instante,
          y: glucosa,
          hora,
          glucosa: leer(fila.glucosa),
          etiqueta: `${nombreToma} · ${hora} · ${glucosaVisible} ${curva?.configuracion.unidad || "mg/dL"}${detalle}`,
        },
      };
    });
  }, [curva, filas, parametros, separadorDecimal, valores]);

  const puntos = puntosPorFila.flatMap((item) => item.punto ? [item.punto] : []);
  const xValores = puntos.map((punto) => punto.x);
  const xMin = xValores.length ? Math.min(...xValores) : 0;
  const xMax = xValores.length ? Math.max(...xValores) : 0;
  const margenX = xMax > xMin ? Math.max(5, (xMax - xMin) * 0.05) : 30;
  const xInicio = dominioArrastre?.inicio ?? xMin - margenX;
  const xFin = dominioArrastre?.fin ?? xMax + margenX;
  const plotAncho = ANCHO - IZQUIERDA - DERECHA;
  const plotAlto = ALTO - ARRIBA - ABAJO;
  const x = (valor: number) => IZQUIERDA + (valor - xInicio) / (xFin - xInicio) * plotAncho;
  const y = (valor: number) => ARRIBA + (GLUCOSA_MAXIMA - valor) / (GLUCOSA_MAXIMA - GLUCOSA_MINIMA) * plotAlto;
  const ticksX = [...new Set(xValores)].sort((a, b) => a - b);
  const ticksY = Array.from(
    { length: (GLUCOSA_MAXIMA - GLUCOSA_MINIMA) / INTERVALO_GLUCOMETRICO + 1 },
    (_, indice) => GLUCOSA_MINIMA + indice * INTERVALO_GLUCOMETRICO,
  );
  const segmentos: PuntoCurva[][] = [];
  puntosPorFila.forEach((item) => {
    if (!item.punto) return segmentos.push([]);
    const ultimo = segmentos[segmentos.length - 1];
    if (ultimo) ultimo.push(item.punto);
    else segmentos.push([item.punto]);
  });
  const seleccion = puntos.find((punto) => punto.fila === puntoEnfocado);

  const iniciarArrastre = (event: React.PointerEvent<SVGSVGElement>) => {
    if (soloLectura || event.button > 0) return;
    const objetivo = event.target;
    if (!(objetivo instanceof Element)) return;
    const filaTexto = objetivo.closest("[data-curva-fila]")?.getAttribute("data-curva-fila");
    if (filaTexto === null || filaTexto === undefined) return;
    const indice = Number(filaTexto);
    const punto = puntos.find((item) => item.fila === indice);
    if (!punto || !filas[indice]) return;

    if (!valoresAntesArrastreRef.current) {
      valoresAntesArrastreRef.current = Object.fromEntries(
        filas.flatMap((fila) => [
          [fila.hora, leer(fila.hora)],
          [fila.glucosa, leer(fila.glucosa)],
          [fila.fecha, leer(fila.fecha)],
        ]),
      );
    }

    const dominio = { inicio: xInicio, fin: xFin };
    dominioArrastreRef.current = dominio;
    origenArrastreRef.current = {
      fila: indice,
      x: punto.x,
      y: punto.y,
      clienteX: event.clientX,
      clienteY: event.clientY,
    };
    filaArrastradaRef.current = indice;
    setArrastreActivo(true);
    setPuntoEnfocado(indice);
    setDominioArrastre(dominio);
    event.currentTarget.setPointerCapture(event.pointerId);
    event.preventDefault();
  };

  const moverPunto = (event: React.PointerEvent<SVGSVGElement>) => {
    const origen = origenArrastreRef.current;
    const dominio = dominioArrastreRef.current;
    const fila = origen && filas[origen.fila];
    if (!origen || !dominio || !fila || soloLectura) return;

    const limites = event.currentTarget.getBoundingClientRect();
    if (!limites.width || !limites.height) return;
    const coordenadaX = (event.clientX - limites.left) * ANCHO / limites.width;
    const coordenadaY = (event.clientY - limites.top) * ALTO / limites.height;
    const desplazamientoX = Math.abs(event.clientX - origen.clienteX) > 2;
    const desplazamientoY = Math.abs(event.clientY - origen.clienteY) > 2;

    let nuevoMinuto = origen.x;
    if (desplazamientoX) {
      const fraccion = Math.max(0, Math.min(1, (coordenadaX - IZQUIERDA) / plotAncho));
      const candidato = Math.round(dominio.inicio + fraccion * (dominio.fin - dominio.inicio));
      const anterior = puntosPorFila.slice(0, origen.fila).reverse().find((item) => item.instante !== null && !item.retrocede)?.instante;
      const siguiente = puntosPorFila.slice(origen.fila + 1).find((item) => item.instante !== null && !item.retrocede)?.instante;
      const minimo = Math.max(dominio.inicio, anterior ?? dominio.inicio);
      const maximo = Math.min(dominio.fin, siguiente ?? dominio.fin);
      nuevoMinuto = Math.max(minimo, Math.min(maximo, candidato));
    }

    let valorGlucosa = leer(fila.glucosa);
    if (desplazamientoY) {
      valorGlucosa = glucosaDesdeCoordenada(coordenadaY, parametros.get(fila.glucosa)?.decimales ?? 0);
    }

    const fechaHora = new Date(nuevoMinuto * 60000);
    const hora = etiquetaHora(nuevoMinuto);
    const fecha = fechaHora.toISOString().slice(0, 10);
    const cambios: Record<string, string> = {};
    if (desplazamientoX && hora !== leer(fila.hora)) cambios[fila.hora] = hora;
    if (desplazamientoY && valorGlucosa !== leer(fila.glucosa)) cambios[fila.glucosa] = valorGlucosa;
    if (desplazamientoX) {
      const fechaManual = fecha === curva?.fecha_estudio ? "" : fecha;
      if (fechaManual !== leer(fila.fecha)) cambios[fila.fecha] = fechaManual;
    }
    if (Object.keys(cambios).length) {
      onChangeMany(cambios);
      setCurvaModificada(true);
    }
  };

  const finalizarArrastre = (event: React.PointerEvent<SVGSVGElement>) => {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    filaArrastradaRef.current = null;
    origenArrastreRef.current = null;
    dominioArrastreRef.current = null;
    setArrastreActivo(false);
    setDominioArrastre(null);
  };

  const restablecerCurva = () => {
    const valoresOriginales = valoresAntesArrastreRef.current;
    if (!valoresOriginales) return;
    const cambios = Object.fromEntries(
      Object.entries(valoresOriginales).filter(([codigo, valor]) => leer(codigo) !== valor),
    );
    if (Object.keys(cambios).length) onChangeMany(cambios);
    valoresAntesArrastreRef.current = null;
    dominioArrastreRef.current = null;
    filaArrastradaRef.current = null;
    origenArrastreRef.current = null;
    setArrastreActivo(false);
    setDominioArrastre(null);
    setCurvaModificada(false);
  };

  return <section className="lis-curva-captura" aria-label="Captura de curva de tolerancia">
    <h4 className="lis-sheet-section-title">Curva de tolerancia oral a la glucosa</h4>
    <div className="lis-sheet-scroll">
      <table className="lis-captura-tabla lis-curva-tabla" aria-label="Resultados de curva de tolerancia">
        <colgroup><col className="lis-curva-col-toma" /><col className="lis-curva-col-hora" /><col className="lis-curva-col-glucosa" /><col className="lis-curva-col-unidad" /></colgroup>
        <thead><tr><th scope="col">Toma</th><th scope="col">Hora de toma</th><th scope="col">Glucosa</th><th scope="col">Unidad</th></tr></thead>
        <tbody>
          {filas.map((fila, indice) => {
            const hora = leer(fila.hora);
            const fechaManual = leer(fila.fecha);
            const evaluacion = puntosPorFila[indice];
            const necesitaFecha = Boolean(fechaManual || hora && (!curva?.fecha_estudio || evaluacion?.retrocede));
            return <tr key={fila.id}>
              <th scope="row" className="lis-curva-toma">{fila.etiqueta}</th>
              <td>
                <input
                  type="time"
                  step={60}
                  className="lis-captura-input lis-curva-input"
                  aria-label={`Hora de toma ${fila.etiqueta}`}
                  value={hora}
                  disabled={soloLectura}
                  aria-invalid={evaluacion?.retrocede || undefined}
                  onChange={(event) => onChange(fila.hora, event.currentTarget.value)}
                  onKeyDown={onKeyDown}
                />
              </td>
              <td>
                <EntradaResultadoNumerico
                  className="lis-captura-input lis-curva-input"
                  aria-label={`Glucosa ${fila.etiqueta}`}
                  value={leer(fila.glucosa)}
                  separadorDecimal={separadorDecimal}
                  onValueChange={(valor) => onChange(fila.glucosa, valor)}
                  onKeyDown={onKeyDown}
                  disabled={soloLectura}
                  autoComplete="off"
                  aria-invalid={evaluacion?.retrocede || undefined}
                />
                {necesitaFecha && <label className="lis-curva-fecha">
                  <span>{evaluacion?.retrocede ? "Aclara la fecha real" : "Fecha de toma"}</span>
                  <input
                    type="date"
                    className="lis-captura-input"
                    aria-label={`Fecha real de toma ${fila.etiqueta}`}
                    value={fechaManual}
                    disabled={soloLectura}
                    onChange={(event) => onChange(fila.fecha, event.currentTarget.value)}
                    onKeyDown={onKeyDown}
                  />
                </label>}
              </td>
              <td className="lis-curva-unidad">{curva?.configuracion.unidad || "mg/dL"}</td>
            </tr>;
          })}
        </tbody>
      </table>
    </div>
    <div className="lis-curva-grafico" aria-label="Gráfica de la curva de tolerancia">
      {!puntos.length ? <p className="lis-curva-vacio">Ingresa la hora y la glucosa de una toma para ver la curva</p> : <>
        <div className="lis-curva-grafico-encabezado">
          <h4>Curva de tolerancia oral a la glucosa</h4>
          <div className="lis-curva-grafico-acciones">
            {!soloLectura && <button
              type="button"
              className="lis-btn lis-btn-outline lis-btn-sm"
              aria-label="Restablecer curva a los valores anteriores al arrastre"
              title="Restablecer curva"
              onClick={restablecerCurva}
              disabled={!curvaModificada}
            >
              <Icono nombre="restaurar" size={12} /> Restablecer
            </button>}
          </div>
        </div>
        <p className="lis-curva-detalle" role="status" aria-live="polite">{seleccion?.etiqueta || ""}</p>
        <svg
          viewBox={`0 0 ${ANCHO} ${ALTO}`}
          role="img"
          aria-label="Gráfica de glucosa según la hora real de toma"
          className={arrastreActivo ? "is-dragging" : undefined}
          onPointerDown={iniciarArrastre}
          onPointerMove={moverPunto}
          onPointerUp={finalizarArrastre}
          onPointerCancel={finalizarArrastre}
        >
          <defs><clipPath id={clipId}><rect x={IZQUIERDA} y={ARRIBA} width={plotAncho} height={plotAlto} /></clipPath></defs>
          {ticksY.map((valor, indice) => <g key={`y-${indice}`}>
            <line x1={IZQUIERDA} x2={ANCHO - DERECHA} y1={y(valor)} y2={y(valor)} className="lis-curva-guia" />
            <text x={IZQUIERDA - 8} y={y(valor) + 4} textAnchor="end" className="lis-curva-etiqueta">{valor}</text>
          </g>)}
          {ticksX.map((valor, indice) => <line
            key={`guia-x-${indice}`}
            x1={x(valor)}
            x2={x(valor)}
            y1={ARRIBA}
            y2={ALTO - ABAJO}
            className="lis-curva-guia lis-curva-guia-vertical"
          />)}
          <line x1={IZQUIERDA} x2={IZQUIERDA} y1={ARRIBA} y2={ALTO - ABAJO} className="lis-curva-eje" />
          <line x1={IZQUIERDA} x2={ANCHO - DERECHA} y1={ALTO - ABAJO} y2={ALTO - ABAJO} className="lis-curva-eje" />
          {ticksX.map((valor, indice) => <g key={`x-${indice}`}>
            <text x={x(valor)} y={ALTO - ABAJO + 17} textAnchor="middle" className="lis-curva-etiqueta">{etiquetaHora(valor)}</text>
          </g>)}
          <g clipPath={`url(#${clipId})`}>
            {segmentos.filter((segmento) => segmento.length > 1).map((segmento) => <path
              key={`segmento-${segmento[0].fila}`}
              d={segmento.map((punto, indice) => `${indice ? "L" : "M"} ${x(punto.x)} ${y(punto.y)}`).join(" ")}
              className="lis-curva-linea"
            />)}
            {puntos.filter((punto) => punto.y >= GLUCOSA_MINIMA && punto.y <= GLUCOSA_MAXIMA).map((punto) => <circle
              key={punto.fila}
              cx={x(punto.x)}
              cy={y(punto.y)}
              r={puntoEnfocado === punto.fila ? 5 : 4}
              className="lis-curva-punto"
              data-curva-fila={punto.fila}
              tabIndex={0}
              role="img"
              aria-label={punto.etiqueta}
              onFocus={() => setPuntoEnfocado(punto.fila)}
              onBlur={() => setPuntoEnfocado(null)}
            ><title>{punto.etiqueta}</title></circle>)}
          </g>
          {puntos.filter((punto) => punto.y < GLUCOSA_MINIMA || punto.y > GLUCOSA_MAXIMA).map((punto) => {
            const fueraPorArriba = punto.y > GLUCOSA_MAXIMA;
            const borde = fueraPorArriba ? ARRIBA : ALTO - ABAJO;
            const direccion = fueraPorArriba ? 1 : -1;
            return <path
              key={punto.fila}
              d={`M ${x(punto.x)} ${borde} l -5 ${direccion * 8} h 10 Z`}
              className="lis-curva-punto-fuera"
              data-curva-fila={punto.fila}
              tabIndex={0}
              role="img"
              aria-label={`${punto.etiqueta} · fuera de escala`}
              onFocus={() => setPuntoEnfocado(punto.fila)}
              onBlur={() => setPuntoEnfocado(null)}
            ><title>{punto.etiqueta} · fuera de escala 0–200 mg/dL; valor exacto en la tabla</title></path>;
          })}
          <text x={IZQUIERDA + plotAncho / 2} y={ALTO - 3} textAnchor="middle" className="lis-curva-titulo-eje">Hora de toma</text>
          <text transform={`translate(14 ${ARRIBA + plotAlto / 2}) rotate(-90)`} textAnchor="middle" className="lis-curva-titulo-eje">Glucosa (mg/dL)</text>
        </svg>
      </>}
    </div>
  </section>;
}
