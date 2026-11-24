import React, { useEffect, useState } from "react";
import { ApiError } from "../../api/client";
import { Estadistica, FiltrosEstadistica, obtenerEstadisticasApi } from "../../api/estadisticas";
import { Icono } from "../../components/Icono";
import { CargaLaboratorio } from "../../components/MarcaLaboratorio";
import { useAuth } from "../auth/AuthProvider";
import { ActividadEstadistica, agruparActividad, BarrasEstadistica, CircularEstadistica } from "./GraficosEstadistica";

function rangoPeriodo(dias: number): FiltrosEstadistica {
  const hasta = new Intl.DateTimeFormat("sv-SE", { timeZone: "America/La_Paz" }).format(new Date());
  const inicio = new Date(`${hasta}T12:00:00Z`);
  inicio.setUTCDate(inicio.getUTCDate() - dias + 1);
  return { desde: inicio.toISOString().slice(0, 10), hasta, id_autor: "", respuesta: "todas" };
}

function duracion(minutos: string | null) {
  if (minutos === null) return "Sin datos";
  const total = Math.round(Number(minutos));
  if (total < 60) return `${total} min`;
  const horas = Math.floor(total / 60);
  return `${horas} h${total % 60 ? ` ${total % 60} min` : ""}`;
}

export const EstadisticasPage: React.FC = () => {
  const { usuario } = useAuth();
  const esAdmin = usuario?.rol === "ADMIN";
  const [filtros, setFiltros] = useState(rangoPeriodo(30));
  const [aplicados, setAplicados] = useState(filtros);
  const [periodo, setPeriodo] = useState("30");
  const [recarga, setRecarga] = useState(0);
  const [datos, setDatos] = useState<Estadistica | null>(null);
  const [profesionales, setProfesionales] = useState<Estadistica["profesionales"]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [metrica, setMetrica] = useState<"estudios" | "responsables">("estudios");
  const [orden, setOrden] = useState("desc");

  useEffect(() => {
    const controlador = new AbortController();
    setCargando(true);
    setError("");
    obtenerEstadisticasApi(aplicados, controlador.signal).then((respuesta) => {
      if (controlador.signal.aborted) return;
      setDatos(respuesta);
      setProfesionales(respuesta.profesionales);
    }).catch((err) => {
      if (!controlador.signal.aborted) setError(err instanceof ApiError ? err.message : "No se pudieron cargar las estadísticas. Reintenta la consulta.");
    }).finally(() => { if (!controlador.signal.aborted) setCargando(false); });
    return () => controlador.abort();
  }, [aplicados, recarga]);

  const barras = datos ? [...datos[metrica]].sort((a, b) => (orden === "desc" ? b.cantidad - a.cantidad : a.cantidad - b.cantidad) || a.nombre.localeCompare(b.nombre)) : [];
  const resumen = datos?.resumen;

  return <div className="lis-stats-page">
    <div className="lis-page-header">
      <div><h2>Estadísticas de desempeño</h2><p className="lis-page-sub">{esAdmin ? "Actividad del laboratorio y sus responsables." : "Actividad de las órdenes bajo tu responsabilidad."}</p></div>
      <button type="button" className="lis-btn lis-btn-secondary" disabled={cargando} onClick={() => setRecarga((valor) => valor + 1)}><Icono nombre="restaurar" size={16} /> Actualizar</button>
    </div>

    <form className="lis-stats-filters" onSubmit={(evento) => { evento.preventDefault(); setAplicados({ ...filtros }); }}>
      <label>Período de inicio<select value={periodo} onChange={(evento) => {
        const valor = evento.target.value;
        setPeriodo(valor);
        if (valor !== "personalizado") setFiltros((prev) => ({ ...prev, ...rangoPeriodo(Number(valor)), id_autor: prev.id_autor, respuesta: prev.respuesta }));
      }}><option value="7">Últimos 7 días</option><option value="30">Últimos 30 días</option><option value="90">Últimos 90 días</option><option value="personalizado">Personalizado</option></select></label>
      <label>Desde<input type="date" value={filtros.desde} required onChange={(evento) => { setPeriodo("personalizado"); setFiltros((prev) => ({ ...prev, desde: evento.target.value })); }} /></label>
      <label>Hasta<input type="date" value={filtros.hasta} min={filtros.desde} required onChange={(evento) => { setPeriodo("personalizado"); setFiltros((prev) => ({ ...prev, hasta: evento.target.value })); }} /></label>
      {esAdmin && <label>Responsable<select value={filtros.id_autor} onChange={(evento) => setFiltros((prev) => ({ ...prev, id_autor: evento.target.value }))}>
        <option value="">Todos los profesionales</option>
        {profesionales.map((profesional) => <option key={profesional.id} value={profesional.id}>LIC. {profesional.nombre}{!profesional.activo ? " (inactivo)" : ""}</option>)}
      </select></label>}
      <label>Duración hasta la primera entrega<select aria-describedby="ayuda-tiempo-respuesta" value={filtros.respuesta} onChange={(evento) => setFiltros((prev) => ({ ...prev, respuesta: evento.target.value as FiltrosEstadistica["respuesta"] }))}>
        <option value="todas">Todas, incluidas las pendientes</option><option value="hasta_60">Entregadas en hasta 1 hora</option><option value="de_60_a_240">Entregadas en más de 1 y hasta 4 horas</option><option value="mas_240">Entregadas en más de 4 horas</option><option value="sin_hora">Entregadas sin intervalo válido</option>
      </select></label>
      <button type="submit" className="lis-btn lis-btn-primary" disabled={cargando}>Aplicar filtros</button>
    </form>
    <p id="ayuda-tiempo-respuesta" className="lis-stats-filter-help">Este filtro cuenta el tiempo entre la toma de muestra y la primera publicación del informe. Al elegir una duración, los gráficos muestran sólo las órdenes ya entregadas en ese intervalo. «Todas» conserva también las pendientes.</p>

    {cargando && <CargaLaboratorio mensaje="Consultando actividad del laboratorio…" />}
    {error && <div className="lis-alert lis-alert-error" role="alert">{error}<button type="button" className="lis-btn lis-btn-secondary" onClick={() => setRecarga((valor) => valor + 1)}>Reintentar</button></div>}

    {!cargando && !error && datos && resumen && <>
      <div className="lis-stats-context"><span><Icono nombre="tabla" size={15} /> Órdenes iniciadas del {datos.desde.split("-").reverse().join("/")} al {datos.hasta.split("-").reverse().join("/")}{datos.respuesta !== "todas" ? " · Con el filtro de respuesta seleccionado" : ""}</span><small>Actualizado {new Intl.DateTimeFormat("es-BO", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "America/La_Paz" }).format(new Date(datos.generado_en))}</small></div>
      <dl className="lis-stats-metrics">
        <div><dt><Icono nombre="tabla" size={17} /> Órdenes iniciadas</dt><dd>{resumen.ordenes.toLocaleString("es-BO")}</dd><small>{resumen.pendientes} pendientes de publicación</small></div>
        <div><dt><Icono nombre="documento" size={17} /> Informes publicados</dt><dd>{resumen.publicadas.toLocaleString("es-BO")}</dd><small>Una primera entrega por orden</small></div>
        <div><dt><Icono nombre="catalogo" size={17} /> Estudios informados</dt><dd>{resumen.estudios_informados.toLocaleString("es-BO")}</dd><small>Sólo estudios con resultados publicados</small></div>
        <div><dt><Icono nombre="reloj" size={17} /> Mediana de respuesta</dt><dd>{duracion(resumen.respuesta_mediana_minutos)}</dd><small>{resumen.respuestas_validas} entregas con hora válida</small></div>
      </dl>

      {!resumen.ordenes && <p className="lis-stats-empty" role="status">No hay órdenes que coincidan con estos filtros. Prueba otro período o tiempo de respuesta.</p>}

      <div className="lis-stats-main-charts">
        <section className="lis-stats-panel">
          <div className="lis-stats-panel-heading"><h3>Volumen de actividad</h3><div className="lis-stats-chart-controls">
            <label><span className="lis-sr-only">Métrica del gráfico de barras</span><select value={metrica} onChange={(evento) => setMetrica(evento.target.value as typeof metrica)}><option value="estudios">Por estudio informado</option><option value="responsables">Por responsable</option></select></label>
            <label><span className="lis-sr-only">Orden de las cantidades</span><select value={orden} onChange={(evento) => setOrden(evento.target.value)}><option value="desc">Mayor primero</option><option value="asc">Menor primero</option></select></label>
          </div></div>
          <BarrasEstadistica datos={barras} />
        </section>
        <section className="lis-stats-panel"><div className="lis-stats-panel-heading"><h3>Estado del trabajo</h3><span className="lis-text-muted">{resumen.ordenes} órdenes</span></div><CircularEstadistica datos={datos.estados} /></section>
      </div>

      <div className="lis-stats-secondary-charts">
        <section className="lis-stats-panel"><div className="lis-stats-panel-heading"><h3>Actividad por {datos.actividad.length > 45 ? "semana" : "día"} de inicio</h3><div className="lis-chart-inline-legend"><span><i style={{ background: "#ff4969" }} />Iniciadas</span><span><i style={{ background: "#06b6d4" }} />Ya publicadas</span></div></div><ActividadEstadistica dias={datos.actividad} /></section>
        <section className="lis-stats-panel"><div className="lis-stats-panel-heading"><h3>Tiempo hasta la entrega</h3></div><BarrasEstadistica datos={datos.tiempos_respuesta} /><p className="lis-stats-note">Toma de muestra → primera publicación. Si no hay hora de toma, se usa la creación de la orden.</p></section>
      </div>

      <details className="lis-stats-panel lis-stats-detail"><summary>Ver detalle de los gráficos</summary>
        <div className="lis-stats-detail-grid">
          <div className="lis-table-responsive"><table className="lis-table lis-table-dense"><caption>{metrica === "estudios" ? "Estudios informados" : "Informes por responsable"}</caption><thead><tr><th>{metrica === "estudios" ? "Estudio" : "Responsable"}</th><th className="lis-text-right">Cantidad</th></tr></thead><tbody>{barras.map((fila) => <tr key={fila.codigo}><td>{fila.nombre}</td><td className="lis-text-right">{fila.cantidad}</td></tr>)}</tbody></table></div>
          <div className="lis-table-responsive"><table className="lis-table lis-table-dense"><caption>Actividad por {datos.actividad.length > 45 ? "semana" : "día"} de inicio</caption><thead><tr><th>Fecha de inicio</th><th className="lis-text-right">Iniciadas</th><th className="lis-text-right">Ya publicadas</th></tr></thead><tbody>{agruparActividad(datos.actividad).map((fila) => <tr key={fila.fecha}><td>{fila.fecha.split("-").reverse().join("/")}</td><td className="lis-text-right">{fila.iniciadas}</td><td className="lis-text-right">{fila.publicadas}</td></tr>)}</tbody></table></div>
        </div>
      </details>
      <p className="lis-stats-note">Cada orden se cuenta una vez por su fecha de creación, en hora de Bolivia. Las versiones, vistas previas e impresiones no suman entregas. Los tiempos agrupan actividad; no representan metas clínicas.{resumen.publicadas_sin_hora ? ` Se excluyen ${resumen.publicadas_sin_hora} entregas sin un intervalo válido de la mediana.` : ""}</p>
    </>}
  </div>;
};
