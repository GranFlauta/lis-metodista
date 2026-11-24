import React, { useId } from "react";
import type { ActividadDiaria, SerieEstadistica } from "../../api/estadisticas";

const COLORES = ["#ff4969", "#06b6d4", "#8b5cf6", "#f59e0b", "#22c55e", "#ec4899"];

export function BarrasEstadistica({ datos }: { datos: SerieEstadistica[] }) {
  const maximo = Math.max(1, ...datos.map((item) => item.cantidad));
  if (!datos.length) return <p className="lis-chart-empty">No hay publicaciones para estos filtros.</p>;
  return <ul className="lis-chart-bars" aria-label="Cantidades por categoría">
    {datos.map((item, indice) => <li key={item.codigo}>
      <span title={item.nombre}>{item.nombre}</span>
      <div className="lis-chart-bar-track" aria-hidden="true"><span style={{ width: `${item.cantidad / maximo * 100}%`, background: COLORES[indice % COLORES.length] }} /></div>
      <strong>{item.cantidad.toLocaleString("es-BO")}</strong>
    </li>)}
  </ul>;
}

function colorEstado(codigo: string) {
  return ({ PUBLICADA: "#06b6d4", COMPLETO: "#22c55e", INCOMPLETO: "#f59e0b" } as Record<string, string>)[codigo] || "#a78bfa";
}

export function CircularEstadistica({ datos }: { datos: SerieEstadistica[] }) {
  const id = useId();
  const total = datos.reduce((sum, item) => sum + item.cantidad, 0);
  let acumulado = 0;
  return <div className="lis-chart-donut-layout">
    <svg className="lis-chart-donut" viewBox="0 0 200 200" role="img" aria-labelledby={id}>
      <title id={id}>{total ? datos.map((item) => `${item.nombre}: ${item.cantidad}`).join(". ") : "Sin órdenes en el período"}</title>
      <circle cx="100" cy="100" r="74" fill="none" stroke="var(--bg-muted)" strokeWidth="22" />
      {datos.filter((item) => item.cantidad > 0).map((item) => {
        const parte = item.cantidad / total * 100;
        const inicio = acumulado;
        acumulado += parte;
        return <circle key={item.codigo} cx="100" cy="100" r="74" fill="none" stroke={colorEstado(item.codigo)} strokeWidth="22"
          pathLength="100" strokeDasharray={`${parte} ${100 - parte}`} strokeDashoffset={-inicio} transform="rotate(-90 100 100)">
          <title>{item.nombre}: {item.cantidad}</title>
        </circle>;
      })}
      <text x="100" y="99" textAnchor="middle" className="lis-chart-donut-number">{total.toLocaleString("es-BO")}</text>
      <text x="100" y="120" textAnchor="middle" className="lis-chart-donut-label">órdenes</text>
    </svg>
    <ul className="lis-chart-legend">
      {datos.map((item) => <li key={item.codigo}>
        <i style={{ background: colorEstado(item.codigo) }} aria-hidden="true" />
        <span>{item.nombre}</span><strong>{item.cantidad}</strong>
        <small>{total ? Math.round(item.cantidad / total * 100) : 0}%</small>
      </li>)}
      {!total && <li className="lis-text-muted">No hay órdenes para estos filtros.</li>}
    </ul>
  </div>;
}

/** Agrupa rangos largos en semanas para mantener las barras legibles. */
export function agruparActividad(dias: ActividadDiaria[]): ActividadDiaria[] {
  const paso = dias.length > 45 ? 7 : 1;
  const grupos: ActividadDiaria[] = [];
  for (let inicio = 0; inicio < dias.length; inicio += paso) {
    const bloque = dias.slice(inicio, inicio + paso);
    grupos.push({ fecha: bloque[0].fecha, iniciadas: bloque.reduce((sum, item) => sum + item.iniciadas, 0), publicadas: bloque.reduce((sum, item) => sum + item.publicadas, 0) });
  }
  return grupos;
}

export function ActividadEstadistica({ dias }: { dias: ActividadDiaria[] }) {
  const titulo = useId();
  const datos = agruparActividad(dias);
  const maximo = Math.max(1, ...datos.map((item) => item.iniciadas));
  const ancho = 780, alto = 156, izquierda = 36, arriba = 14, base = 126;
  const espacio = (ancho - izquierda - 10) / Math.max(datos.length, 1);
  const anchoBarra = Math.min(16, espacio * 0.34);
  return <div className="lis-chart-activity">
    <svg viewBox={`0 0 ${ancho} ${alto}`} role="img" aria-labelledby={titulo}>
      <title id={titulo}>Órdenes iniciadas por {dias.length > 45 ? "semana" : "día"} y cuántas ya fueron publicadas. Los valores están disponibles en el detalle de actividad.</title>
      {[...new Set([0, Math.ceil(maximo / 2), maximo])].map((valor) => {
        const y = base - valor / maximo * (base - arriba);
        return <g key={valor}><line x1={izquierda} x2={ancho - 4} y1={y} y2={y} className="lis-chart-grid" /><text x={izquierda - 7} y={y + 4} textAnchor="end">{valor}</text></g>;
      })}
      {datos.map((dia, indice) => {
        const x = izquierda + espacio * (indice + 0.5);
        const hInicio = dia.iniciadas / maximo * (base - arriba);
        const hPublicacion = dia.publicadas / maximo * (base - arriba);
        return <g key={dia.fecha}>
          <title>{dia.fecha}: {dia.iniciadas} iniciadas, {dia.publicadas} publicadas</title>
          <rect x={x - anchoBarra} y={base - hInicio} width={anchoBarra} height={hInicio} rx="3" fill="#ff4969" />
          <rect x={x + 1} y={base - hPublicacion} width={anchoBarra} height={hPublicacion} rx="3" fill="#06b6d4" />
          {(indice === 0 || indice === datos.length - 1 || indice % Math.max(1, Math.ceil(datos.length / 7)) === 0) &&
            <text x={x} y={base + 20} textAnchor="middle">{dia.fecha.slice(8)}/{dia.fecha.slice(5, 7)}</text>}
        </g>;
      })}
    </svg>
  </div>;
}
