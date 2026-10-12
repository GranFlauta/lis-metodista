/**
 * Pantalla de Captura de Resultados Clínicos, Cálculo en Vivo y Banderas.
 * Implementa PROMPT_FASE_3.md §9:
 * - Ruta /ordenes/:id/captura
 * - Formulario por estudio y secciones por grupo a la izquierda.
 * - Panel lateral fijo de "Vista previa" con tabla Parámetro · Resultado · Unidad · Referencia · Bandera.
 * - POST /calcular a los 400 ms de pausa sin recargar.
 * - PUT /resultados (autoguardado) a los 1500 ms de inactividad con indicador de estado visible.
 * - Banderas visuales con icono + texto (↓ Bajo, ↑ Alto, ✓ Normal).
 * - Confirmación de valores por defecto virtuales con botón explícito.
 * - Indicador de completitud interactivo (clic en pendiente enfoca el campo).
 * - Modo solo lectura para ADMIN (campos deshabilitados, sin botones de guardado/confirmación).
 * - Exclusividad de apiClient en memoria (sin localStorage ni sessionStorage).
 */

import React, { useEffect, useState, useRef, useCallback } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";
import {
  getCapturaOrdenApi,
  calcularResultadosApi,
  guardarResultadosApi,
  confirmarDefectosApi,
  getConfiguracionLaboratorioApi,
  CapturaOrdenResponse,
  ParametroCaptura,
  ConfiguracionLaboratorio,
} from "../../api/resultados";
import { ApiError } from "../../api/client";

export const CapturaResultadosPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const ordenId = Number(id);
  const navigate = useNavigate();
  const { usuario } = useAuth();
  const esAdmin = usuario?.rol === "ADMIN";

  // Estado principal de la captura
  const [captura, setCaptura] = useState<CapturaOrdenResponse | null>(null);
  const [configLab, setConfigLab] = useState<ConfiguracionLaboratorio>({
    nombre_laboratorio: "Laboratorio Clínico",
    separador_decimal: ",",
  });
  const [cargando, setCargando] = useState<boolean>(true);
  const [errorGeneral, setErrorGeneral] = useState<string | null>(null);

  // Valores locales en los inputs (código -> valor string)
  const [valoresForm, setValoresForm] = useState<Record<string, string>>({});

  // Valores modificados pendientes de persistir (código -> valor string o null)
  const valoresModificadosRef = useRef<Record<string, string | null>>({});

  // Estado del autoguardado
  const [estadoGuardado, setEstadoGuardado] = useState<
    "inactivo" | "modificado" | "guardando" | "guardado" | "error"
  >("inactivo");
  const [horaUltimoGuardado, setHoraUltimoGuardado] = useState<string | null>(null);
  const [errorGuardadoMensaje, setErrorGuardadoMensaje] = useState<string | null>(null);

  // Referencias a timers para debounce
  const timerCalcularRef = useRef<number | null>(null);
  const timerGuardarRef = useRef<number | null>(null);

  // Cargar configuración de laboratorio y captura inicial
  useEffect(() => {
    let activo = true;

    async function cargarDatos() {
      setCargando(true);
      setErrorGeneral(null);
      try {
        const [respConfig, respCaptura] = await Promise.all([
          getConfiguracionLaboratorioApi().catch(() => ({
            nombre_laboratorio: "Laboratorio Clínico",
            separador_decimal: ",",
          })),
          getCapturaOrdenApi(ordenId),
        ]);

        if (!activo) return;

        setConfigLab(respConfig);
        setCaptura(respCaptura);

        // Inicializar mapa de valores en formulario
        const mapaInicial: Record<string, string> = {};
        respCaptura.estudios.forEach((est) => {
          est.secciones.forEach((sec) => {
            sec.parametros.forEach((p) => {
              if (!p.es_calculado && p.valor !== null) {
                mapaInicial[p.codigo] = p.valor;
              }
            });
          });
        });
        setValoresForm(mapaInicial);
      } catch (err: unknown) {
        if (!activo) return;
        if (err instanceof ApiError) {
          if (err.status === 404) {
            setErrorGeneral("La orden no existe o no tiene permisos para acceder a ella.");
          } else {
            setErrorGeneral(err.message || "Error al cargar la captura de la orden.");
          }
        } else {
          setErrorGeneral("Error inesperado al conectar con el servidor.");
        }
      } finally {
        if (activo) setCargando(false);
      }
    }

    if (ordenId && !isNaN(ordenId)) {
      cargarDatos();
    } else {
      setErrorGeneral("Identificador de orden inválido.");
      setCargando(false);
    }

    return () => {
      activo = false;
      if (timerCalcularRef.current) window.clearTimeout(timerCalcularRef.current);
      if (timerGuardarRef.current) window.clearTimeout(timerGuardarRef.current);
    };
  }, [ordenId]);

  // Manejo de beforeunload: advertir solo si hay cambios sin guardar (§9)
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (Object.keys(valoresModificadosRef.current).length > 0) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, []);

  // Función para disparar cálculo en vivo (POST /calcular)
  const dispararCalculoEnVivo = useCallback(
    async (valoresActuales: Record<string, string>) => {
      if (!captura) return;
      try {
        // Enviar todos los valores ingresados (vacíos = null)
        const payloadValores: Record<string, string | null> = {};
        // Registrar todos los parámetros no calculados del alcance
        captura.estudios.forEach((est) => {
          est.secciones.forEach((sec) => {
            sec.parametros.forEach((p) => {
              if (!p.es_calculado) {
                const val = valoresActuales[p.codigo];
                if (val !== undefined && val.trim() !== "") {
                  payloadValores[p.codigo] = val.trim();
                } else {
                  payloadValores[p.codigo] = null;
                }
              }
            });
          });
        });

        const resp = await calcularResultadosApi(ordenId, payloadValores);
        setCaptura(resp);
      } catch (err) {
        // En vista previa síncrona silenciar errores de conexión menores para no interrumpir digitación
        console.warn("Error en vista previa de cálculo:", err);
      }
    },
    [captura, ordenId]
  );

  // Función para persistir cambios (PUT /resultados)
  const ejecutarGuardado = useCallback(
    async (cambiosPendientes?: Record<string, string | null>) => {
      if (esAdmin) return;
      const cambios = cambiosPendientes || { ...valoresModificadosRef.current };
      if (Object.keys(cambios).length === 0) return;

      setEstadoGuardado("guardando");
      setErrorGuardadoMensaje(null);

      try {
        const resp = await guardarResultadosApi(ordenId, cambios);
        setCaptura(resp);
        // Limpiar cambios persistidos
        Object.keys(cambios).forEach((k) => {
          delete valoresModificadosRef.current[k];
        });

        const ahora = new Date();
        const horaStr = ahora.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
        setHoraUltimoGuardado(horaStr);
        setEstadoGuardado("guardado");
      } catch (err: unknown) {
        setEstadoGuardado("error");
        if (err instanceof ApiError) {
          setErrorGuardadoMensaje(err.message || "Error al persistir resultados.");
        } else {
          setErrorGuardadoMensaje("Error de conexión al guardar resultados.");
        }
      }
    },
    [esAdmin, ordenId]
  );

  // Manejar cambio en un campo de entrada
  const manejarCambioCampo = (codigo: string, nuevoValor: string) => {
    if (esAdmin) return;

    const valoresActualizados = {
      ...valoresForm,
      [codigo]: nuevoValor,
    };
    setValoresForm(valoresActualizados);

    // Marcar como modificado (si está vacío, se envía null para borrar)
    const valorPersistir = nuevoValor.trim() === "" ? null : nuevoValor.trim();
    valoresModificadosRef.current[codigo] = valorPersistir;
    setEstadoGuardado("modificado");

    // 1. Debounce de 400 ms para Vista Previa en Vivo (POST /calcular)
    if (timerCalcularRef.current) window.clearTimeout(timerCalcularRef.current);
    timerCalcularRef.current = window.setTimeout(() => {
      dispararCalculoEnVivo(valoresActualizados);
    }, 400);

    // 2. Debounce de 1500 ms para Autoguardado (PUT /resultados)
    if (timerGuardarRef.current) window.clearTimeout(timerGuardarRef.current);
    timerGuardarRef.current = window.setTimeout(() => {
      ejecutarGuardado();
    }, 1500);
  };

  // Confirmar valores por defecto virtuales (POST /confirmar-defectos)
  const handleConfirmarDefectos = async () => {
    if (esAdmin) return;
    setEstadoGuardado("guardando");
    setErrorGuardadoMensaje(null);
    try {
      const resp = await confirmarDefectosApi(ordenId);
      setCaptura(resp);
      // Actualizar valores en form con los defectos confirmados
      const nuevoMapa = { ...valoresForm };
      resp.estudios.forEach((est) => {
        est.secciones.forEach((sec) => {
          sec.parametros.forEach((p) => {
            if (!p.es_calculado && p.valor !== null) {
              nuevoMapa[p.codigo] = p.valor;
            }
          });
        });
      });
      setValoresForm(nuevoMapa);

      const ahora = new Date();
      setHoraUltimoGuardado(
        ahora.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
      );
      setEstadoGuardado("guardado");
    } catch (err: unknown) {
      setEstadoGuardado("error");
      if (err instanceof ApiError) {
        setErrorGuardadoMensaje(err.message || "Error al confirmar valores por defecto.");
      } else {
        setErrorGuardadoMensaje("Error al confirmar valores por defecto.");
      }
    }
  };

  // Enfocar campo pendiente al hacer clic en el indicador
  const enfocarParametro = (codigo: string) => {
    const el = document.getElementById(`input-${codigo}`);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      el.focus();
    }
  };

  // Formatear valor numérico para la vista según separador decimal configurado
  const formatearValorVisual = (val: string | null): string => {
    if (val === null || val === undefined || val === "") return "—";
    if (configLab.separador_decimal === ",") {
      // Reemplazar punto decimal por coma para visualización
      return val.replace(".", ",");
    }
    return val;
  };

  // Renderizar insignia de bandera (nunca solo color: icono + texto)
  const renderizarBanderaBadge = (bandera: "BAJO" | "NORMAL" | "ALTO" | null) => {
    if (!bandera) return <span className="lis-text-muted">—</span>;
    switch (bandera) {
      case "BAJO":
        return (
          <span className="lis-flag-badge lis-flag-bajo" title="Resultado por debajo del rango de referencia">
            ↓ Bajo
          </span>
        );
      case "ALTO":
        return (
          <span className="lis-flag-badge lis-flag-alto" title="Resultado por encima del rango de referencia">
            ↑ Alto
          </span>
        );
      case "NORMAL":
        return (
          <span className="lis-flag-badge lis-flag-normal" title="Resultado dentro del rango de referencia">
            ✓ Normal
          </span>
        );
      default:
        return null;
    }
  };

  if (cargando) {
    return (
      <div className="lis-page-container">
        <div className="lis-table-loading">
          <div className="lis-spinner" style={{ margin: "0 auto 0.5rem" }} />
          <p>Cargando plantilla analítica de la orden clínica...</p>
        </div>
      </div>
    );
  }

  if (errorGeneral || !captura) {
    return (
      <div className="lis-page-container">
        <div className="lis-alert lis-alert-error" style={{ marginBottom: "1rem" }}>
          {errorGeneral || "No fue posible cargar la información de captura."}
        </div>
        <Link to="/ordenes" className="lis-btn lis-btn-primary">
          ← Volver a Órdenes
        </Link>
      </div>
    );
  }

  const { orden, estudios, completitud } = captura;

  return (
    <div className="lis-page-container" style={{ maxWidth: "1600px" }}>
      {/* Cabecera de la Orden */}
      <div className="lis-patient-header" style={{ marginBottom: "1rem" }}>
        <div>
          <Link
            to={`/ordenes/${orden.id}`}
            className="lis-btn lis-btn-text"
            style={{ paddingLeft: 0, marginBottom: "0.25rem", display: "inline-block" }}
          >
            ← Volver a Detalle de Orden #{orden.id}
          </Link>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" }}>
            <h2>Captura de Resultados — Orden #{orden.id}</h2>
            <span
              className={`lis-status-badge ${
                orden.estado_trabajo === "COMPLETO"
                  ? "lis-status-completo"
                  : orden.estado_trabajo === "PUBLICADA"
                  ? "lis-status-publicada"
                  : "lis-status-incompleto"
              }`}
            >
              {orden.estado_trabajo}
            </span>
            {orden.bloqueada && (
              <span className="lis-status-badge lis-status-bloqueada">
                🔒 Bloqueada por concurrencia
              </span>
            )}
            <span className="lis-chip" style={{ fontSize: "0.8rem" }}>
              Sexo: {orden.paciente.sexo === "M" ? "Masculino" : "Femenino"} ·{" "}
              {orden.edad_anios !== null ? `${orden.edad_anios} años` : "Edad s/d"}
            </span>
          </div>
        </div>

        {/* Indicador de Estado de Autoguardado y Botones Manuales */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" }}>
          {esAdmin ? (
            <div className="lis-alert lis-alert-warning" style={{ padding: "0.4rem 0.85rem", margin: 0, fontSize: "0.85rem" }}>
              🛡️ Modo Supervisión (Solo Lectura) — Acceso auditado ADMIN_VE_PRIVADO
            </div>
          ) : (
            <>
              {/* Estado de guardado visible */}
              <div className="lis-autosave-indicator" style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                {estadoGuardado === "guardando" && (
                  <span style={{ color: "var(--primary)", fontWeight: 600, fontSize: "0.85rem" }}>
                    🔄 Guardando cambios…
                  </span>
                )}
                {estadoGuardado === "guardado" && (
                  <span style={{ color: "var(--success)", fontWeight: 600, fontSize: "0.85rem" }}>
                    ✓ Guardado a las {horaUltimoGuardado}
                  </span>
                )}
                {estadoGuardado === "modificado" && (
                  <span style={{ color: "var(--warning)", fontWeight: 600, fontSize: "0.85rem" }}>
                    🟡 Cambios sin guardar…
                  </span>
                )}
                {estadoGuardado === "error" && (
                  <span style={{ color: "var(--error)", fontWeight: 600, fontSize: "0.85rem" }}>
                    ❌ {errorGuardadoMensaje || "Error al guardar"}
                  </span>
                )}
              </div>

              {/* Botón Guardar Ahora */}
              <button
                type="button"
                className="lis-btn lis-btn-primary lis-btn-sm"
                onClick={() => ejecutarGuardado()}
                disabled={estadoGuardado === "guardando"}
                title="Persistir inmediatamente todos los valores modificados"
              >
                💾 Guardar ahora
              </button>
            </>
          )}
        </div>
      </div>

      {/* Disposición Principal en Dos Columnas: Formulario Izquierda | Vista Previa Derecha */}
      <div className="lis-captura-grid">
        {/* Columna Izquierda: Formulario por Estudio */}
        <div className="lis-captura-form-col">
          {estudios.map((estudio) => (
            <div key={estudio.codigo} className="lis-table-card lis-study-capture-card" style={{ marginBottom: "1.25rem" }}>
              {/* Cabecera del Estudio */}
              <div
                style={{
                  padding: "0.85rem 1.25rem",
                  borderBottom: "1px solid var(--border-color)",
                  backgroundColor: "#f8fafc",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  flexWrap: "wrap",
                  gap: "0.5rem",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                  <span className="lis-chip lis-chip-primary" style={{ fontWeight: 800 }}>
                    {estudio.codigo}
                  </span>
                  <h3 style={{ margin: 0, fontSize: "1.05rem", fontWeight: 700 }}>
                    {estudio.nombre}
                  </h3>
                </div>

                {estudio.grupos_seleccionados && (
                  <div style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                    Grupos pedidos: <strong>{estudio.grupos_seleccionados.join(", ")}</strong>
                  </div>
                )}
              </div>

              {/* Validaciones de Reglas Cruzadas del Estudio */}
              {estudio.validaciones && estudio.validaciones.length > 0 && (
                <div style={{ padding: "0.75rem 1.25rem 0", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                  {estudio.validaciones.map((val, idx) => (
                    <div
                      key={idx}
                      className={`lis-alert ${
                        val.severidad === "ERROR" ? "lis-alert-error" : "lis-alert-warning"
                      }`}
                      style={{ padding: "0.6rem 0.85rem", margin: 0, fontSize: "0.9rem" }}
                    >
                      <strong>{val.severidad === "ERROR" ? "⛔ [Error Clínico]" : "⚠️ [Advertencia Analítica]"}</strong>{" "}
                      {val.mensaje}
                    </div>
                  ))}
                </div>
              )}

              {/* Secciones y Parámetros */}
              <div style={{ padding: "1.25rem" }}>
                {estudio.secciones.map((sec, secIdx) => (
                  <div key={secIdx} style={{ marginBottom: secIdx < estudio.secciones.length - 1 ? "1.5rem" : 0 }}>
                    {/* Título de Grupo si existe */}
                    {sec.grupo && (
                      <h4
                        style={{
                          fontSize: "0.95rem",
                          fontWeight: 700,
                          color: "var(--primary-hover)",
                          borderBottom: "2px solid #e2e8f0",
                          paddingBottom: "0.35rem",
                          marginBottom: "0.85rem",
                          textTransform: "uppercase",
                          letterSpacing: "0.02em",
                        }}
                      >
                        {sec.grupo.replace(/_/g, " ")}
                      </h4>
                    )}

                    {/* Lista de Campos */}
                    <div className="lis-param-fields-grid">
                      {sec.parametros.map((param: ParametroCaptura) => {
                        const valorActual = valoresForm[param.codigo] !== undefined
                          ? valoresForm[param.codigo]
                          : param.valor || "";

                        return (
                          <div
                            key={param.codigo}
                            className={`lis-param-field-box ${param.es_calculado ? "is-calculado" : ""}`}
                          >
                            {/* Cabecera del Campo */}
                            <div className="lis-param-field-header">
                              <label htmlFor={`input-${param.codigo}`} className="lis-param-field-label">
                                {param.nombre}
                                {param.obligatorio && <span style={{ color: "var(--error)", marginLeft: "0.2rem" }}>*</span>}
                              </label>

                              {/* Indicador de valor por defecto virtual */}
                              {param.es_defecto && !param.confirmado && (
                                <span
                                  className="lis-chip lis-chip-warning"
                                  style={{ fontSize: "0.7rem", padding: "0.15rem 0.45rem" }}
                                  title="Valor por defecto virtual: debe confirmarse o editarse"
                                >
                                  Sin confirmar
                                </span>
                              )}

                              {param.es_calculado && (
                                <span
                                  className="lis-chip"
                                  style={{ fontSize: "0.7rem", padding: "0.15rem 0.45rem", backgroundColor: "#e0f2fe", color: "#0369a1" }}
                                >
                                  🧮 Calculado
                                </span>
                              )}
                            </div>

                            {/* Control de Entrada según tipo_campo */}
                            <div className="lis-param-input-wrapper">
                              {param.es_calculado ? (
                                /* Parámetro Calculado: SOLO LECTURA */
                                <div className="lis-param-readonly-display">
                                  {param.calculable && param.valor !== null ? (
                                    <div style={{ display: "flex", alignItems: "baseline", gap: "0.4rem" }}>
                                      <span style={{ fontSize: "1.1rem", fontWeight: 700, color: "var(--text-main)" }}>
                                        {formatearValorVisual(param.valor)}
                                      </span>
                                      {param.unidad && (
                                        <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                                          {param.unidad}
                                        </span>
                                      )}
                                      <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontStyle: "italic" }}>
                                        (estimado)
                                      </span>
                                    </div>
                                  ) : (
                                    <span style={{ color: "#94a3b8", fontStyle: "italic", fontSize: "0.9rem" }}>
                                      No calculable — {param.motivo_no_calculable || "Faltan entradas"}
                                    </span>
                                  )}
                                </div>
                              ) : param.tipo_campo === "SELECCION" ? (
                                /* Desplegable de Selección */
                                <select
                                  id={`input-${param.codigo}`}
                                  value={valorActual}
                                  onChange={(e) => manejarCambioCampo(param.codigo, e.target.value)}
                                  disabled={esAdmin}
                                  className="lis-input"
                                >
                                  <option value="">-- Seleccionar --</option>
                                  {param.opciones?.map((opt) => (
                                    <option key={opt} value={opt}>
                                      {opt}
                                    </option>
                                  ))}
                                </select>
                              ) : param.tipo_campo === "TEXTO" ? (
                                /* Texto libre */
                                <textarea
                                  id={`input-${param.codigo}`}
                                  value={valorActual}
                                  onChange={(e) => manejarCambioCampo(param.codigo, e.target.value)}
                                  disabled={esAdmin}
                                  maxLength={500}
                                  rows={2}
                                  className="lis-input"
                                  placeholder="Observaciones clínicas…"
                                />
                              ) : param.tipo_campo === "FECHA" ? (
                                /* Selector de Fecha */
                                <input
                                  id={`input-${param.codigo}`}
                                  type="date"
                                  value={valorActual}
                                  onChange={(e) => manejarCambioCampo(param.codigo, e.target.value)}
                                  disabled={esAdmin}
                                  className="lis-input"
                                />
                              ) : (
                                /* NUMERICO o RECUENTO (usar text para aceptar coma y punto sin type=number) */
                                <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                                  <input
                                    id={`input-${param.codigo}`}
                                    type="text"
                                    inputMode="decimal"
                                    value={valorActual}
                                    onChange={(e) => manejarCambioCampo(param.codigo, e.target.value)}
                                    disabled={esAdmin}
                                    maxLength={param.tipo_campo === "RECUENTO" ? 50 : 25}
                                    className="lis-input"
                                    placeholder={param.tipo_campo === "NUMERICO" ? "0.00" : ""}
                                    style={{ flex: 1 }}
                                  />
                                  {param.unidad && (
                                    <span
                                      style={{
                                        fontSize: "0.85rem",
                                        fontWeight: 600,
                                        color: "var(--text-muted)",
                                        minWidth: "38px",
                                      }}
                                    >
                                      {param.unidad}
                                    </span>
                                  )}
                                </div>
                              )}
                            </div>

                            {/* Información de Referencia y Bandera en el Campo */}
                            <div className="lis-param-field-footer">
                              <span style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>
                                Ref: {param.referencia?.texto || "No aplica"}
                              </span>
                              <div>{renderizarBanderaBadge(param.bandera)}</div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Columna Derecha: Panel Fijo de Vista Previa en Vivo y Completitud */}
        <div className="lis-captura-preview-col">
          <div className="lis-table-card lis-sticky-preview-panel">
            {/* Cabecera del Panel */}
            <div
              style={{
                padding: "1rem 1.25rem",
                borderBottom: "1px solid var(--border-color)",
                backgroundColor: "#f8fafc",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <div>
                <h3 style={{ margin: 0, fontSize: "1.05rem", fontWeight: 700 }}>
                  📋 Vista Previa en Vivo
                </h3>
                <span style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>
                  Recálculo síncrono en servidor ({configLab.nombre_laboratorio})
                </span>
              </div>

              {!esAdmin && completitud.sin_confirmar.length > 0 && (
                <button
                  type="button"
                  className="lis-btn lis-btn-outline lis-btn-sm"
                  onClick={handleConfirmarDefectos}
                  title="Confirmar todos los valores por defecto virtuales"
                >
                  Confirmar defectos ({completitud.sin_confirmar.length})
                </button>
              )}
            </div>

            {/* Tarjeta de Estado de Completitud (§9) */}
            <div style={{ padding: "1rem 1.25rem", borderBottom: "1px solid var(--border-color)" }}>
              {completitud.completo ? (
                <div className="lis-alert lis-alert-success" style={{ margin: 0 }}>
                  <strong>✓ Orden COMPLETA</strong>
                  <p style={{ margin: "0.2rem 0 0", fontSize: "0.85rem" }}>
                    Todos los parámetros obligatorios del alcance se encuentran resueltos satisfactoriamente.
                  </p>
                </div>
              ) : (
                <div className="lis-alert lis-alert-warning" style={{ margin: 0 }}>
                  <strong>
                    ⚠️ Faltan {completitud.pendientes.length} campo(s) obligatorio(s)
                  </strong>

                  {completitud.pendientes.length > 0 && (
                    <div style={{ marginTop: "0.5rem" }}>
                      <span style={{ fontSize: "0.78rem", fontWeight: 700, display: "block", marginBottom: "0.25rem" }}>
                        Pendientes (haga clic para enfocar):
                      </span>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.35rem" }}>
                        {completitud.pendientes.map((cod) => (
                          <button
                            key={cod}
                            type="button"
                            onClick={() => enfocarParametro(cod)}
                            className="lis-chip lis-chip-pending"
                            title={`Ir al parámetro ${cod}`}
                          >
                            {cod}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {completitud.sin_confirmar.length > 0 && (
                    <div style={{ marginTop: "0.5rem", fontSize: "0.82rem", color: "#854d0e" }}>
                      • {completitud.sin_confirmar.length} valores por defecto pendientes de confirmación.
                    </div>
                  )}

                  {completitud.errores.length > 0 && (
                    <div style={{ marginTop: "0.5rem", fontSize: "0.82rem", color: "var(--error)" }}>
                      <strong>Errores analíticos que impiden completar:</strong>
                      <ul style={{ margin: "0.25rem 0 0 1.25rem" }}>
                        {completitud.errores.map((err, eIdx) => (
                          <li key={eIdx}>{err}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Tabla Resumen Parámetro · Resultado · Unidad · Referencia · Bandera */}
            <div style={{ padding: "0.5rem 0", maxHeight: "calc(100vh - 340px)", overflowY: "auto" }}>
              <table className="lis-table lis-preview-table" style={{ fontSize: "0.85rem" }}>
                <thead>
                  <tr>
                    <th>Parámetro</th>
                    <th>Resultado</th>
                    <th>Unidad</th>
                    <th>Referencia</th>
                    <th>Bandera</th>
                  </tr>
                </thead>
                <tbody>
                  {estudios.flatMap((est) =>
                    est.secciones.flatMap((sec) =>
                      sec.parametros.map((p) => {
                        const valDisplay = p.es_calculado
                          ? p.calculable && p.valor !== null
                            ? `${formatearValorVisual(p.valor)} (est)`
                            : "No calculable"
                          : formatearValorVisual(p.valor);

                        return (
                          <tr
                            key={p.codigo}
                            className={
                              p.bandera === "ALTO"
                                ? "row-flag-alto"
                                : p.bandera === "BAJO"
                                ? "row-flag-bajo"
                                : ""
                            }
                          >
                            <td>
                              <span style={{ fontWeight: 600 }}>{p.nombre}</span>
                              <span
                                style={{
                                  display: "block",
                                  fontSize: "0.72rem",
                                  color: "var(--text-muted)",
                                }}
                              >
                                {p.codigo}
                              </span>
                            </td>
                            <td style={{ fontWeight: 700 }}>{valDisplay}</td>
                            <td style={{ color: "var(--text-muted)" }}>{p.unidad || "—"}</td>
                            <td style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                              {p.referencia?.texto || "—"}
                            </td>
                            <td>{renderizarBanderaBadge(p.bandera)}</td>
                          </tr>
                        );
                      })
                    )
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
export default CapturaResultadosPage;
