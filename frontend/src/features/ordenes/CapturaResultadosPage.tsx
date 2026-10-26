/**
 * Pantalla de Captura de Resultados Clínicos, Modo Enfocado y Paginador de Estudios.
 * Refactor de diseño fiel al Excel (docs/UX_GUIDE.md §3 y §4):
 * - Modo enfocado: muestra ÚNICAMENTE el formulario del estudio activo en la columna izquierda.
 * - Columna derecha: Vista previa en tiempo real intacta y actualizada conforme se llenan campos.
 * - Barra inferior / Paginador fija al pie de la columna izquierda con:
 *   - Botón [ < Anterior ]
 *   - Pestañas/chips ordenados (estudios asignados primero, estudios no asignados al final)
 *   - Tres estados visuales claros:
 *     1. Asignado y Activo (azul primario sólido, texto blanco)
 *     2. Asignado pero Inactivo (azul pastel suave con borde y badge)
 *     3. No Asignado (estilo atenuado/fantasma con borde sutil y texto gris)
 *   - Acción dinámica contextual "[ + Añadir estudio a esta orden ]" para estudios no asignados.
 *   - Botón [ Siguiente > ]
 * - Navegación por teclado tipo Excel (Enter/Tab sin enviar formulario).
 * - Cero emojis, cero dependencias externas, cero almacenamiento en navegador.
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
import {
  obtenerEstudiosCatalogoApi,
  EstudioCatalogo,
} from "../../api/catalogo";
import { ApiError } from "../../api/client";
import {
  generarEstudioCapturaPlantilla,
  calcularEstudioLocalmente,
} from "./catalogoEstudiosPlantillas";

export const CapturaResultadosPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const ordenId = Number(id);
  const location = useLocation();
  const advertenciasSolapamiento = (location.state as { advertencias?: AdvertenciaSolapamiento[] } | null)?.advertencias;

  const { usuario } = useAuth();
  const esAdmin = usuario?.rol === "ADMIN";

  // Estados de datos principales
  const [captura, setCaptura] = useState<CapturaOrdenResponse | null>(null);
  const [ordenDetalle, setOrdenDetalle] = useState<OrdenDetalle | null>(null);
  const [configLab, setConfigLab] = useState<ConfiguracionLaboratorio>({
    nombre_laboratorio: "Laboratorio Clínico Metodista",
    separador_decimal: ",",
  });
  const [cargando, setCargando] = useState<boolean>(true);
  const [errorGeneral, setErrorGeneral] = useState<string | null>(null);

  // Catálogo total de estudios del sistema
  const [catalogoEstudios, setCatalogoEstudios] = useState<EstudioCatalogo[]>([]);

  // Lista de estudios asignados a esta orden (inicia con los de BD y puede recibir nuevos en memoria)
  const [estudiosAsignados, setEstudiosAsignados] = useState<EstudioCaptura[]>([]);

  // Código del estudio activo en el modo enfocado
  const [estudioActivoCodigo, setEstudioActivoCodigo] = useState<string>("");

  // Conjunto de códigos de parámetros pertenecientes a la orden en backend (para no violar alcance en PUT/calcular)
  const codigosParametrosBackendRef = useRef<Set<string>>(new Set());

  // Valores locales en los inputs (código -> valor string)
  const [valoresForm, setValoresForm] = useState<Record<string, string>>({});

  // Valores modificados pendientes de persistir (código -> valor string o null)
  const valoresModificadosRef = useRef<Record<string, string | null>>({});

  // Referencias para asegurar scroll y foco
  const focoInicialRealizadoRef = useRef<boolean>(false);
  const activeTabRef = useRef<HTMLButtonElement | null>(null);
  const tabsScrollRef = useRef<HTMLDivElement | null>(null);

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
    focoInicialRealizadoRef.current = false;

    async function cargarDatos() {
      setCargando(true);
      setErrorGeneral(null);
      try {
        const [respConfig, respCaptura, respDetalle, respCatalogo] = await Promise.all([
          getConfiguracionLaboratorioApi().catch(() => ({
            nombre_laboratorio: "Laboratorio Clínico Metodista",
            separador_decimal: ",",
          })),
          getCapturaOrdenApi(ordenId),
          obtenerOrdenApi(ordenId).catch(() => null),
          obtenerEstudiosCatalogoApi().catch(() => []),
        ]);

        if (!activo) return;

        setConfigLab(respConfig);
        setCaptura(respCaptura);
        setOrdenDetalle(respDetalle);
        setCatalogoEstudios(respCatalogo);
        setEstudiosAsignados(respCaptura.estudios);

        // Registrar qué parámetros existen en la orden en el backend
        const backendParams = new Set<string>();
        respCaptura.estudios.forEach((est) => {
          est.secciones.forEach((sec) => {
            sec.parametros.forEach((p) => {
              backendParams.add(p.codigo);
            });
          });
        });
        codigosParametrosBackendRef.current = backendParams;

        // Estudio activo inicial: el primer estudio asignado
        if (respCaptura.estudios.length > 0) {
          setEstudioActivoCodigo(respCaptura.estudios[0].codigo);
        }

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

  // Foco automático en el primer campo editable del estudio activo
  const enfocarPrimerInputEstudioActivo = useCallback(() => {
    if (esAdmin) return;
    window.setTimeout(() => {
      const primerInput = document.querySelector<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>(
        ".lis-captura-hoja-content .lis-captura-input:not([disabled])"
      );
      if (primerInput) {
        primerInput.focus();
        if (primerInput instanceof HTMLInputElement) primerInput.select();
      }
    }, 60);
  }, [esAdmin]);

  // Ejecutar foco inicial al cargar la orden
  useEffect(() => {
    if (!cargando && captura && !esAdmin && !focoInicialRealizadoRef.current) {
      focoInicialRealizadoRef.current = true;
      enfocarPrimerInputEstudioActivo();
    }
  }, [cargando, captura, esAdmin, enfocarPrimerInputEstudioActivo]);

  // Scroll automático en barra de pestañas para mantener visible la pestaña activa
  useEffect(() => {
    if (activeTabRef.current) {
      activeTabRef.current.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
        inline: "nearest",
      });
    }
  }, [estudioActivoCodigo]);

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
        // Enviar únicamente parámetros que pertenezcan al alcance de la orden en backend
        const payloadValores: Record<string, string | null> = {};
        let hayParametrosBackend = false;

        Object.keys(valoresActuales).forEach((cod) => {
          if (codigosParametrosBackendRef.current.has(cod)) {
            const val = valoresActuales[cod];
            payloadValores[cod] = val && val.trim() !== "" ? val.trim() : null;
            hayParametrosBackend = true;
          }
        });

        // 1. Recálculo en backend si hay estudios originales
        if (hayParametrosBackend) {
          const resp = await calcularResultadosApi(ordenId, payloadValores);
          setCaptura(resp);

          // Sincronizar estudios asignados manteniendo los virtuales agregados
          setEstudiosAsignados((prev) => {
            const codigosBackend = new Set(resp.estudios.map((e) => e.codigo));
            const virtuales = prev.filter((e) => !codigosBackend.has(e.codigo));
            const virtualesRecalculados = virtuales.map((v) =>
              calcularEstudioLocalmente(v, valoresActuales)
            );
            return [...resp.estudios, ...virtualesRecalculados];
          });
        } else {
          // Si solo hay virtuales, calcular localmente
          setEstudiosAsignados((prev) =>
            prev.map((e) => calcularEstudioLocalmente(e, valoresActuales))
          );
        }
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

      // Filtrar solo los parámetros que pertenecen a la orden en backend
      const cambiosBackend: Record<string, string | null> = {};
      Object.keys(cambios).forEach((k) => {
        if (codigosParametrosBackendRef.current.has(k)) {
          cambiosBackend[k] = cambios[k];
        }
      });

      if (Object.keys(cambiosBackend).length === 0) {
        // Son solo cambios de estudios en memoria/virtuales
        Object.keys(cambios).forEach((k) => {
          delete valoresModificadosRef.current[k];
        });
        const ahora = new Date();
        setHoraUltimoGuardado(ahora.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
        setEstadoGuardado("guardado");
        return;
      }

      setEstadoGuardado("guardando");
      setErrorGuardadoMensaje(null);

      try {
        const resp = await guardarResultadosApi(ordenId, cambiosBackend);
        setCaptura(resp);
        Object.keys(cambiosBackend).forEach((k) => {
          delete valoresModificadosRef.current[k];
        });

        // Actualizar estudios asignados conservando los agregados en memoria
        setEstudiosAsignados((prev) => {
          const codigosBackend = new Set(resp.estudios.map((e) => e.codigo));
          const virtuales = prev.filter((e) => !codigosBackend.has(e.codigo));
          return [...resp.estudios, ...virtuales];
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

    // Actualizar localmente los cálculos instantáneos
    setEstudiosAsignados((prev) =>
      prev.map((e) => calcularEstudioLocalmente(e, valoresActualizados))
    );

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

      setEstudiosAsignados((prev) => {
        const codigosBackend = new Set(resp.estudios.map((e) => e.codigo));
        const virtuales = prev.filter((e) => !codigosBackend.has(e.codigo));
        return [...resp.estudios, ...virtuales];
      });

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
          ".lis-captura-hoja-content .lis-captura-input:not([disabled])"
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

  // Enfocar campo pendiente al hacer clic desde el desplegable de pendientes
  const enfocarParametro = (codigo: string) => {
    setMostrarMenuPendientes(false);
    // Buscar en qué estudio se encuentra el parámetro y cambiar la pestaña activa si es necesario
    const estudioContenedor = estudiosAsignados.find((est) =>
      est.secciones.some((sec) => sec.parametros.some((p) => p.codigo === codigo))
    );
    if (estudioContenedor && estudioContenedor.codigo !== estudioActivoCodigo) {
      setEstudioActivoCodigo(estudioContenedor.codigo);
    }

    window.setTimeout(() => {
      const el = document.getElementById(`input-${codigo}`);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
        el.focus();
        if (el instanceof HTMLInputElement) el.select();
      }
    }, 100);
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

  // Acción dinámica: Añadir estudio del catálogo a la orden en memoria
  const handleAnadirEstudioAOrden = (codigo: string, nombreEstudio: string) => {
    const sexoPac = ordenDetalle?.paciente?.sexo || captura?.orden?.paciente?.sexo || "M";
    const nuevoEstudio = generarEstudioCapturaPlantilla(codigo, nombreEstudio, sexoPac);

    // Si tiene valores por defecto, agregarlos a valoresForm
    const nuevosValores = { ...valoresForm };
    nuevoEstudio.secciones.forEach((sec) => {
      sec.parametros.forEach((p) => {
        if (p.valor !== null && p.valor !== undefined) {
          nuevosValores[p.codigo] = p.valor;
        }
      });
    });
    setValoresForm(nuevosValores);

    // Agregar a la lista de estudios asignados al final de la cola
    setEstudiosAsignados((prev) => [...prev, nuevoEstudio]);

    // Establecer como estudio activo de inmediato
    setEstudioActivoCodigo(codigo);

    // Foco en el primer campo útil
    enfocarPrimerInputEstudioActivo();
  };

  // Navegación: Cambiar de estudio activo (guarda cambios pendientes)
  const cambiarEstudioActivo = (codigo: string) => {
    if (Object.keys(valoresModificadosRef.current).length > 0) {
      ejecutarGuardado();
    }
    setEstudioActivoCodigo(codigo);
    enfocarPrimerInputEstudioActivo();
  };

  // Botón [ Siguiente > ]
  const handleSiguienteEstudio = () => {
    const idxActual = estudiosAsignados.findIndex((e) => e.codigo === estudioActivoCodigo);
    if (idxActual >= 0 && idxActual + 1 < estudiosAsignados.length) {
      cambiarEstudioActivo(estudiosAsignados[idxActual + 1].codigo);
    }
  };

  // Botón [ < Anterior ]
  const handleAnteriorEstudio = () => {
    const idxActual = estudiosAsignados.findIndex((e) => e.codigo === estudioActivoCodigo);
    if (idxActual > 0) {
      cambiarEstudioActivo(estudiosAsignados[idxActual - 1].codigo);
    } else if (idxActual === -1 && estudiosAsignados.length > 0) {
      // Si estaba en un estudio no asignado, regresa al último asignado
      cambiarEstudioActivo(estudiosAsignados[estudiosAsignados.length - 1].codigo);
    }
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

  const { orden, completitud } = captura;

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

  // Identificar estudios asignados y no asignados del catálogo
  const codigosAsignados = new Set(estudiosAsignados.map((e) => e.codigo));
  const estudiosNoAsignadosCatalogo = catalogoEstudios.filter(
    (cat) => !codigosAsignados.has(cat.codigo)
  );

  // Estudio activo asignado (si aplica)
  const estudioActivo = estudiosAsignados.find((e) => e.codigo === estudioActivoCodigo);

  // Estudio activo no asignado (si se seleccionó una pestaña no asignada)
  const estudioCatalogoNoAsignado = !estudioActivo
    ? catalogoEstudios.find((c) => c.codigo === estudioActivoCodigo)
    : null;

  // Índices para paginador
  const idxAsignadoActual = estudiosAsignados.findIndex((e) => e.codigo === estudioActivoCodigo);
  const puedeAnterior = idxAsignadoActual > 0 || (idxAsignadoActual === -1 && estudiosAsignados.length > 0);
  const puedeSiguiente = idxAsignadoActual >= 0 && idxAsignadoActual + 1 < estudiosAsignados.length;

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

  // Renderizar sección analítica
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
          {/* Columna Izquierda (≈ 55 %) — Modo Enfocado con Barra de Navegación Inferior */}
          <div className="lis-captura-hoja">
            {/* Área de Trabajo: Muestra ÚNICAMENTE el formulario del estudio activo */}
            <div className="lis-captura-hoja-content">
              {estudioActivo ? (
                <div key={estudioActivo.codigo} className="lis-captura-estudio-box">
                  {/* Encabezado del estudio enfocado */}
                  {(() => {
                    const conteo = calcularConteoEstudio(estudioActivo);
                    const idx = estudiosAsignados.findIndex((e) => e.codigo === estudioActivo.codigo);
                    return (
                      <div className="lis-captura-estudio-header">
                        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                          <span style={{ fontSize: "14px", fontWeight: 700 }}>
                            {idx + 1}. {estudioActivo.nombre}
                          </span>
                          <span
                            className="lis-chip"
                            style={{ fontSize: "11px", padding: "1px 6px", backgroundColor: "#e2e8f0" }}
                          >
                            Estudio {idx + 1} de {estudiosAsignados.length}
                          </span>
                        </div>
                        <span
                          className="lis-chip"
                          style={{
                            fontSize: "11px",
                            padding: "1px 6px",
                            backgroundColor:
                              conteo.completos === conteo.total && conteo.total > 0
                                ? "var(--success-bg, #dcfce7)"
                                : "#f1f5f9",
                            color:
                              conteo.completos === conteo.total && conteo.total > 0
                                ? "var(--success)"
                                : "inherit",
                          }}
                        >
                          {conteo.completos}/{conteo.total} completados
                        </span>
                      </div>
                    );
                  })()}

                  {/* Validaciones de reglas cruzadas del estudio si aplican */}
                  {estudioActivo.validaciones && estudioActivo.validaciones.length > 0 && (
                    <div style={{ padding: "4px 8px", display: "flex", flexDirection: "column", gap: "4px" }}>
                      {estudioActivo.validaciones.map((val, idx) => (
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

                  {/* Secciones y tabla de captura del estudio activo */}
                  <div style={{ padding: "6px" }}>
                    {estudioActivo.secciones.map((sec) => renderizarSeccion(sec))}
                  </div>
                </div>
              ) : estudioCatalogoNoAsignado ? (
                /* Vista contextual cuando se hace clic en una pestaña de estudio NO asignado */
                <div className="lis-unassigned-card">
                  <div className="lis-unassigned-banner">
                    <div>
                      <div style={{ fontSize: "12px", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700 }}>
                        Estudio del catálogo no asignado
                      </div>
                      <h3 style={{ margin: "2px 0 4px 0", fontSize: "16px", color: "var(--text-main)" }}>
                        {estudioCatalogoNoAsignado.nombre}
                      </h3>
                      <div style={{ fontSize: "12.5px", color: "var(--text-muted)" }}>
                        Categoría: <strong>{estudioCatalogoNoAsignado.categoria}</strong>
                      </div>
                    </div>

                    {!esAdmin && (
                      <button
                        type="button"
                        className="lis-btn lis-btn-primary"
                        onClick={() =>
                          handleAnadirEstudioAOrden(
                            estudioCatalogoNoAsignado.codigo,
                            estudioCatalogoNoAsignado.nombre
                          )
                        }
                        title="Incorporar este estudio a la orden actual del paciente"
                        style={{ padding: "6px 16px", fontWeight: 700 }}
                      >
                        + Añadir estudio a esta orden
                      </button>
                    )}
                  </div>

                  <div style={{ fontSize: "13px", color: "var(--text-main)" }}>
                    <p style={{ margin: "0 0 8px 0" }}>
                      Este estudio no forma parte de la solicitud inicial de este paciente. Si desea registrar resultados analíticos para este estudio, pulse el botón <strong>Añadir estudio a esta orden</strong>.
                    </p>
                    <p style={{ margin: 0, color: "var(--text-muted)", fontSize: "12px" }}>
                      Al añadirlo, se activará su hoja de captura en esta pantalla y se incorporará en tiempo real al informe previo del panel derecho.
                    </p>
                  </div>
                </div>
              ) : (
                <div style={{ padding: "20px", textAlign: "center", color: "var(--text-muted)" }}>
                  Seleccione un estudio de la barra inferior para capturar resultados.
                </div>
              )}
            </div>

            {/* Barra de Navegación / Paginador Inferior Fija (§3 y §4) */}
            <div className="lis-captura-bottom-bar">
              {/* Botón [ < Anterior ] */}
              <button
                type="button"
                className="lis-captura-nav-btn"
                onClick={handleAnteriorEstudio}
                disabled={!puedeAnterior}
                title="Regresar al estudio asignado previo"
              >
                ← Anterior
              </button>

              {/* Contenedor con Scroll Horizontal de Pestañas / Chips Numerados */}
              <div className="lis-captura-tabs-scroll" ref={tabsScrollRef}>
                {/* 1. Primeros puestos: Estudios ya asignados a la orden */}
                {estudiosAsignados.map((est, idx) => {
                  const esActivo = est.codigo === estudioActivoCodigo;
                  const conteo = calcularConteoEstudio(est);
                  const estaCompleto = conteo.completos === conteo.total && conteo.total > 0;

                  return (
                    <button
                      key={est.codigo}
                      ref={esActivo ? activeTabRef : null}
                      type="button"
                      className={`lis-captura-tab is-assigned ${esActivo ? "is-active" : ""}`}
                      onClick={() => cambiarEstudioActivo(est.codigo)}
                      title={`Estudio asignado: ${est.nombre} (${conteo.completos}/${conteo.total})`}
                    >
                      <span>
                        {idx + 1}. {est.nombre}
                      </span>
                      <span className="lis-tab-badge">
                        {estaCompleto ? "✓" : `${conteo.completos}/${conteo.total}`}
                      </span>
                    </button>
                  );
                })}

                {/* Separador sutil si hay estudios no asignados */}
                {estudiosNoAsignadosCatalogo.length > 0 && (
                  <div
                    style={{
                      width: "1px",
                      height: "20px",
                      backgroundColor: "var(--border-color)",
                      margin: "0 2px",
                      flexShrink: 0,
                    }}
                  />
                )}

                {/* 2. Puestos finales: Estudios del catálogo no incluidos en la orden */}
                {estudiosNoAsignadosCatalogo.map((cat, idx) => {
                  const numero = estudiosAsignados.length + idx + 1;
                  const esActivo = cat.codigo === estudioActivoCodigo;

                  return (
                    <button
                      key={cat.codigo}
                      ref={esActivo ? activeTabRef : null}
                      type="button"
                      className={`lis-captura-tab is-unassigned ${esActivo ? "is-active" : ""}`}
                      onClick={() => cambiarEstudioActivo(cat.codigo)}
                      title={`Estudio fuera de la orden: ${cat.nombre} (clic para ver y añadir)`}
                    >
                      <span>
                        {numero}. {cat.nombre}
                      </span>
                      <span className="lis-tab-badge">+</span>
                    </button>
                  );
                })}
              </div>

              {/* Botón [ Siguiente > ] */}
              <button
                type="button"
                className="lis-captura-nav-btn"
                onClick={handleSiguienteEstudio}
                disabled={!puedeSiguiente}
                title="Avanzar al siguiente estudio asignado de la orden"
              >
                Siguiente →
              </button>
            </div>
          </div>

          {/* Columna Derecha (≈ 45 %) — Vista Previa Grande con scroll propio e intacta */}
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
                  <span style={{ fontSize: "11.5px", color: "var(--text-muted)", display: "block" }}>Pieza:</span>
                  <span>{ordenDetalle?.pieza || "No asignada"}</span>
                </div>
              </div>

              {/* Tablas por estudio con fuente >= 14 px para todos los estudios asignados */}
              {estudiosAsignados.map((estudio) => (
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
                          } else {
                            const valAct = valoresForm[p.codigo] !== undefined ? valoresForm[p.codigo] : p.valor;
                            if (valAct !== null && valAct !== undefined && valAct !== "") {
                              valorTexto = formatearValorVisual(valAct);
                            }
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
