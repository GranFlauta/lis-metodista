/**
 * Pantalla de Captura de Resultados Clínicos, Cálculo en Vivo y Banderas.
 * Implementa PROMPT_FASE_3_6_UX.md §6.5 y docs/UX_GUIDE.md (§3 y §4):
 * - Ruta /ordenes/:id/captura, ancho completo (sin max-width).
 * - Barra fija superior: paciente, CI, edad, hora de inicio, indicador Completo / Faltan N,
 *   guardado con aria-live, botones Guardar ahora y Confirmar valores por defecto.
 * - Izquierda (≈ 55 %): hoja de captura con bloques de estudio (Hemograma N/M) y filas de 28-32 px.
 *   En pantallas anchas se disponen en columnas (mínimo 420 px).
 * - Fidelidad al Excel: en grupo DIFERENCIAL, una fila por leucocito con dos celdas (% editable y mm3 calculado)
 *   emparejadas por prefijo *_PCT / *_ABS.
 * - Teclado: Enter y Tab pasan al siguiente campo editable; Enter nunca envía formularios.
 * - Derecha (≈ 45 %): vista previa grande con membrete, paciente, tablas de estudio (fuente >= 14 px),
 *   scroll propio y botón de pantalla completa.
 * - Banderas fieles a UX_GUIDE.md §4: ▲ Alto, ▼ Bajo, Normal, Sin confirmar.
 * - Sin emojis, sin textos de desarrollo, sin almacenamiento en navegador.
 */

import React, { useEffect, useState, useRef, useCallback } from "react";
import { useParams, Link, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";
import {
  getCapturaOrdenApi,
  calcularResultadosApi,
  guardarResultadosApi,
  confirmarDefectosApi,
  getConfiguracionLaboratorioApi,
  CapturaOrdenResponse,
  EstudioCaptura,
  SeccionCaptura,
  ParametroCaptura,
  ConfiguracionLaboratorio,
} from "../../api/resultados";
import {
  obtenerOrdenApi,
  OrdenDetalle,
  AdvertenciaSolapamiento,
} from "../../api/ordenes";
import { ApiError } from "../../api/client";

export const CapturaResultadosPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const ordenId = Number(id);
  const location = useLocation();
  const advertenciasSolapamiento = (location.state as { advertencias?: AdvertenciaSolapamiento[] } | null)?.advertencias;

  const { usuario } = useAuth();
  const esAdmin = usuario?.rol === "ADMIN";

  // Estados de datos
  const [captura, setCaptura] = useState<CapturaOrdenResponse | null>(null);
  const [ordenDetalle, setOrdenDetalle] = useState<OrdenDetalle | null>(null);
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

  // Desplegable de pendientes en barra superior y pantalla completa de vista previa
  const [mostrarMenuPendientes, setMostrarMenuPendientes] = useState<boolean>(false);
  const [vistaPreviaFullscreen, setVistaPreviaFullscreen] = useState<boolean>(false);

  // Referencias a timers para debounce
  const timerCalcularRef = useRef<number | null>(null);
  const timerGuardarRef = useRef<number | null>(null);

  // Cargar datos iniciales
  useEffect(() => {
    let activo = true;

    async function cargarDatos() {
      setCargando(true);
      setErrorGeneral(null);
      try {
        const [respConfig, respCaptura, respDetalle] = await Promise.all([
          getConfiguracionLaboratorioApi().catch(() => ({
            nombre_laboratorio: "Laboratorio Clínico",
            separador_decimal: ",",
          })),
          getCapturaOrdenApi(ordenId),
          obtenerOrdenApi(ordenId).catch(() => null),
        ]);

        if (!activo) return;

        setConfigLab(respConfig);
        setCaptura(respCaptura);
        setOrdenDetalle(respDetalle);

        // Inicializar mapa de valores en formulario
        const mapaInicial: Record<string, string> = {};
        respCaptura.estudios.forEach((est: EstudioCaptura) => {
          est.secciones.forEach((sec: SeccionCaptura) => {
            sec.parametros.forEach((p: ParametroCaptura) => {
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

  // Foco inicial en el primer campo editable al cargar
  useEffect(() => {
    if (!cargando && captura && !esAdmin) {
      const timer = window.setTimeout(() => {
        const primerInput = document.querySelector<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>(
          ".lis-captura-input:not([disabled])"
        );
        if (primerInput) {
          primerInput.focus();
        }
      }, 100);
      return () => window.clearTimeout(timer);
    }
  }, [cargando, captura, esAdmin]);

  // Manejo de beforeunload: advertir solo si hay cambios sin guardar
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

  // Escape para salir de pantalla completa de vista previa
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && vistaPreviaFullscreen) {
        setVistaPreviaFullscreen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [vistaPreviaFullscreen]);

  // Disparar cálculo en vivo (POST /calcular con debounce 400ms)
  const dispararCalculoEnVivo = useCallback(
    async (valoresActuales: Record<string, string>) => {
      if (!captura) return;
      try {
        const payloadValores: Record<string, string | null> = {};
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
        console.warn("Error en vista previa de cálculo síncrono:", err);
      }
    },
    [captura, ordenId]
  );

  // Persistir cambios (PUT /resultados con autoguardado 1500ms o botón Guardar ahora)
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
        Object.keys(cambios).forEach((k) => {
          delete valoresModificadosRef.current[k];
        });

        const ahora = new Date();
        const horaStr = ahora.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
        setHoraUltimoGuardado(horaStr);
        setEstadoGuardado("guardado");
      } catch (err: unknown) {
        setEstadoGuardado("error");
        if (err instanceof ApiError) {
          setErrorGuardadoMensaje(err.message || "Error al persistir resultados.");
        } else {
          setErrorGuardadoMensaje("Error de conexión al guardar.");
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

    const valorPersistir = nuevoValor.trim() === "" ? null : nuevoValor.trim();
    valoresModificadosRef.current[codigo] = valorPersistir;
    setEstadoGuardado("modificado");

    // 1. Debounce 400 ms para Vista Previa en Vivo (POST /calcular)
    if (timerCalcularRef.current) window.clearTimeout(timerCalcularRef.current);
    timerCalcularRef.current = window.setTimeout(() => {
      dispararCalculoEnVivo(valoresActualizados);
    }, 400);

    // 2. Debounce 1500 ms para Autoguardado (PUT /resultados)
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
      setHoraUltimoGuardado(ahora.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
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

  // Navegación con teclado tipo Excel: Enter y Tab pasan al siguiente campo editable; Enter nunca envía
  const manejarKeyDownInput = (e: React.KeyboardEvent<HTMLElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      const todosInputs = Array.from(
        document.querySelectorAll<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>(
          ".lis-captura-input:not([disabled])"
        )
      );
      const idx = todosInputs.indexOf(e.currentTarget as any);
      if (idx >= 0) {
        if (e.shiftKey) {
          const prev = todosInputs[idx - 1];
          if (prev) {
            prev.focus();
            if (prev instanceof HTMLInputElement) prev.select();
          }
        } else {
          const next = todosInputs[idx + 1];
          if (next) {
            next.focus();
            if (next instanceof HTMLInputElement) next.select();
          }
        }
      }
    }
  };

  // Enfocar campo pendiente al hacer clic
  const enfocarParametro = (codigo: string) => {
    setMostrarMenuPendientes(false);
    const el = document.getElementById(`input-${codigo}`);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      el.focus();
      if (el instanceof HTMLInputElement) el.select();
    }
  };

  // Formatear valor numérico para la visualización
  const formatearValorVisual = (val: string | null | undefined): string => {
    if (val === null || val === undefined || val === "") return "—";
    if (configLab.separador_decimal === ",") {
      return val.replace(".", ",");
    }
    return val;
  };

  // Renderizar insignia de bandera (UX_GUIDE.md §4: ▲ Alto, ▼ Bajo, Normal, Sin confirmar)
  const renderizarBanderaBadge = (
    bandera: "BAJO" | "NORMAL" | "ALTO" | null,
    esDefectoSinConfirmar?: boolean
  ) => {
    if (esDefectoSinConfirmar) {
      return (
        <span className="lis-flag-badge lis-flag-sin-confirmar" title="Valor por defecto virtual sin confirmar">
          Sin confirmar
        </span>
      );
    }
    if (!bandera) return <span style={{ color: "var(--text-muted)", fontSize: "11px" }}>—</span>;
    switch (bandera) {
      case "ALTO":
        return (
          <span className="lis-flag-badge lis-flag-alto" title="Resultado por encima del rango de referencia">
            ▲ Alto
          </span>
        );
      case "BAJO":
        return (
          <span className="lis-flag-badge lis-flag-bajo" title="Resultado por debajo del rango de referencia">
            ▼ Bajo
          </span>
        );
      case "NORMAL":
        return (
          <span className="lis-flag-badge lis-flag-normal" title="Resultado dentro del rango de referencia">
            Normal
          </span>
        );
      default:
        return null;
    }
  };

  // Conteo de completitud por estudio fiel a las filas del Excel (ej. Hemograma 9/12)
  const calcularConteoEstudio = (estudio: EstudioCaptura) => {
    let total = 0;
    let completos = 0;
    estudio.secciones.forEach((sec) => {
      sec.parametros.forEach((p) => {
        // En grupo DIFERENCIAL, *_ABS se calcula y muestra en la misma fila del *_PCT
        if (sec.grupo === "DIFERENCIAL" && p.codigo.endsWith("_ABS")) return;

        const v = valoresForm[p.codigo] !== undefined ? valoresForm[p.codigo] : p.valor;
        const estaLleno = p.es_calculado
          ? (p.calculable && p.valor !== null)
          : (v !== null && v !== undefined && v.trim() !== "");

        if (p.obligatorio) {
          total += 1;
          if (estaLleno) completos += 1;
        } else if (estaLleno) {
          total += 1;
          completos += 1;
        }
      });
    });
    return { completos, total };
  };

  if (cargando) {
    return (
      <div className="lis-page-container">
        <div className="lis-table-loading">
          <div className="lis-spinner" style={{ margin: "0 auto 0.5rem" }} />
          <p>Cargando plantilla analítica de la orden clínica…</p>
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

  // Datos del paciente y orden formateados
  const nombrePaciente = ordenDetalle
    ? `${ordenDetalle.paciente.nombres} ${ordenDetalle.paciente.apellido_paterno} ${ordenDetalle.paciente.apellido_materno || ""}`.trim()
    : `Paciente #${orden.paciente?.id || orden.id}`;

  const ciPaciente = ordenDetalle?.paciente.ci
    ? `${ordenDetalle.paciente.ci}${ordenDetalle.paciente.ci_complemento ? "-" + ordenDetalle.paciente.ci_complemento : ""}`
    : "Sin CI";

  const edadStr = ordenDetalle?.edad_anios !== null && ordenDetalle?.edad_anios !== undefined
    ? `${ordenDetalle.edad_anios} años`
    : orden.edad_anios !== null
    ? `${orden.edad_anios} años`
    : "Edad s/d";

  const horaInicioRaw = ordenDetalle?.fecha_hora_toma_muestra || ordenDetalle?.creado_en;
  const horaInicioStr = horaInicioRaw
    ? new Date(horaInicioRaw).toLocaleString([], {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "Sin registro de hora";

  // Renderizar fila doble de diferencial (% editable y mm3 calculado)
  const renderizarFilaDiferencial = (pctParam: ParametroCaptura, absParam?: ParametroCaptura) => {
    const valorPctActual = valoresForm[pctParam.codigo] !== undefined
      ? valoresForm[pctParam.codigo]
      : pctParam.valor || "";

    const absCalculable = absParam?.calculable && absParam?.valor !== null;
    const absValorStr = absCalculable ? formatearValorVisual(absParam.valor) : "—";

    return (
      <tr key={pctParam.codigo}>
        <td>
          <span style={{ fontWeight: 600 }}>{pctParam.nombre}</span>
          {pctParam.obligatorio && <span style={{ color: "var(--error)", marginLeft: "2px" }}>*</span>}
        </td>
        <td>
          <div className="lis-diferencial-cell">
            <input
              id={`input-${pctParam.codigo}`}
              type="text"
              inputMode="decimal"
              className="lis-captura-input is-numeric is-diferencial-pct"
              value={valorPctActual}
              onChange={(e) => manejarCambioCampo(pctParam.codigo, e.target.value)}
              onKeyDown={manejarKeyDownInput}
              onFocus={(e) => e.target.select()}
              disabled={esAdmin}
              placeholder="0"
              title={`${pctParam.nombre} (%)`}
            />
            <span style={{ fontSize: "11px", color: "var(--text-muted)", width: "12px" }}>%</span>
            <span
              className="lis-captura-calc-box is-diferencial-abs"
              title={absParam ? `${absParam.nombre}: ${absValorStr} mm3` : ""}
            >
              {absValorStr}
            </span>
            <span style={{ fontSize: "11px", color: "var(--text-muted)", width: "24px" }}>mm3</span>
          </div>
        </td>
        <td style={{ fontSize: "12px", color: "var(--text-muted)" }}>% / mm3</td>
        <td style={{ fontSize: "11.5px", color: "var(--text-muted)" }}>
          {pctParam.referencia?.texto || "—"}
        </td>
        <td>{renderizarBanderaBadge(pctParam.bandera, pctParam.es_defecto && !pctParam.confirmado)}</td>
      </tr>
    );
  };

  // Renderizar fila estándar de parámetro
  const renderizarFilaParametro = (param: ParametroCaptura) => {
    const valorActual = valoresForm[param.codigo] !== undefined
      ? valoresForm[param.codigo]
      : param.valor || "";

    return (
      <tr key={param.codigo}>
        <td>
          <span style={{ fontWeight: 600 }}>{param.nombre}</span>
          {param.obligatorio && <span style={{ color: "var(--error)", marginLeft: "2px" }}>*</span>}
        </td>
        <td>
          {param.es_calculado ? (
            <div style={{ textAlign: "right" }}>
              {param.calculable && param.valor !== null ? (
                <span className="lis-captura-calc-box" style={{ minWidth: "75px" }}>
                  {formatearValorVisual(param.valor)}
                </span>
              ) : (
                <span
                  style={{ color: "#94a3b8", fontStyle: "italic", fontSize: "11.5px" }}
                  title={param.motivo_no_calculable || "Faltan entradas"}
                >
                  No calculable
                </span>
              )}
            </div>
          ) : param.tipo_campo === "SELECCION" ? (
            <select
              id={`input-${param.codigo}`}
              className="lis-captura-input"
              value={valorActual}
              onChange={(e) => manejarCambioCampo(param.codigo, e.target.value)}
              onKeyDown={manejarKeyDownInput}
              disabled={esAdmin}
            >
              <option value="">--</option>
              {param.opciones?.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
          ) : param.tipo_campo === "TEXTO" ? (
            <input
              id={`input-${param.codigo}`}
              type="text"
              className="lis-captura-input"
              value={valorActual}
              onChange={(e) => manejarCambioCampo(param.codigo, e.target.value)}
              onKeyDown={manejarKeyDownInput}
              onFocus={(e) => e.target.select()}
              disabled={esAdmin}
              maxLength={500}
              placeholder="Observación…"
            />
          ) : param.tipo_campo === "FECHA" ? (
            <input
              id={`input-${param.codigo}`}
              type="date"
              className="lis-captura-input"
              value={valorActual}
              onChange={(e) => manejarCambioCampo(param.codigo, e.target.value)}
              onKeyDown={manejarKeyDownInput}
              disabled={esAdmin}
            />
          ) : (
            <input
              id={`input-${param.codigo}`}
              type="text"
              inputMode="decimal"
              className="lis-captura-input is-numeric"
              value={valorActual}
              onChange={(e) => manejarCambioCampo(param.codigo, e.target.value)}
              onKeyDown={manejarKeyDownInput}
              onFocus={(e) => e.target.select()}
              disabled={esAdmin}
              maxLength={param.tipo_campo === "RECUENTO" ? 50 : 25}
              placeholder={param.tipo_campo === "NUMERICO" ? "0" : ""}
            />
          )}
        </td>
        <td style={{ fontSize: "12px", color: "var(--text-muted)" }}>{param.unidad || "—"}</td>
        <td style={{ fontSize: "11.5px", color: "var(--text-muted)" }}>
          {param.referencia?.texto || "—"}
        </td>
        <td>{renderizarBanderaBadge(param.bandera, param.es_defecto && !param.confirmado)}</td>
      </tr>
    );
  };

  // Renderizar sección de parámetros (agrupación analítica)
  const renderizarSeccion = (sec: SeccionCaptura) => {
    const esDiferencial = sec.grupo === "DIFERENCIAL";

    return (
      <div key={sec.grupo || "general"} style={{ marginBottom: "6px" }}>
        {sec.grupo && (
          <div
            style={{
              fontSize: "11px",
              fontWeight: 700,
              color: "var(--text-muted)",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              padding: "2px 6px",
              backgroundColor: "#f8fafc",
              borderLeft: "3px solid var(--primary)",
              marginBottom: "2px",
            }}
          >
            {sec.grupo.replace(/_/g, " ")}
          </div>
        )}
        <table className="lis-captura-tabla">
          <thead>
            <tr>
              <th style={{ width: esDiferencial ? "30%" : "32%" }}>Parámetro</th>
              <th style={{ width: esDiferencial ? "36%" : "28%", textAlign: "right" }}>Resultado</th>
              <th style={{ width: esDiferencial ? "14%" : "12%" }}>Unidad</th>
              <th style={{ width: esDiferencial ? "10%" : "16%" }}>V. Ref.</th>
              <th style={{ width: esDiferencial ? "10%" : "12%" }}>Bandera</th>
            </tr>
          </thead>
          <tbody>
            {sec.parametros.map((param) => {
              if (esDiferencial && param.codigo.endsWith("_ABS")) {
                return null;
              }

              if (esDiferencial && param.codigo.endsWith("_PCT")) {
                const prefix = param.codigo.replace(/_PCT$/, "");
                const absParam = sec.parametros.find((p) => p.codigo === `${prefix}_ABS`);
                return renderizarFilaDiferencial(param, absParam);
              }

              return renderizarFilaParametro(param);
            })}
          </tbody>
        </table>
      </div>
    );
  };

  return (
    <div className="lis-captura-page">
      {/* Barra Fija Superior (§6.5) */}
      <div className="lis-captura-top-bar">
        <div className="lis-captura-top-info">
          <Link to={`/ordenes/${orden.id}`} className="lis-btn lis-btn-text" style={{ padding: "0 4px" }}>
            ← Volver #{orden.id}
          </Link>
          <strong style={{ fontSize: "14.5px", color: "var(--text-main)" }}>
            {nombrePaciente}
          </strong>
          <span className="lis-chip" style={{ fontSize: "12px", padding: "1px 6px" }}>
            CI: {ciPaciente}
          </span>
          <span className="lis-chip" style={{ fontSize: "12px", padding: "1px 6px" }}>
            {edadStr}
          </span>
          <span className="lis-chip" style={{ fontSize: "12px", padding: "1px 6px" }} title="Hora de inicio o toma de muestra">
            Inicio: {horaInicioStr}
          </span>

          {/* Indicador de Completitud interactivo */}
          <div style={{ position: "relative", display: "inline-block" }}>
            {completitud.completo ? (
              <span className="lis-status-badge lis-status-completo" style={{ fontSize: "12px" }}>
                ✓ Completo
              </span>
            ) : (
              <button
                type="button"
                className="lis-status-badge lis-status-incompleto"
                style={{ fontSize: "12px", cursor: "pointer", border: "none" }}
                onClick={() => setMostrarMenuPendientes((prev) => !prev)}
                title="Haga clic para ver los parámetros pendientes"
              >
                Faltan {completitud.pendientes.length}
              </button>
            )}

            {/* Menú flotante de pendientes */}
            {mostrarMenuPendientes && !completitud.completo && (
              <div
                style={{
                  position: "absolute",
                  top: "100%",
                  left: 0,
                  marginTop: "4px",
                  backgroundColor: "#ffffff",
                  border: "1px solid var(--border-color)",
                  borderRadius: "var(--radius)",
                  boxShadow: "0 4px 6px rgba(0, 0, 0, 0.1)",
                  padding: "8px",
                  zIndex: 100,
                  minWidth: "220px",
                }}
              >
                <div style={{ fontSize: "11.5px", fontWeight: 700, marginBottom: "4px", color: "var(--text-muted)" }}>
                  Parámetros pendientes (clic para ir):
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
                  {completitud.pendientes.map((cod) => (
                    <button
                      key={cod}
                      type="button"
                      className="lis-chip lis-chip-pending"
                      style={{ cursor: "pointer", fontSize: "11px" }}
                      onClick={() => enfocarParametro(cod)}
                    >
                      {cod}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Estados de guardado y botones */}
        <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
          {esAdmin ? (
            <div className="lis-alert lis-alert-warning" style={{ padding: "3px 8px", margin: 0, fontSize: "12px" }}>
              Modo Supervisión (Solo Lectura) — Acceso auditado ADMIN_VE_PRIVADO
            </div>
          ) : (
            <>
              {/* Indicador de estado de autoguardado con aria-live */}
              <div
                aria-live="polite"
                className="lis-autosave-indicator"
                style={{ fontSize: "12.5px", fontWeight: 600 }}
              >
                {estadoGuardado === "guardando" && (
                  <span style={{ color: "var(--primary)" }}>Guardando…</span>
                )}
                {estadoGuardado === "guardado" && (
                  <span style={{ color: "var(--success)" }}>Guardado a las {horaUltimoGuardado}</span>
                )}
                {estadoGuardado === "modificado" && (
                  <span style={{ color: "var(--warning)" }}>Cambios sin guardar…</span>
                )}
                {estadoGuardado === "error" && (
                  <span style={{ color: "var(--error)" }} title={errorGuardadoMensaje || ""}>
                    Error — reintentar
                  </span>
                )}
              </div>

              {/* Confirmar defectos si existen */}
              {completitud.sin_confirmar.length > 0 && (
                <button
                  type="button"
                  className="lis-btn lis-btn-outline lis-btn-sm"
                  onClick={handleConfirmarDefectos}
                  title="Confirmar todos los valores por defecto virtuales"
                >
                  Confirmar valores por defecto ({completitud.sin_confirmar.length})
                </button>
              )}

              {/* Botón Guardar ahora */}
              <button
                type="button"
                className="lis-btn lis-btn-primary lis-btn-sm"
                onClick={() => ejecutarGuardado()}
                disabled={estadoGuardado === "guardando"}
                title="Persistir inmediatamente todos los valores modificados"
              >
                Guardar ahora
              </button>
            </>
          )}
        </div>
      </div>

      {/* Banner Superior de Advertencias de Solapamiento si existen */}
      {advertenciasSolapamiento && advertenciasSolapamiento.length > 0 && (
        <div
          className="lis-alert lis-alert-warning"
          style={{ marginBottom: "8px", padding: "6px 12px", fontSize: "13px" }}
        >
          <strong>Advertencia de solapamiento de órdenes activas:</strong>
          <ul style={{ margin: "2px 0 0 16px" }}>
            {advertenciasSolapamiento.map((adv, idx) => (
              <li key={idx}>
                Estudios compartidos: <strong>{adv.estudios.join(", ")}</strong> — Autor de la otra orden:{" "}
                {adv.autor ? `${adv.autor.nombres} ${adv.autor.apellido_paterno}` : "Bioquímico registrado"}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Disposición Principal en Dos Columnas: Izquierda (≈ 55 %) | Derecha (≈ 45 %) */}
      <form
        onSubmit={(e) => e.preventDefault()}
        onKeyDown={(e) => {
          if (e.key === "Enter") e.preventDefault();
        }}
      >
        <div className="lis-captura-layout">
          {/* Izquierda (≈ 55 %) — Hoja de Captura Fiel al Excel */}
          <div className="lis-captura-hoja">
            <div className="lis-captura-hoja-grid">
              {estudios.map((estudio) => {
                const conteo = calcularConteoEstudio(estudio);
                return (
                  <div key={estudio.codigo} className="lis-captura-estudio-box">
                    {/* Encabezado del estudio (ej. Hemograma 9/12) */}
                    <div className="lis-captura-estudio-header">
                      <span>{estudio.nombre}</span>
                      <span className="lis-chip" style={{ fontSize: "11px", padding: "1px 6px" }}>
                        {conteo.completos}/{conteo.total}
                      </span>
                    </div>

                    {/* Validaciones de reglas cruzadas del estudio si aplican */}
                    {estudio.validaciones && estudio.validaciones.length > 0 && (
                      <div style={{ padding: "4px 8px", display: "flex", flexDirection: "column", gap: "4px" }}>
                        {estudio.validaciones.map((val, idx) => (
                          <div
                            key={idx}
                            className={`lis-alert ${
                              val.severidad === "ERROR" ? "lis-alert-error" : "lis-alert-warning"
                            }`}
                            style={{ padding: "4px 8px", margin: 0, fontSize: "12px" }}
                          >
                            <strong>{val.severidad === "ERROR" ? "[Error]" : "[Advertencia]"}</strong> {val.mensaje}
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Secciones y tabla del estudio */}
                    <div style={{ padding: "6px" }}>
                      {estudio.secciones.map((sec) => renderizarSeccion(sec))}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Derecha (≈ 45 %) — Vista Previa Grande con scroll propio */}
          <div className="lis-captura-vista-previa">
            <div className={`lis-vista-previa-sheet ${vistaPreviaFullscreen ? "is-fullscreen" : ""}`}>
              {/* Barra superior de la vista previa */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  borderBottom: "1px solid var(--border-light)",
                  paddingBottom: "6px",
                }}
              >
                <span style={{ fontSize: "12px", color: "var(--text-muted)", fontStyle: "italic" }}>
                  Vista previa — no es el informe oficial
                </span>
                <button
                  type="button"
                  className="lis-btn lis-btn-secondary lis-btn-sm"
                  onClick={() => setVistaPreviaFullscreen((prev) => !prev)}
                  title={
                    vistaPreviaFullscreen
                      ? "Cerrar pantalla completa (Esc)"
                      : "Ver vista previa en pantalla completa"
                  }
                >
                  {vistaPreviaFullscreen ? "Cerrar pantalla completa" : "Pantalla completa"}
                </button>
              </div>

              {/* Membrete del laboratorio */}
              <div className="lis-preview-lab-header">
                <h2 className="lis-preview-lab-title">{configLab.nombre_laboratorio}</h2>
                <div className="lis-preview-lab-sub">Informe de Análisis Clínicos</div>
              </div>

              {/* Bloque del paciente */}
              <div className="lis-preview-patient-grid">
                <div>
                  <span style={{ fontSize: "11.5px", color: "var(--text-muted)", display: "block" }}>Paciente:</span>
                  <strong>{nombrePaciente}</strong>
                </div>
                <div>
                  <span style={{ fontSize: "11.5px", color: "var(--text-muted)", display: "block" }}>C.I.:</span>
                  <strong>{ciPaciente}</strong>
                </div>
                <div>
                  <span style={{ fontSize: "11.5px", color: "var(--text-muted)", display: "block" }}>Edad / Sexo:</span>
                  <strong>
                    {edadStr} · {orden.paciente?.sexo === "M" ? "Masculino" : "Femenino"}
                  </strong>
                </div>
                <div>
                  <span style={{ fontSize: "11.5px", color: "var(--text-muted)", display: "block" }}>Inicio de orden:</span>
                  <span>{horaInicioStr}</span>
                </div>
                <div>
                  <span style={{ fontSize: "11.5px", color: "var(--text-muted)", display: "block" }}>Médico:</span>
                  <span>{ordenDetalle?.medico_solicitante || "No especificado"}</span>
                </div>
                <div>
                  <span style={{ fontSize: "11.5px", color: "var(--text-muted)", display: "block" }}>Origen:</span>
                  <span>{ordenDetalle?.origen_solicitud || "General"}</span>
                </div>
              </div>

              {/* Tablas por estudio con fuente >= 14 px */}
              {estudios.map((estudio) => (
                <div
                  key={estudio.codigo}
                  style={{
                    border: "1px solid var(--border-light)",
                    borderRadius: "var(--radius)",
                    padding: "8px",
                  }}
                >
                  <h4
                    style={{
                      margin: "0 0 6px 0",
                      fontSize: "14.5px",
                      fontWeight: 700,
                      color: "var(--primary-hover)",
                      borderBottom: "1px solid var(--border-light)",
                      paddingBottom: "4px",
                    }}
                  >
                    {estudio.nombre}
                  </h4>
                  <table className="lis-preview-study-table">
                    <thead>
                      <tr>
                        <th style={{ width: "32%" }}>Parámetro</th>
                        <th style={{ width: "24%", textAlign: "right" }}>Resultado</th>
                        <th style={{ width: "14%" }}>Unidad</th>
                        <th style={{ width: "18%" }}>Valores de referencia</th>
                        <th style={{ width: "12%" }}>Bandera</th>
                      </tr>
                    </thead>
                    <tbody>
                      {estudio.secciones.flatMap((sec) =>
                        sec.parametros.map((p) => {
                          let valorTexto = "—";
                          if (p.es_calculado) {
                            if (p.calculable && p.valor !== null) {
                              valorTexto = formatearValorVisual(p.valor);
                            } else {
                              valorTexto = `No calculable — ${p.motivo_no_calculable || "Faltan entradas"}`;
                            }
                          } else if (p.valor !== null && p.valor !== undefined && p.valor !== "") {
                            valorTexto = formatearValorVisual(p.valor);
                          }

                          return (
                            <tr key={p.codigo}>
                              <td>
                                <span style={{ fontWeight: 600 }}>{p.nombre}</span>
                              </td>
                              <td style={{ textAlign: "right", fontWeight: 700 }}>
                                {valorTexto}
                              </td>
                              <td style={{ color: "var(--text-muted)" }}>{p.unidad || "—"}</td>
                              <td style={{ color: "var(--text-muted)", fontSize: "13px" }}>
                                {p.referencia?.texto || "—"}
                              </td>
                              <td>{renderizarBanderaBadge(p.bandera, p.es_defecto && !p.confirmado)}</td>
                            </tr>
                          );
                        })
                      )}
                    </tbody>
                  </table>
                </div>
              ))}

              <div
                style={{
                  textAlign: "center",
                  marginTop: "8px",
                  borderTop: "1px solid var(--border-light)",
                  paddingTop: "6px",
                }}
              >
                <span style={{ fontSize: "12px", color: "var(--text-muted)", fontStyle: "italic" }}>
                  Vista previa — no es el informe oficial
                </span>
              </div>
            </div>
          </div>
        </div>
      </form>
    </div>
  );
};

export default CapturaResultadosPage;
