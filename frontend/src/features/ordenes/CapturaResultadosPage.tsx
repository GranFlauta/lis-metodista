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

import React, { useEffect, useMemo, useState, useRef, useCallback } from "react";
import { EntradaResultadoTexto } from "../../components/EntradaResultadoTexto";
import { MuestrasSeriadas } from "../../components/MuestrasSeriadas";
import { useParams, Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";
import {
  getCapturaOrdenApi,
  calcularResultadosApi,
  guardarResultadosApi,
  confirmarDefectosApi,
  getConfiguracionLaboratorioApi,
  VistaPreviaPayload,
  CapturaOrdenResponse,
  EstudioCaptura,
  SeccionCaptura,
  ParametroCaptura,
  ConfiguracionLaboratorio,
  RangoOverrideItem,
} from "../../api/resultados";
import {
  obtenerOrdenApi,
  OrdenDetalle,
  AdvertenciaSolapamiento,
  agregarEstudioAOrdenApi,
  actualizarGruposEstudioApi,
  eliminarEstudioDeOrdenApi,
} from "../../api/ordenes";
import {
  obtenerEstudiosCatalogoApi,
  EstudioCatalogo,
} from "../../api/catalogo";
import { ApiError } from "../../api/client";
import { CurvaToleranciaCaptura } from "./CurvaToleranciaCaptura";
import { formatearResultadoClinico } from "../../utils/formatoNumerico";
import { EntradaResultadoNumerico } from "../../components/EntradaResultadoNumerico";
import { VistaPreviaInforme } from "../../components/VistaPreviaInforme";
import { SeccionInmunoserologia } from "./SeccionInmunoserologia";
import { SeccionGrupoSanguineo } from "./SeccionGrupoSanguineo";
import {
  ModalEditarRango,
  ModalSeleccionarInmunosero,
} from "./ModalCapturaHelpers";
import { publicarOrden } from "../../api/informes";
import { CargaLaboratorio, MarcaLaboratorio } from "../../components/MarcaLaboratorio";
import { Icono } from "../../components/Icono";

export const CapturaResultadosPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const ordenId = Number(id);
  const location = useLocation();
  const advertenciasSolapamiento = (location.state as { advertencias?: AdvertenciaSolapamiento[] } | null)?.advertencias;

  const navigate = useNavigate();
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

  // Lista de estudios asignados a esta orden
  const [estudiosAsignados, setEstudiosAsignados] = useState<EstudioCaptura[]>([]);

  // Código del estudio activo en el modo enfocado
  const [estudioActivoCodigo, setEstudioActivoCodigo] = useState<string>("");

  // Conjunto de códigos de parámetros pertenecientes a la orden en backend
  const codigosParametrosBackendRef = useRef<Set<string>>(new Set());

  // Valores locales en los inputs (código -> valor string)
  const [valoresForm, setValoresForm] = useState<Record<string, string>>({});
  const [etiquetaCayados, setEtiquetaCayados] = useState("Cayados");

  // Valores modificados pendientes de persistir (código -> valor string o null)
  const valoresModificadosRef = useRef<Record<string, string | null>>({});

  const [unidadesForm, setUnidadesForm] = useState<Record<string, string | null>>({});
  const unidadesFormRef = useRef<Record<string, string | null>>({});
  const unidadesModificadasRef = useRef<Record<string, string | null>>({});

  // Observaciones por estudio y generales de la orden
  const [observacionesEstudios, setObservacionesEstudios] = useState<Record<string, string>>({});
  const observacionesEstudiosRef = useRef<Record<string, string | null>>({});
  const etiquetasEstudiosRef = useRef<Record<string, string | null>>({});
  const [observacionesOrden, setObservacionesOrden] = useState<string>("");
  const observacionesOrdenRef = useRef<string | null>(null);

  // Overrides de rangos de referencia editables
  const [rangosOverride, setRangosOverride] = useState<Record<string, RangoOverrideItem>>({});
  const rangosOverrideRef = useRef<Record<string, RangoOverrideItem>>({});

  // Modales interactivos
  const [modalRangoAbierto, setModalRangoAbierto] = useState<{
    codigo: string;
    nombre: string;
    inf: string;
    sup: string;
    txt: string;
    modificada: boolean;
  } | null>(null);

  const [modalInmunoAbierto, setModalInmunoAbierto] = useState<boolean>(false);
  const [gruposInmunoseroSeleccionados, setGruposInmunoseroSeleccionados] = useState<Set<string>>(new Set());

  // Estados para Publicación Oficial (Fase 4)
  const [modalPublicarAbierto, setModalPublicarAbierto] = useState<boolean>(false);
  const [justificativoUrgenciaPub, setJustificativoUrgenciaPub] = useState<string>("");
  const [publicando, setPublicando] = useState<boolean>(false);
  const [errorPublicacion, setErrorPublicacion] = useState<string | null>(null);
  const [resultadoPublicacion, setResultadoPublicacion] = useState<{
    folio: string;
    numero_version: number;
    snapshot_sha256: string;
  } | null>(null);

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

  // Referencias a timers para debounce
  const timerCalcularRef = useRef<number | null>(null);
  const timerGuardarRef = useRef<number | null>(null);
  const guardadoEnCursoRef = useRef<Promise<void> | null>(null);

  const codigosVistaPrevia = (captura?.estudios || [])
    .flatMap((estudio) => estudio.secciones.flatMap((seccion) => seccion.parametros))
    .filter((parametro) => !parametro.es_calculado)
    .map((parametro) => parametro.codigo).join("|");
  const payloadVistaPrevia = useMemo<VistaPreviaPayload>(() => {
    if (esAdmin) return { valores: {} };
    const permitidos = new Set(codigosVistaPrevia.split("|"));
    return {
      valores: Object.fromEntries(Object.entries(valoresForm).filter(([codigo]) => permitidos.has(codigo))),
      rangos_override: Object.fromEntries(Object.entries(rangosOverride).filter(([codigo]) => codigosParametrosBackendRef.current.has(codigo))),
      observaciones_estudios: observacionesEstudios,
      observaciones_orden: observacionesOrden,
      etiqueta_cayados: etiquetaCayados,
      unidades_override: Object.fromEntries(Object.entries(unidadesForm).filter(([codigo]) => permitidos.has(codigo))),
    };
  }, [esAdmin, codigosVistaPrevia, valoresForm, rangosOverride, observacionesEstudios, observacionesOrden, etiquetaCayados, unidadesForm]);

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
        const etiquetaCayadosInicial = respCaptura.estudios.find((est) => est.codigo === "HEMOGRAMA")?.etiqueta_cayados;
        setEtiquetaCayados(etiquetaCayadosInicial || "Cayados");

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
        const unidadesIniciales: Record<string, string | null> = {};
        const overridesIniciales: Record<string, RangoOverrideItem> = {};
        const obsEstudiosIniciales: Record<string, string> = {};

        respCaptura.estudios.forEach((est: EstudioCaptura) => {
          if (est.observaciones) {
            obsEstudiosIniciales[est.codigo] = est.observaciones;
          }
          if (est.codigo === "INMUNOSEROLOGIA" && est.grupos_seleccionados) {
            setGruposInmunoseroSeleccionados(new Set(est.grupos_seleccionados));
          }

          est.secciones.forEach((sec: SeccionCaptura) => {
            sec.parametros.forEach((p: ParametroCaptura) => {
              if (!p.es_calculado && p.valor !== null && !(p.es_defecto && !p.confirmado)) {
                mapaInicial[p.codigo] = p.valor;
              }
              if (p.unidad_editable && p.unidad_modificada) unidadesIniciales[p.codigo] = p.unidad ?? "";
              if (p.referencia?.modificada) {
                overridesIniciales[p.codigo] = {
                  limite_inferior: p.referencia.inferior,
                  limite_superior: p.referencia.superior,
                  texto: p.referencia.texto,
                  reestablecer: false,
                };
              }
            });
          });
        });

        setValoresForm(mapaInicial);
        setUnidadesForm(unidadesIniciales);
        unidadesFormRef.current = unidadesIniciales;
        unidadesModificadasRef.current = {};
        setRangosOverride(overridesIniciales);
        rangosOverrideRef.current = overridesIniciales;

        setObservacionesEstudios(obsEstudiosIniciales);
        const obsOrd = respCaptura.orden.observaciones || "";
        setObservacionesOrden(obsOrd);
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
    const tabs = tabsScrollRef.current;
    const activeTab = activeTabRef.current;
    if (!tabs || !activeTab) return;

    const tabsBounds = tabs.getBoundingClientRect();
    const tabBounds = activeTab.getBoundingClientRect();
    if (tabBounds.left < tabsBounds.left) {
      tabs.scrollBy({ left: tabBounds.left - tabsBounds.left, behavior: "smooth" });
    } else if (tabBounds.right > tabsBounds.right) {
      tabs.scrollBy({ left: tabBounds.right - tabsBounds.right, behavior: "smooth" });
    }
  }, [estudioActivoCodigo]);

  // Manejo de beforeunload: advertir solo si hay cambios sin guardar
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (Object.keys(valoresModificadosRef.current).length > 0 || Object.keys(unidadesModificadasRef.current).length > 0) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, []);

  // Disparar cálculo en vivo (POST /calcular con debounce 400ms)
  const dispararCalculoEnVivo = useCallback(
    async (valoresActuales: Record<string, string>) => {
      if (!captura) return;
      try {
        const payloadValores: Record<string, string | null> = {};
        Object.keys(valoresActuales).forEach((cod) => {
          if (codigosParametrosBackendRef.current.has(cod)) {
            const val = valoresActuales[cod];
            payloadValores[cod] = val && val.trim() !== "" ? val.trim() : null;
          }
        });

        const resp = await calcularResultadosApi(
          ordenId,
          payloadValores,
          Object.keys(rangosOverrideRef.current).length > 0 ? rangosOverrideRef.current : undefined,
          Object.fromEntries(Object.entries(unidadesFormRef.current).filter(([codigo]) => codigosParametrosBackendRef.current.has(codigo)))
        );
        setCaptura(resp);
        setEstudiosAsignados(resp.estudios);
      } catch (err) {
        console.warn("Error en vista previa de cálculo síncrono:", err);
      }
    },
    [captura, ordenId]
  );

  // Persistir cambios (PUT /resultados con autoguardado 1500ms o botón Guardar ahora)
  const ejecutarGuardado = useCallback(
    async (cambiosPendientes?: Record<string, string | null>) => {
      if (esAdmin) return false;
      while (guardadoEnCursoRef.current) await guardadoEnCursoRef.current;
      const cambios = cambiosPendientes || { ...valoresModificadosRef.current };
      const overridesEnviados = { ...rangosOverrideRef.current };
      const obsEstudiosEnviadas = { ...observacionesEstudiosRef.current };
      const obsOrdenEnviada = observacionesOrdenRef.current;
      const etiquetasEnviadas = { ...etiquetasEstudiosRef.current };
      const unidadesEnviadas = { ...unidadesModificadasRef.current };
      const hayCambiosValores = Object.keys(cambios).length > 0;
      const hayOverrides = Object.keys(overridesEnviados).length > 0;
      const hayObsEstudios = Object.keys(obsEstudiosEnviadas).length > 0;
      const hayObsOrden = obsOrdenEnviada !== null;
      const hayEtiquetas = Object.keys(etiquetasEnviadas).length > 0;
      const hayUnidades = Object.keys(unidadesEnviadas).length > 0;

      if (!hayCambiosValores && !hayOverrides && !hayObsEstudios && !hayObsOrden && !hayEtiquetas && !hayUnidades) return true;

      const cambiosBackend: Record<string, string | null> = {};
      Object.keys(cambios).forEach((k) => {
        if (codigosParametrosBackendRef.current.has(k)) {
          cambiosBackend[k] = cambios[k];
        }
      });

      setEstadoGuardado("guardando");
      setErrorGuardadoMensaje(null);
      let liberarGuardado!: () => void;
      guardadoEnCursoRef.current = new Promise<void>((resolve) => { liberarGuardado = resolve; });

      try {
        const resp = await guardarResultadosApi(
          ordenId,
          cambiosBackend,
          hayOverrides ? overridesEnviados : undefined,
          hayObsEstudios ? obsEstudiosEnviadas : undefined,
          hayObsOrden ? obsOrdenEnviada : undefined,
          hayEtiquetas ? etiquetasEnviadas : undefined,
          hayUnidades ? unidadesEnviadas : undefined
        );
        setCaptura(resp);
        setEstudiosAsignados(resp.estudios);
        if (etiquetasEstudiosRef.current.HEMOGRAMA === etiquetasEnviadas.HEMOGRAMA) {
          setEtiquetaCayados(resp.estudios.find((est) => est.codigo === "HEMOGRAMA")?.etiqueta_cayados || "Cayados");
        }

        Object.keys(cambiosBackend).forEach((k) => {
          if (valoresModificadosRef.current[k] === cambiosBackend[k]) delete valoresModificadosRef.current[k];
        });
        if (observacionesOrdenRef.current === obsOrdenEnviada) observacionesOrdenRef.current = null;
        Object.keys(obsEstudiosEnviadas).forEach((k) => {
          if (observacionesEstudiosRef.current[k] === obsEstudiosEnviadas[k]) delete observacionesEstudiosRef.current[k];
        });
        Object.keys(etiquetasEnviadas).forEach((k) => {
          if (etiquetasEstudiosRef.current[k] === etiquetasEnviadas[k]) delete etiquetasEstudiosRef.current[k];
        });
        Object.keys(unidadesEnviadas).forEach((codigo) => {
          if (unidadesModificadasRef.current[codigo] === unidadesEnviadas[codigo]) delete unidadesModificadasRef.current[codigo];
        });

        const ahora = new Date();
        const horaStr = ahora.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
        setHoraUltimoGuardado(horaStr);
        const quedanCambios = Object.keys(valoresModificadosRef.current).length > 0
          || Object.keys(observacionesEstudiosRef.current).length > 0
          || Object.keys(etiquetasEstudiosRef.current).length > 0
          || Object.keys(unidadesModificadasRef.current).length > 0
          || observacionesOrdenRef.current !== null;
        setEstadoGuardado(quedanCambios ? "modificado" : "guardado");
        return !quedanCambios;
      } catch (err: unknown) {
        setEstadoGuardado("error");
        if (err instanceof ApiError) {
          setErrorGuardadoMensaje(err.message || "Error al persistir resultados.");
        } else {
          setErrorGuardadoMensaje("Error de conexión al guardar.");
        }
        return false;
      } finally {
        guardadoEnCursoRef.current = null;
        liberarGuardado();
      }
    },
    [esAdmin, ordenId]
  );

  // Manejar cambio en un campo de entrada
  const manejarCambiosCampos = (cambios: Record<string, string>) => {
    if (esAdmin) return;

    const valoresActualizados = {
      ...valoresForm,
      ...cambios,
    };
    setValoresForm(valoresActualizados);

    Object.entries(cambios).forEach(([codigo, nuevoValor]) => {
      const valorPersistir = nuevoValor.trim() === "" ? null : nuevoValor.trim();
      valoresModificadosRef.current[codigo] = valorPersistir;
    });
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

  const manejarCambioCampo = (codigo: string, nuevoValor: string) => {
    manejarCambiosCampos({ [codigo]: nuevoValor });
  };

  const manejarCambioUnidad = (codigo: string, unidad: string) => {
    if (esAdmin) return;
    const nuevas = { ...unidadesFormRef.current, [codigo]: unidad };
    unidadesFormRef.current = nuevas;
    setUnidadesForm(nuevas);
    unidadesModificadasRef.current[codigo] = unidad.trim();
    setEstadoGuardado("modificado");
    if (timerCalcularRef.current) window.clearTimeout(timerCalcularRef.current);
    timerCalcularRef.current = window.setTimeout(() => dispararCalculoEnVivo(valoresForm), 400);
    if (timerGuardarRef.current) window.clearTimeout(timerGuardarRef.current);
    timerGuardarRef.current = window.setTimeout(() => ejecutarGuardado(), 1500);
  };

  const manejarCambioEtiquetaCayados = (nuevoValor: string) => {
    if (esAdmin) return;
    const etiqueta = nuevoValor.slice(0, 80);
    setEtiquetaCayados(etiqueta);
    etiquetasEstudiosRef.current.HEMOGRAMA = etiqueta.trim() || null;
    setEstadoGuardado("modificado");
    if (timerGuardarRef.current) window.clearTimeout(timerGuardarRef.current);
    timerGuardarRef.current = window.setTimeout(() => ejecutarGuardado(), 1500);
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

  // Formatear valor numérico para la visualización (miles y decimales según configuración)
  const formatearValorVisual = (val: string | null | undefined, decimalesMax?: number): string => {
    return formatearResultadoClinico(val, configLab.separador_decimal, decimalesMax);
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
    // Si no hay bandera calculada, no renderizar guión '—' horrible
    if (!bandera) return null;
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

        const v = valoresForm[p.codigo] ?? p.valor;
        const estaLleno = p.captura_serologia ? Boolean(p.serologia?.completo) : p.es_calculado
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

  // Manejo de observaciones por estudio y orden
  const manejarCambioObservacionEstudio = (codigoEstudio: string, texto: string) => {
    if (esAdmin) return;
    setObservacionesEstudios((prev) => ({ ...prev, [codigoEstudio]: texto }));
    observacionesEstudiosRef.current[codigoEstudio] = texto.trim() === "" ? null : texto;
    setEstadoGuardado("modificado");
    if (timerGuardarRef.current) window.clearTimeout(timerGuardarRef.current);
    timerGuardarRef.current = window.setTimeout(() => {
      ejecutarGuardado();
    }, 1500);
  };

  const manejarCambioObservacionOrden = (texto: string) => {
    if (esAdmin) return;
    setObservacionesOrden(texto);
    observacionesOrdenRef.current = texto;
    setEstadoGuardado("modificado");
    if (timerGuardarRef.current) window.clearTimeout(timerGuardarRef.current);
    timerGuardarRef.current = window.setTimeout(() => {
      ejecutarGuardado();
    }, 1500);
  };

  // Manejo de overrides de rangos de referencia editables
  const handleGuardarRangoOverride = (codigo: string, inf: string, sup: string, txt: string) => {
    const item: RangoOverrideItem = {
      limite_inferior: inf || null,
      limite_superior: sup || null,
      texto: txt || null,
      reestablecer: false,
    };
    rangosOverrideRef.current[codigo] = item;
    setRangosOverride((prev) => ({ ...prev, [codigo]: item }));
    setModalRangoAbierto(null);
    dispararCalculoEnVivo(valoresForm);
    ejecutarGuardado();
  };

  const handleReestablecerRango = (codigo: string) => {
    const item: RangoOverrideItem = { reestablecer: true };
    rangosOverrideRef.current[codigo] = item;
    setRangosOverride((prev) => ({ ...prev, [codigo]: item }));
    setModalRangoAbierto(null);
    dispararCalculoEnVivo(valoresForm);
    ejecutarGuardado();
  };

  // Guardar subestudios seleccionados para Inmunoserología
  const handleGuardarSubestudiosInmuno = async () => {
    if (gruposInmunoseroSeleccionados.size === 0) {
      alert("Debe seleccionar al menos un subestudio de Inmunoserología.");
      return;
    }

    const estudioExistente = estudiosAsignados.find((e) => e.codigo === "INMUNOSEROLOGIA");
    try {
      setCargando(true);
      setModalInmunoAbierto(false);
      if (estudioExistente && estudioExistente.id_estudio) {
        await actualizarGruposEstudioApi(
          ordenId,
          estudioExistente.id_estudio,
          Array.from(gruposInmunoseroSeleccionados)
        );
      } else {
        await agregarEstudioAOrdenApi(ordenId, {
          codigo: "INMUNOSEROLOGIA",
          grupos: Array.from(gruposInmunoseroSeleccionados),
        });
      }

      const resp = await getCapturaOrdenApi(ordenId);
      setCaptura(resp);
      setEstudiosAsignados(resp.estudios);
      setEstudioActivoCodigo("INMUNOSEROLOGIA");

      const backendParams = new Set<string>();
      resp.estudios.forEach((est) => {
        est.secciones.forEach((sec) => {
          sec.parametros.forEach((p) => {
            backendParams.add(p.codigo);
          });
        });
      });
      codigosParametrosBackendRef.current = backendParams;

      const nuevoMapaInmuno = { ...valoresForm };
      resp.estudios.forEach((est) => {
        est.secciones.forEach((sec) => {
          sec.parametros.forEach((p) => {
            if (!p.es_calculado && p.valor !== null && !(p.es_defecto && !p.confirmado) && nuevoMapaInmuno[p.codigo] === undefined) {
              nuevoMapaInmuno[p.codigo] = p.valor;
            }
          });
        });
      });
      setValoresForm(nuevoMapaInmuno);
      dispararCalculoEnVivo(nuevoMapaInmuno);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        alert(err.message || "Error al actualizar subestudios de Inmunoserología.");
      } else {
        alert("Error de conexión al actualizar subestudios.");
      }
    } finally {
      setCargando(false);
    }
  };

  // Acción dinámica: Añadir estudio del catálogo a la orden en backend
  const handleAnadirEstudioAOrden = async (codigo: string, nombreEstudio: string) => {
    if (codigo === "INMUNOSEROLOGIA") {
      setModalInmunoAbierto(true);
      return;
    }

    try {
      setCargando(true);
      await agregarEstudioAOrdenApi(ordenId, { codigo });
      const resp = await getCapturaOrdenApi(ordenId);
      setCaptura(resp);
      setEstudiosAsignados(resp.estudios);
      setEstudioActivoCodigo(codigo);

      const backendParams = new Set<string>();
      resp.estudios.forEach((est) => {
        est.secciones.forEach((sec) => {
          sec.parametros.forEach((p) => {
            backendParams.add(p.codigo);
          });
        });
      });
      codigosParametrosBackendRef.current = backendParams;

      const nuevoMapaEstudios = { ...valoresForm };
      resp.estudios.forEach((est) => {
        est.secciones.forEach((sec) => {
          sec.parametros.forEach((p) => {
            if (!p.es_calculado && p.valor !== null && !(p.es_defecto && !p.confirmado) && nuevoMapaEstudios[p.codigo] === undefined) {
              nuevoMapaEstudios[p.codigo] = p.valor;
            }
          });
        });
      });
      setValoresForm(nuevoMapaEstudios);
      dispararCalculoEnVivo(nuevoMapaEstudios);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        alert(err.message || "Error al añadir estudio a la orden.");
      } else {
        alert("Error de conexión al añadir estudio.");
      }
    } finally {
      setCargando(false);
    }
  };

  // Acción dinámica: Eliminar estudio de la orden con auto-cancelación si quedan 0 estudios
  const handleEliminarEstudio = async (estudio: EstudioCaptura) => {
    if (!estudio.id_estudio) return;

    const seguro = window.confirm(
      `¿Desea eliminar el estudio "${estudio.nombre}" de esta orden clínica?\n\nSi elimina todos los estudios, la orden quedará descartada y cancelada automáticamente según la regla del laboratorio.`
    );
    if (!seguro) return;

    try {
      setCargando(true);
      const res = await eliminarEstudioDeOrdenApi(ordenId, estudio.id_estudio);
      if (res.orden_descartada) {
        alert(
          "Todos los estudios de la orden han sido eliminados.\nLa orden ha sido descartada y cancelada automáticamente."
        );
        navigate("/ordenes");
        return;
      }

      const resp = await getCapturaOrdenApi(ordenId);
      setCaptura(resp);
      setEstudiosAsignados(resp.estudios);
      if (resp.estudios.length > 0) {
        setEstudioActivoCodigo(resp.estudios[0].codigo);
      }

      const backendParams = new Set<string>();
      resp.estudios.forEach((est) => {
        est.secciones.forEach((sec) => {
          sec.parametros.forEach((p) => {
            backendParams.add(p.codigo);
          });
        });
      });
      codigosParametrosBackendRef.current = backendParams;
      const unidadesRestantes = Object.fromEntries(Object.entries(unidadesFormRef.current).filter(([codigo]) => backendParams.has(codigo)));
      unidadesFormRef.current = unidadesRestantes;
      setUnidadesForm(unidadesRestantes);
      unidadesModificadasRef.current = Object.fromEntries(Object.entries(unidadesModificadasRef.current).filter(([codigo]) => backendParams.has(codigo)));
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        alert(err.message || "Error al eliminar el estudio de la orden.");
      } else {
        alert("Error de conexión al eliminar estudio.");
      }
    } finally {
      setCargando(false);
    }
  };

  // Publicación Oficial de la Orden (Fase 4)
  const handleAbrirPublicar = async () => {
    setErrorPublicacion(null);
    setJustificativoUrgenciaPub("");
    setModalPublicarAbierto(true);
  };

  const handleConfirmarPublicacion = async () => {
    setPublicando(true);
    setErrorPublicacion(null);
    try {
      if (timerGuardarRef.current) window.clearTimeout(timerGuardarRef.current);
      if (timerCalcularRef.current) window.clearTimeout(timerCalcularRef.current);
      const guardadoCorrecto = await ejecutarGuardado();
      if (!guardadoCorrecto) {
        setErrorPublicacion("No se guardaron todos los cambios. Revise la conexión y vuelva a publicar.");
        return;
      }
      const res = await publicarOrden(ordenId, justificativoUrgenciaPub.trim() || undefined);
      setResultadoPublicacion({
        folio: res.folio,
        numero_version: res.numero_version,
        snapshot_sha256: res.snapshot_sha256,
      });
      if (ordenDetalle) {
        setOrdenDetalle({ ...ordenDetalle, estado_trabajo: "PUBLICADA" });
      }
      if (captura) {
        setCaptura({
          ...captura,
          orden: { ...captura.orden, estado_trabajo: "PUBLICADA" },
        });
      }
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setErrorPublicacion(err.message || "Error al publicar la orden.");
      } else {
        setErrorPublicacion("Error de conexión al emitir la publicación oficial.");
      }
    } finally {
      setPublicando(false);
    }
  };

  // Navegación: Cambiar de estudio activo (guarda cambios pendientes)
  const cambiarEstudioActivo = (codigo: string) => {
    if (Object.keys(valoresModificadosRef.current).length > 0 || Object.keys(unidadesModificadasRef.current).length > 0) {
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
        <CargaLaboratorio mensaje="Cargando plantilla del estudio…" />
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
    const nombreDiferencial = pctParam.codigo === "CAYADOS_PCT" ? etiquetaCayados : pctParam.nombre;
    const valorPctActual = valoresForm[pctParam.codigo] !== undefined
      ? valoresForm[pctParam.codigo]
      : pctParam.valor || "";

    const absCalculable = absParam?.calculable && absParam?.valor !== null;
    const absValorStr = absCalculable
      ? formatearValorVisual(absParam.valor)
      : (absParam?.motivo_no_calculable && !absParam.motivo_no_calculable.toLowerCase().includes("falta"))
      ? "No calculable"
      : "Esperando datos";

    return (
      <tr key={pctParam.codigo}>
        <td className="lis-sheet-parameter">
          {pctParam.codigo === "CAYADOS_PCT" && !esAdmin ? (
            <input aria-label="Nombre del diferencial" className="lis-captura-input" maxLength={80} value={etiquetaCayados} onChange={(e) => manejarCambioEtiquetaCayados(e.target.value)} style={{ width: 104, fontWeight: 600 }} />
          ) : <span style={{ fontWeight: 600 }}>{nombreDiferencial}</span>}
          {pctParam.obligatorio && <span style={{ color: "var(--error)", marginLeft: "2px" }}>*</span>}
        </td>
        <td className="lis-sheet-entry">
            <EntradaResultadoNumerico
              id={`input-${pctParam.codigo}`}
              separadorDecimal={configLab.separador_decimal}
              className="lis-captura-input is-numeric is-diferencial-pct"
              value={valorPctActual}
              onValueChange={(valor) => manejarCambioCampo(pctParam.codigo, valor)}
              onKeyDown={manejarKeyDownInput}
              onFocus={(e) => e.target.select()}
              disabled={esAdmin}
              aria-label={`${nombreDiferencial}: relativo (%)`}
              title={`${nombreDiferencial} (%)`}
            />
        </td>
        <td className="lis-sheet-output">
            <output
              className={`lis-captura-calc-box is-diferencial-abs ${!absCalculable ? "is-unavailable" : ""}`}
              htmlFor={`input-${pctParam.codigo}`}
              aria-label={`${nombreDiferencial}: absoluto calculado`}
              title={absParam ? `${absParam.nombre}: ${absValorStr} mm3` : ""}
            >
              {absValorStr}
            </output>
        </td>
        <td style={{ fontSize: "11.5px", color: "var(--text-muted)" }}>
          <div className="lis-sheet-reference">
            <span>{pctParam.referencia?.texto || "—"}</span>
            {!esAdmin && (
              <div style={{ display: "flex", alignItems: "center", gap: "2px" }}>
                {pctParam.referencia?.modificada && (
                  <span
                    className="lis-chip"
                    style={{ fontSize: "9px", padding: "0 4px", backgroundColor: "var(--warning-bg)", color: "var(--warning)" }}
                    title="Valor de referencia personalizado para esta orden"
                  >
                    Modificado
                  </span>
                )}
                <button
                  type="button"
                  onClick={() =>
                    setModalRangoAbierto({
                      codigo: pctParam.codigo,
                      nombre: pctParam.nombre,
                      inf: pctParam.referencia?.inferior || "",
                      sup: pctParam.referencia?.superior || "",
                      txt: pctParam.referencia?.texto || "",
                      modificada: !!pctParam.referencia?.modificada,
                    })
                  }
                  title="Editar valor de referencia para esta orden"
                  aria-label={`Editar referencia de ${nombreDiferencial}`}
                  className="lis-sheet-icon-btn"
                >
                  <Icono nombre="editar" size={13} />
                </button>
                {pctParam.referencia?.modificada && (
                  <button
                    type="button"
                    onClick={() => handleReestablecerRango(pctParam.codigo)}
                    title="Reestablecer a valor predeterminado del catálogo"
                    aria-label={`Restablecer referencia de ${nombreDiferencial}`}
                    className="lis-sheet-icon-btn"
                  >
                    <Icono nombre="restaurar" size={13} />
                  </button>
                )}
              </div>
            )}
          </div>
        </td>
        <td>{renderizarBanderaBadge(pctParam.bandera, pctParam.es_defecto && !pctParam.confirmado)}</td>
      </tr>
    );
  };

  // Renderizar fila estándar de parámetro
  const renderizarFilaParametro = (param: ParametroCaptura, soloTexto = false, ocultarNombre = false) => {
    const valorActual = valoresForm[param.codigo] !== undefined
      ? valoresForm[param.codigo]
      : param.valor || "";

    return (
      <tr key={param.codigo} className={param.es_calculado ? "lis-sheet-calculated-row" : undefined}>
        {!ocultarNombre && <td className="lis-sheet-parameter">
          <span style={{ fontWeight: 600 }}>{param.nombre}</span>
          {param.obligatorio && <span style={{ color: "var(--error)", marginLeft: "2px" }}>*</span>}
        </td>}
        <td className={param.es_calculado ? "lis-sheet-output" : "lis-sheet-entry"}>
          {param.es_calculado ? (
            <div style={{ textAlign: "right" }}>
              {param.calculable && param.valor !== null ? (
                <output className="lis-captura-calc-box" aria-label={`${param.nombre}: calculado`}>
                  {formatearValorVisual(param.valor)}
                </output>
              ) : (
                <output
                  className="lis-captura-calc-box is-unavailable"
                  title={param.motivo_no_calculable || "Esperando datos de entrada"}
                >
                  {param.motivo_no_calculable &&
                  !param.motivo_no_calculable.toLowerCase().includes("falta") &&
                  param.motivo_no_calculable !== "No calculable"
                    ? "No calculable"
                    : "Esperando datos"}
                </output>
              )}
            </div>
          ) : param.tipo_campo === "NUMERICO" ? (
            <EntradaResultadoNumerico
              id={`input-${param.codigo}`}
              className="lis-captura-input is-numeric"
              separadorDecimal={configLab.separador_decimal}
              value={valorActual}
              onValueChange={(valor) => manejarCambioCampo(param.codigo, valor)}
              onKeyDown={manejarKeyDownInput}
              onFocus={(event) => event.target.select()}
              disabled={esAdmin}
              maxLength={40}
              aria-label={param.nombre}
            />
          ) : param.tipo_campo === "SELECCION" ? (
            <div className="lis-combo-seleccion" style={{ display: "flex", alignItems: "center", gap: "4px" }}>
              <input
                id={`input-${param.codigo}`}
                type="text"
                className="lis-captura-input"
                placeholder={param.valor_defecto || "Elegir o escribir…"}
                value={valorActual}
                onChange={(e) => manejarCambioCampo(param.codigo, e.target.value)}
                onKeyDown={manejarKeyDownInput}
                onFocus={(e) => e.target.select()}
                disabled={esAdmin}
                maxLength={500}
                aria-label={param.nombre}
                style={{ flex: 1, minWidth: "120px" }}
              />
              {param.opciones && param.opciones.length > 0 && (
                <select
                  className="lis-captura-input"
                  style={{ width: "auto", minWidth: "85px", maxWidth: "150px", padding: "1px 4px", fontSize: "11px", cursor: "pointer" }}
                  value=""
                  onChange={(e) => {
                    if (e.target.value) manejarCambioCampo(param.codigo, e.target.value);
                  }}
                  disabled={esAdmin}
                  title={`Elegir opción para ${param.nombre}`}
                  aria-label={`Opciones para ${param.nombre}`}
                >
                  <option value="" disabled>▼ Elegir…</option>
                  {param.opciones.map((opt) => (
                    <option key={opt} value={opt}>
                      {opt}
                    </option>
                  ))}
                </select>
              )}
              {!esAdmin && !valorActual && param.valor_defecto && (
                <button
                  type="button"
                  className="lis-sheet-icon-btn lis-sample-accept"
                  title={`Aceptar sugerencia: ${param.valor_defecto}`}
                  aria-label={`Aceptar ${param.valor_defecto} para ${param.nombre}`}
                  onClick={() => manejarCambioCampo(param.codigo, param.valor_defecto || "")}
                >
                  <Icono nombre="correcto" size={14} />
                </button>
              )}
              {!esAdmin && valorActual && (
                <button
                  type="button"
                  className="lis-sheet-icon-btn"
                  title="Restablecer al valor predeterminado"
                  aria-label={`Restablecer ${param.nombre}`}
                  onClick={() => manejarCambioCampo(param.codigo, "")}
                >
                  <Icono nombre="restaurar" size={14} />
                </button>
              )}
            </div>
          ) : param.texto_sin_limite ? (
            <EntradaResultadoTexto
              id={`input-${param.codigo}`}
              value={valorActual}
              onValueChange={(valor) => manejarCambioCampo(param.codigo, valor)}
              onKeyDown={manejarKeyDownInput}
              disabled={esAdmin}
              aria-label={param.nombre}
            />
          ) : param.tipo_campo === "TEXTO" || param.tipo_campo === "TEXTO_LIBRE" ? (
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
              aria-label={param.nombre}
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
              aria-label={param.nombre}
            />
          ) : (
            <input
              id={`input-${param.codigo}`}
              type="text"
              className="lis-captura-input is-numeric"
              value={valorActual}
              onChange={(e) => manejarCambioCampo(param.codigo, e.target.value)}
              onKeyDown={manejarKeyDownInput}
              onFocus={(e) => e.target.select()}
              disabled={esAdmin}
              maxLength={param.tipo_campo === "RECUENTO" ? 50 : 25}
              aria-label={param.nombre}
            />
          )}
        </td>
        {!soloTexto && <><td className={param.unidad_editable ? "lis-sheet-entry" : undefined} style={{ fontSize: "12px", color: "var(--text-muted)" }}>
          {param.unidad_editable ? <input type="text" className="lis-captura-input"
            aria-label={`${param.nombre}: unidad`} value={unidadesForm[param.codigo] ?? param.unidad ?? ""}
            maxLength={30} disabled={esAdmin} onChange={(event) => manejarCambioUnidad(param.codigo, event.target.value)}
            onKeyDown={manejarKeyDownInput} />
            : ["FR_DILUCION", "ASTO_DILUCION"].includes(param.codigo) ? "" : (param.unidad || "—")}
        </td>
        <td style={{ fontSize: "11.5px", color: "var(--text-muted)" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "4px" }}>
            <span>
              {param.referencia?.texto || "—"}
            </span>
            {!esAdmin && (
              <div style={{ display: "flex", alignItems: "center", gap: "2px" }}>
                {param.referencia?.modificada && (
                  <span
                    className="lis-chip"
                    style={{ fontSize: "9px", padding: "0 4px", backgroundColor: "var(--warning-bg)", color: "var(--warning)" }}
                    title="Valor de referencia personalizado para esta orden"
                  >
                    Modificado
                  </span>
                )}
                <button
                  type="button"
                  onClick={() =>
                    setModalRangoAbierto({
                      codigo: param.codigo,
                      nombre: param.nombre,
                      inf: param.referencia?.inferior || "",
                      sup: param.referencia?.superior || "",
                      txt: param.referencia?.texto || "",
                      modificada: !!param.referencia?.modificada,
                    })
                  }
                  title="Editar valor de referencia para esta orden"
                  aria-label={`Editar referencia de ${param.nombre}`}
                  className="lis-sheet-icon-btn"
                >
                  <Icono nombre="editar" size={13} />
                </button>
                {param.referencia?.modificada && (
                  <button
                    type="button"
                    onClick={() => handleReestablecerRango(param.codigo)}
                    title="Reestablecer a valor predeterminado del catálogo"
                    aria-label={`Restablecer referencia de ${param.nombre}`}
                    className="lis-sheet-icon-btn"
                  >
                    <Icono nombre="restaurar" size={13} />
                  </button>
                )}
              </div>
            )}
          </div>
        </td>
        <td>{renderizarBanderaBadge(param.bandera, param.es_defecto && !param.confirmado)}</td></>}
      </tr>
    );
  };

  // Renderizar sección analítica
  const renderizarSeccion = (sec: SeccionCaptura) => {
    if (sec.formato === "MUESTRAS_SERIADAS") return <section key={sec.grupo || "muestras"} className="lis-sheet-section">
      <h4 className="lis-sheet-section-title">{sec.grupo?.replace(/_/g, " ")}</h4>
      {sec.parametros.map((param) => <MuestrasSeriadas key={param.codigo} parametro={param}
        valor={valoresForm[param.codigo] ?? param.valor ?? ""} soloLectura={esAdmin}
        onChange={manejarCambioCampo} onKeyDown={manejarKeyDownInput} />)}
    </section>;
    if (estudioActivo?.codigo === "INMUNOSEROLOGIA") return <SeccionInmunoserologia
      key={sec.grupo || "general"} seccion={sec} valores={valoresForm} soloLectura={esAdmin}
      separadorDecimal={configLab.separador_decimal} onChange={manejarCambioCampo} onKeyDown={manejarKeyDownInput}
    />;
    if (estudioActivo?.codigo === "COAGULOGRAMA" && sec.grupo === "GRUPO_SANGUINEO") return <SeccionGrupoSanguineo
      key={sec.grupo} seccion={sec} valores={valoresForm} soloLectura={esAdmin}
      onChange={manejarCambioCampo} onKeyDown={manejarKeyDownInput}
    />;
    const esEgoQuimico = estudioActivo?.codigo === "EGO" && sec.grupo === "QUIMICO";
    if (sec.formato === "SELECCION_SIMPLE" || esEgoQuimico) return (
      <section key={sec.grupo || "quimica"} className="lis-sheet-section">
        <h4 className="lis-sheet-section-title">{sec.grupo === "QUIMICO" ? "QUÍMICA" : sec.grupo?.replace(/_/g, " ")}</h4>
        <table className="lis-captura-tabla lis-lista-texto" aria-label={sec.grupo === "QUIMICO" ? "QUÍMICA" : sec.grupo?.replace(/_/g, " ") || estudioActivo?.nombre}>
          <thead><tr><th scope="col">Parámetro</th><th scope="col">Resultado</th></tr></thead>
          <tbody>{sec.parametros.map((param) => renderizarFilaParametro(param, true))}</tbody>
        </table>
      </section>
    );
    if (sec.formato === "LISTA_TEXTO") {
      const soloResultado = sec.grupo === "COPROPARASITOLOGICO_SIMPLE";
      return <section key={sec.grupo || "general"} className="lis-sheet-section">
        <h4 className="lis-sheet-section-title">{sec.grupo?.replace(/_/g, " ")}</h4>
        <table className={`lis-captura-tabla lis-lista-texto${soloResultado ? " is-solo-resultado" : ""}`} aria-label={sec.grupo?.replace(/_/g, " ")}>
          <thead><tr>{!soloResultado && <th scope="col">Campo</th>}<th scope="col">Resultado</th></tr></thead>
          <tbody>{sec.parametros.map((param) => renderizarFilaParametro(param, true, soloResultado))}</tbody>
        </table>
      </section>;
    }
    const esDiferencial = sec.grupo === "DIFERENCIAL";
    const sumaDiferencial = esDiferencial ? estudioActivo?.sumas?.find((suma) => suma.parametros.some((codigo) => sec.parametros.some((parametro) => parametro.codigo === codigo))) : undefined;

    return (
      <section key={sec.grupo || "general"} className="lis-sheet-section">
        {sec.grupo && (
          <h4 className="lis-sheet-section-title">
            {sec.grupo.replace(/_/g, " ")}
          </h4>
        )}
        <div className="lis-sheet-scroll"><table className={`lis-captura-tabla ${esDiferencial ? "lis-sheet-differential" : ""}`} aria-label={sec.grupo?.replace(/_/g, " ") || estudioActivo?.nombre}>
          <thead>
            <tr>
              <th scope="col" style={{ width: esDiferencial ? "26%" : "28%" }}>Parámetro</th>
              <th scope="col" className="lis-sheet-entry-heading" style={{ width: "22%" }}>{esDiferencial ? "Relativo (%)" : "Resultado"}</th>
              <th scope="col" style={{ width: esDiferencial ? "20%" : "10%" }}>{esDiferencial ? "Absoluto (/mm³)" : "Unidad"}</th>
              <th scope="col" style={{ width: esDiferencial ? "18%" : "26%" }}>{esDiferencial ? "V. Ref. (%)" : "V. Ref."}</th>
              <th scope="col" style={{ width: "14%" }}>Bandera</th>
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
        </table></div>
        {esDiferencial && (
          <div className={`lis-diferencial-suma ${sumaDiferencial?.valida ? "is-valid" : "is-warning"}`} aria-live="polite">
            <strong>Suma del diferencial: {formatearValorVisual(sumaDiferencial?.valor)} %</strong>
            <span>{sumaDiferencial?.valida ? "Diferencial dentro del intervalo esperado" : "Complete o revise el diferencial"}{sumaDiferencial ? ` (${sumaDiferencial.esperado} ± ${sumaDiferencial.tolerancia} %)` : ""}</span>
          </div>
        )}
      </section>
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
                {completitud.pendientes.length ? `Faltan ${completitud.pendientes.length}` : "Sin resultados"}
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
                  backgroundColor: "var(--bg-card)",
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
                {(estadoGuardado === "guardando" || estadoGuardado === "guardado") && <MarcaLaboratorio className="lis-save-mark" />}
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

              {/* Botón Publicar Informe Oficial */}
              {completitud.completo && captura?.orden?.estado_trabajo !== "PUBLICADA" && (
                <button
                  type="button"
                  className="lis-btn lis-btn-sm"
                  style={{ backgroundColor: "var(--action-bg)", color: "#ffffff", fontWeight: 700 }}
                  onClick={handleAbrirPublicar}
                  disabled={estadoGuardado === "guardando" || publicando}
                  title="Emitir informe oficial con folio secuencial inmutable"
                >
                  <Icono nombre="publicar" size={14} /> Publicar informe
                </button>
              )}

              {captura?.orden?.estado_trabajo === "PUBLICADA" && (
                <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                  <span className="lis-badge" style={{ backgroundColor: "var(--success-bg)", color: "var(--success)", fontWeight: 700 }}>
                    ✓ Publicada
                  </span>
                  <Link
                    to="/informes"
                    className="lis-btn lis-btn-outline lis-btn-sm"
                    style={{ fontWeight: 600 }}
                  >
                    Ver en Informes →
                  </Link>
                </div>
              )}
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
                  {/* Encabezado fijo y notificaciones fijas del estudio */}
                  <div className="lis-captura-sticky-header-group">
                    {(() => {
                      const conteo = calcularConteoEstudio(estudioActivo);
                      const idx = estudiosAsignados.findIndex((e) => e.codigo === estudioActivo.codigo);
                      return (
                        <div className="lis-captura-estudio-header">
                          <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
                            <span style={{ fontSize: "14px", fontWeight: 700 }}>
                              {idx + 1}. {estudioActivo.nombre}
                            </span>
                                <span
                              className="lis-chip"
                              style={{ fontSize: "11px", padding: "1px 6px", backgroundColor: "var(--bg-muted)" }}
                            >
                              Estudio {idx + 1} de {estudiosAsignados.length}
                            </span>
                            {estudioActivo.codigo === "INMUNOSEROLOGIA" && !esAdmin && (
                              <button
                                type="button"
                                className="lis-btn lis-btn-sm"
                                style={{
                                  fontSize: "11.5px",
                                  padding: "2px 8px",
                                  backgroundColor: "var(--primary-light)",
                                  borderColor: "var(--primary)",
                                  color: "var(--primary)",
                                  fontWeight: 700,
                                }}
                                onClick={() => {
                                  const existentes = new Set(
                                    estudioActivo.grupos_seleccionados ||
                                      estudioActivo.secciones.map((s) => s.grupo).filter(Boolean) as string[]
                                  );
                                  setGruposInmunoseroSeleccionados(existentes);
                                  setModalInmunoAbierto(true);
                                }}
                                title="Configurar qué subestudios de Inmunoserología se incluyen en la orden"
                              >
                                <Icono nombre="ajustes" size={14} /> Subestudios ({estudioActivo.grupos_seleccionados?.length || estudioActivo.secciones.length})
                              </button>
                            )}
                          </div>

                          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                            <span
                              className="lis-chip"
                              style={{
                                fontSize: "11px",
                                padding: "1px 6px",
                                backgroundColor:
                                  conteo.completos === conteo.total && conteo.total > 0
                                    ? "var(--success-bg, var(--success-bg))"
                                    : "var(--bg-hover)",
                                color:
                                  conteo.completos === conteo.total && conteo.total > 0
                                    ? "var(--success)"
                                    : "inherit",
                              }}
                            >
                              {conteo.completos}/{conteo.total} completados
                            </span>

                            {!esAdmin && (
                              <button
                                type="button"
                                className="lis-btn lis-btn-outline lis-btn-sm"
                                style={{
                                  fontSize: "11.5px",
                                  padding: "2px 8px",
                                  borderColor: "var(--error)",
                                  color: "var(--error)",
                                  fontWeight: 600,
                                }}
                                onClick={() => handleEliminarEstudio(estudioActivo)}
                                title="Eliminar este estudio de la orden"
                              >
                                <Icono nombre="eliminar" size={14} /> Eliminar estudio
                              </button>
                            )}
                          </div>
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
                  </div>

                  {/* Secciones y tabla de captura del estudio activo */}
                  <div className="lis-sheet-legend"><span><Icono nombre="tabla" size={13} /> Entrada editable</span><span><Icono nombre="calcular" size={13} /> Salida calculada</span><span>Tab / Enter · Siguiente campo</span></div>
                  <div style={{ padding: "6px" }}>
                    {estudioActivo.codigo === "CURVA_TOLERANCIA" ? (
                      <CurvaToleranciaCaptura
                        estudio={estudioActivo}
                        valores={valoresForm}
                        separadorDecimal={configLab.separador_decimal}
                        soloLectura={esAdmin}
                        onChange={manejarCambioCampo}
                        onChangeMany={manejarCambiosCampos}
                        onKeyDown={manejarKeyDownInput}
                      />
                    ) : estudioActivo.secciones.map((sec) => renderizarSeccion(sec))}
                  </div>

                  {/* Observaciones específicas por estudio */}
                  <div
                    style={{
                      margin: "12px 6px 6px 6px",
                      padding: "10px",
                      backgroundColor: "var(--bg-soft)",
                      borderRadius: "var(--radius)",
                      border: "1px solid var(--border-light)",
                    }}
                  >
                    <label
                      style={{
                        display: "block",
                        fontSize: "12px",
                        fontWeight: 700,
                        color: "var(--text-main)",
                        marginBottom: "4px",
                      }}
                    >
                      Observaciones del estudio ({estudioActivo.nombre}):
                    </label>
                    <textarea
                      className="lis-captura-input"
                      style={{ width: "100%", minHeight: "50px", resize: "vertical", fontSize: "12.5px" }}
                      placeholder="Observaciones analíticas o técnicas para este estudio…"
                      value={observacionesEstudios[estudioActivo.codigo] ?? (estudioActivo.observaciones || "")}
                      onChange={(e) => manejarCambioObservacionEstudio(estudioActivo.codigo, e.target.value)}
                      disabled={esAdmin}
                    />
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
              {/* Observaciones generales de la orden (para el informe final dentro del área scrollable) */}
              <div
                style={{
                  margin: "12px 6px 6px 6px",
                  padding: "10px",
                  backgroundColor: "var(--bg-hover)",
                  borderRadius: "var(--radius)",
                  border: "1px solid var(--border-color)",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                  <label style={{ fontSize: "12.5px", fontWeight: 700, color: "var(--text-main)" }}>
                    Observaciones finales de la orden (Impresión en informe final):
                  </label>
                  <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>Visible para médico y paciente</span>
                </div>
                <textarea
                  className="lis-captura-input"
                  style={{ width: "100%", minHeight: "55px", resize: "vertical", fontSize: "12.5px" }}
                  placeholder="Notas generales, comentarios clínicos o recomendaciones finales que se imprimirán en el informe oficial…"
                  value={observacionesOrden}
                  onChange={(e) => manejarCambioObservacionOrden(e.target.value)}
                  disabled={esAdmin}
                />
              </div>
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

              {/* Contenedor con Scroll Horizontal de Pestañas / Chips Numerados con soporte de rueda del mouse */}
              <div
                className="lis-captura-tabs-scroll"
                ref={tabsScrollRef}
                onWheel={(e) => {
                  if (e.deltaY !== 0) {
                    e.currentTarget.scrollLeft += e.deltaY;
                  }
                }}
              >
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

          {/* La vista previa se regenera desde los valores actuales, en hojas Carta. */}
          <div className="lis-captura-vista-previa">
            <VistaPreviaInforme
              ordenId={ordenId}
              payload={payloadVistaPrevia}
              habilitada={!cargando && captura.orden.estado_trabajo !== "PUBLICADA" && ordenDetalle?.estado_trabajo !== "PUBLICADA" && !captura.orden.bloqueada}
            />
          </div>
        </div>
      </form>

      {/* Modales auxiliares */}
      <ModalEditarRango
        abierto={!!modalRangoAbierto}
        parametro={modalRangoAbierto}
        onCerrar={() => setModalRangoAbierto(null)}
        onGuardar={handleGuardarRangoOverride}
        onReestablecer={handleReestablecerRango}
      />

      <ModalSeleccionarInmunosero
        abierto={modalInmunoAbierto}
        gruposSeleccionados={gruposInmunoseroSeleccionados}
        onToggleGrupo={(grupo) => {
          setGruposInmunoseroSeleccionados((prev) => {
            const next = new Set(prev);
            if (next.has(grupo)) next.delete(grupo);
            else next.add(grupo);
            return next;
          });
        }}
        onCerrar={() => setModalInmunoAbierto(false)}
        onGuardar={handleGuardarSubestudiosInmuno}
        estudioInmunoCatalogo={catalogoEstudios.find((c) => c.codigo === "INMUNOSEROLOGIA")}
      />


      {/* Modal de Publicación Oficial (Fase 4) */}
      {modalPublicarAbierto && (
        <div className="lis-modal-overlay">
          <div className="lis-modal-card" style={{ maxWidth: "520px" }}>
            <div className="lis-modal-header">
              <h3 className="lis-modal-title">
                {resultadoPublicacion ? "¡Orden Publicada Exitosamente!" : "Publicar Informe Oficial"}
              </h3>
              <button
                type="button"
                className="lis-btn-icon"
                onClick={() => {
                  setModalPublicarAbierto(false);
                  if (resultadoPublicacion) {
                    navigate(`/informes/${resultadoPublicacion.folio}`);
                  }
                }}
                disabled={publicando}
              >
                ✕
              </button>
            </div>

            <div className="lis-modal-body">
              {resultadoPublicacion ? (
                <div style={{ textAlign: "center", padding: "10px 0" }}>
                  <MarcaLaboratorio className="lis-publication-mark" />
                  <h4 style={{ color: "var(--action-bg)", marginBottom: "6px" }}>Documento Oficial Emitido</h4>
                  <div
                    style={{
                      fontFamily: "monospace",
                      fontSize: "20px",
                      fontWeight: 800,
                      color: "var(--error)",
                      backgroundColor: "var(--error-bg)",
                      padding: "8px 16px",
                      borderRadius: "4px",
                      display: "inline-block",
                      marginBottom: "12px",
                      border: "1px dashed #f87171",
                    }}
                  >
                    FOLIO: {resultadoPublicacion.folio}
                  </div>
                  <p style={{ fontSize: "12.5px", color: "var(--text-muted)", lineHeight: 1.5 }}>
                    El informe oficial ya está disponible para consulta e impresión con su folio.
                  </p>
                </div>
              ) : (
                <>
                  {publicando && <CargaLaboratorio mensaje="Emitiendo el informe oficial…" />}
                  <p style={{ fontSize: "13px", color: "var(--text-main)", marginBottom: "12px", lineHeight: 1.5 }}>
                    Está a punto de emitir el <strong>informe oficial inmutable</strong>. Una vez publicado, se le asignará un <strong>folio secuencial único</strong> y sus resultados quedarán congelados para impresión.
                  </p>

                  <p className="lis-input-hint">Se publican únicamente los campos utilizados. Las observaciones son opcionales.</p>

                  {errorPublicacion && (
                    <div className="lis-alert lis-alert-error" style={{ fontSize: "12.5px", marginBottom: "12px" }}>
                      {errorPublicacion}
                    </div>
                  )}

                  {usuario?.rol === "BIOQUIMICO" && ordenDetalle && ordenDetalle.autor?.id !== usuario?.id && (
                    <div className="lis-form-group" style={{ marginTop: "10px" }}>
                      <label className="lis-label" htmlFor="pub-urgencia-input">
                        Justificativo de Urgencia (No es el autor original de la orden):
                      </label>
                      <textarea
                        id="pub-urgencia-input"
                        className="lis-textarea"
                        rows={3}
                        placeholder="Indique el motivo de urgencia por el cual publica esta orden ajena…"
                        value={justificativoUrgenciaPub}
                        onChange={(e) => setJustificativoUrgenciaPub(e.target.value)}
                        disabled={publicando}
                      />
                    </div>
                  )}
                </>
              )}
            </div>

            <div className="lis-modal-footer">
              {resultadoPublicacion ? (
                <button
                  type="button"
                  className="lis-btn lis-btn-primary"
                  onClick={() => navigate(`/informes/${resultadoPublicacion.folio}`)}
                >
                  <Icono nombre="documento" size={16} /> Ver e imprimir informe oficial
                </button>
              ) : (
                <>
                  <button
                    type="button"
                    className="lis-btn lis-btn-outline"
                    onClick={() => setModalPublicarAbierto(false)}
                    disabled={publicando}
                  >
                    Cancelar
                  </button>
                  <button
                    type="button"
                    className="lis-btn"
                    style={{ backgroundColor: "var(--action-bg)", color: "#ffffff", fontWeight: 700 }}
                    onClick={handleConfirmarPublicacion}
                    disabled={publicando}
                  >
                    {publicando ? "Emitiendo Folio…" : "Confirmar y Publicar"}
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CapturaResultadosPage;
