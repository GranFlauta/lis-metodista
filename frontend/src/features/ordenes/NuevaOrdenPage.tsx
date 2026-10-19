/**
 * Creación de Órdenes Clínicas en una sola pantalla (3 zonas en fila).
 * PROMPT_FASE_3_6_UX.md §6.3 y §6.4, docs/UX_GUIDE.md §2.
 */

import React, { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  EstudioCatalogo,
  obtenerEstudiosCatalogoApi,
  obtenerPerfilesCatalogoApi,
  PerfilCatalogo,
} from "../../api/catalogo";
import {
  listarPacientesApi,
  obtenerPacienteApi,
  PacienteCreatePayload,
  PacienteDetalle,
} from "../../api/pacientes";
import {
  crearOrdenApi,
  EstudioItemCreate,
  OrdenCreatePayload,
} from "../../api/ordenes";
import { ApiError } from "../../api/client";

function obtenerFechaHoraActualLocal(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  const year = d.getFullYear();
  const month = pad(d.getMonth() + 1);
  const day = pad(d.getDate());
  const hours = pad(d.getHours());
  const minutes = pad(d.getMinutes());
  return `${year}-${month}-${day}T${hours}:${minutes}`;
}

function calcularEdadAnios(fechaNacimiento: string | null | undefined): number | null {
  if (!fechaNacimiento) return null;
  const nac = new Date(fechaNacimiento);
  if (isNaN(nac.getTime())) return null;
  const hoy = new Date();
  let anios = hoy.getFullYear() - nac.getFullYear();
  const m = hoy.getMonth() - nac.getMonth();
  if (m < 0 || (m === 0 && hoy.getDate() < nac.getDate())) {
    anios--;
  }
  return Math.max(0, anios);
}

export const NuevaOrdenPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const idPacienteParam = searchParams.get("id_paciente") || searchParams.get("pacienteId");

  // Catálogo clínico
  const [estudiosCatalogo, setEstudiosCatalogo] = useState<EstudioCatalogo[]>([]);
  const [perfilesCatalogo, setPerfilesCatalogo] = useState<PerfilCatalogo[]>([]);
  const [cargandoCatalogo, setCargandoCatalogo] = useState<boolean>(true);

  // Zona 1: Paciente
  const [modoCrearNuevo, setModoCrearNuevo] = useState<boolean>(false);
  const [pacienteSeleccionado, setPacienteSeleccionado] = useState<PacienteDetalle | null>(null);
  const [edadPacienteSeleccionadoManual, setEdadPacienteSeleccionadoManual] = useState<string>("");

  // Buscador de paciente
  const [busqueda, setBusqueda] = useState<string>("");
  const [resultadosBusqueda, setResultadosBusqueda] = useState<PacienteDetalle[]>([]);
  const [buscando, setBuscando] = useState<boolean>(false);

  // Formulario nuevo paciente
  const [nuevoSinCi, setNuevoSinCi] = useState<boolean>(false);
  const [nuevoCi, setNuevoCi] = useState<string>("");
  const [nuevoCiComp, setNuevoCiComp] = useState<string>("");
  const [nuevoNombres, setNuevoNombres] = useState<string>("");
  const [nuevoPaterno, setNuevoPaterno] = useState<string>("");
  const [nuevoMaterno, setNuevoMaterno] = useState<string>("");
  const [nuevoSexo, setNuevoSexo] = useState<"M" | "F">("M");
  const [nuevoFechaNac, setNuevoFechaNac] = useState<string>("");
  const [nuevoEdadAnios, setNuevoEdadAnios] = useState<string>("");
  const [conflictoPacienteId, setConflictoPacienteId] = useState<number | null>(null);

  // Zona 2: Perfil y Estudios
  const [perfilActivo, setPerfilActivo] = useState<string>("");
  const [estudiosSeleccionados, setEstudiosSeleccionados] = useState<Set<string>>(new Set());
  const [gruposInmunosero, setGruposInmunosero] = useState<Set<string>>(new Set());

  // Datos de la Orden
  const [medicoSolicitante, setMedicoSolicitante] = useState<string>("");
  const [pieza, setPieza] = useState<string>("");

  // Modal de confirmación (§6.4)
  const [modalAbierto, setModalAbierto] = useState<boolean>(false);
  const [fechaHoraInicio, setFechaHoraInicio] = useState<string>(obtenerFechaHoraActualLocal());
  const [guardando, setGuardando] = useState<boolean>(false);
  const [errorModal, setErrorModal] = useState<string | null>(null);
  const [bloqueoDuplicado, setBloqueoDuplicado] = useState<{
    autor: { nombres: string; apellido_paterno: string };
    estudios: string[];
  } | null>(null);

  const botonEmpezarRef = useRef<HTMLButtonElement | null>(null);

  // 1. Cargar catálogo clínico al montar
  useEffect(() => {
    let montado = true;
    async function cargarCat() {
      setCargandoCatalogo(true);
      try {
        const [estData, perfData] = await Promise.all([
          obtenerEstudiosCatalogoApi(),
          obtenerPerfilesCatalogoApi(),
        ]);
        if (montado) {
          setEstudiosCatalogo(estData);
          setPerfilesCatalogo(perfData);
        }
      } catch {
        // Silencioso o manejo local
      } finally {
        if (montado) {
          setCargandoCatalogo(false);
        }
      }
    }
    cargarCat();
    return () => {
      montado = false;
    };
  }, []);

  // 2. Cargar paciente si viene en parámetro de URL
  useEffect(() => {
    if (idPacienteParam) {
      let montado = true;
      async function cargarPac() {
        try {
          const pac = await obtenerPacienteApi(Number(idPacienteParam));
          if (montado) {
            setPacienteSeleccionado(pac);
            setModoCrearNuevo(false);
          }
        } catch {
          // Si falla, se ignora
        }
      }
      cargarPac();
      return () => {
        montado = false;
      };
    }
  }, [idPacienteParam]);

  // 3. Debounce para búsqueda única de paciente (300 ms)
  useEffect(() => {
    if (modoCrearNuevo || pacienteSeleccionado) return;
    if (!busqueda.trim()) {
      setResultadosBusqueda([]);
      return;
    }

    const timer = setTimeout(async () => {
      setBuscando(true);
      try {
        const resp = await listarPacientesApi({ q: busqueda.trim(), limit: 5 });
        setResultadosBusqueda(resp.items);
      } catch {
        setResultadosBusqueda([]);
      } finally {
        setBuscando(false);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [busqueda, modoCrearNuevo, pacienteSeleccionado]);

  // Foco en botón "Empezar a calcular" al abrir el modal
  useEffect(() => {
    if (modalAbierto) {
      const timer = setTimeout(() => {
        botonEmpezarRef.current?.focus();
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [modalAbierto]);

  // Manejo de tecla Escape para cerrar modal
  useEffect(() => {
    const manejarKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && modalAbierto && !guardando) {
        setModalAbierto(false);
      }
    };
    window.addEventListener("keydown", manejarKeyDown);
    return () => window.removeEventListener("keydown", manejarKeyDown);
  }, [modalAbierto, guardando]);

  // Preselección por botón de perfil (D36-02)
  const handleSeleccionarPerfil = (codigoPerfil: string) => {
    if (perfilActivo === codigoPerfil) {
      setPerfilActivo("");
      return;
    }
    setPerfilActivo(codigoPerfil);
    const perfil = perfilesCatalogo.find((p) => p.codigo === codigoPerfil);
    if (!perfil) return;

    const nuevosEstudios = new Set<string>();
    const nuevosGrupos = new Set<string>();

    for (const item of perfil.estudios) {
      nuevosEstudios.add(item.codigo);
      if (item.codigo === "INMUNOSEROLOGIA" && item.grupos) {
        for (const g of item.grupos) {
          nuevosGrupos.add(g);
        }
      }
    }

    setEstudiosSeleccionados(nuevosEstudios);
    setGruposInmunosero(nuevosGrupos);
  };

  // Toggle de estudio individual
  const handleToggleEstudio = (codigoEstudio: string) => {
    setPerfilActivo("");
    const copia = new Set(estudiosSeleccionados);
    if (copia.has(codigoEstudio)) {
      copia.delete(codigoEstudio);
      if (codigoEstudio === "INMUNOSEROLOGIA") {
        setGruposInmunosero(new Set());
      }
    } else {
      copia.add(codigoEstudio);
      if (codigoEstudio === "INMUNOSEROLOGIA") {
        const inmu = estudiosCatalogo.find((e) => e.codigo === "INMUNOSEROLOGIA");
        if (inmu?.grupos) {
          setGruposInmunosero(new Set(inmu.grupos.map((g) => g.codigo)));
        }
      }
    }
    setEstudiosSeleccionados(copia);
  };

  // Toggle de grupo de Inmunoserología
  const handleToggleGrupoInmunosero = (codigoGrupo: string) => {
    const copia = new Set(gruposInmunosero);
    if (copia.has(codigoGrupo)) {
      copia.delete(codigoGrupo);
    } else {
      copia.add(codigoGrupo);
    }
    setGruposInmunosero(copia);

    if (copia.size > 0 && !estudiosSeleccionados.has("INMUNOSEROLOGIA")) {
      const copiaEst = new Set(estudiosSeleccionados);
      copiaEst.add("INMUNOSEROLOGIA");
      setEstudiosSeleccionados(copiaEst);
    } else if (copia.size === 0 && estudiosSeleccionados.has("INMUNOSEROLOGIA")) {
      const copiaEst = new Set(estudiosSeleccionados);
      copiaEst.delete("INMUNOSEROLOGIA");
      setEstudiosSeleccionados(copiaEst);
    }
  };

  // Validación para habilitar el botón "Continuar"
  const pacienteValido = Boolean(
    (pacienteSeleccionado && (
      Boolean(pacienteSeleccionado.fecha_nacimiento) ||
      (edadPacienteSeleccionadoManual.trim() !== "" && !isNaN(parseInt(edadPacienteSeleccionadoManual, 10)) && parseInt(edadPacienteSeleccionadoManual, 10) >= 0 && parseInt(edadPacienteSeleccionadoManual, 10) <= 130)
    )) ||
    (modoCrearNuevo &&
      nuevoNombres.trim() &&
      nuevoPaterno.trim() &&
      (nuevoSinCi || nuevoCi.trim().length >= 5) &&
      (nuevoFechaNac || nuevoEdadAnios.trim()))
  );

  const estudiosValidos =
    estudiosSeleccionados.size > 0 &&
    (!estudiosSeleccionados.has("INMUNOSEROLOGIA") || gruposInmunosero.size > 0);

  const puedeContinuar = pacienteValido && estudiosValidos;

  // Abrir ventana modal de confirmación (§6.4)
  const handleContinuar = (e: React.FormEvent) => {
    e.preventDefault();
    if (!puedeContinuar) return;
    setErrorModal(null);
    setBloqueoDuplicado(null);
    setConflictoPacienteId(null);
    setFechaHoraInicio(obtenerFechaHoraActualLocal());
    setModalAbierto(true);
  };

  // Ejecutar creación real al pulsar "Empezar a calcular" en el modal
  const handleEmpezarCalculo = async () => {
    setErrorModal(null);
    setBloqueoDuplicado(null);
    setConflictoPacienteId(null);

    // 1. Estudios payload
    const estudiosPayload: EstudioItemCreate[] = Array.from(estudiosSeleccionados).map((codigo) => {
      if (codigo === "INMUNOSEROLOGIA") {
        return {
          codigo,
          grupos: Array.from(gruposInmunosero),
        };
      }
      return { codigo };
    });

    // 2. Paciente payload si es nuevo o edad manual
    let pacPayload: PacienteCreatePayload | null = null;
    let edadAniosFinal: number | null = null;

    if (modoCrearNuevo) {
      pacPayload = {
        sin_ci: nuevoSinCi,
        ci: nuevoSinCi ? null : nuevoCi.trim().replace(/\s+/g, "").toUpperCase(),
        ci_complemento: nuevoSinCi || !nuevoCiComp.trim() ? null : nuevoCiComp.trim().toUpperCase(),
        nombres: nuevoNombres.trim().replace(/\s+/g, " "),
        apellido_paterno: nuevoPaterno.trim().replace(/\s+/g, " "),
        apellido_materno: nuevoMaterno.trim() ? nuevoMaterno.trim().replace(/\s+/g, " ") : null,
        sexo: nuevoSexo,
        fecha_nacimiento: nuevoFechaNac || null,
        telefono: null,
      };
      if (!nuevoFechaNac && nuevoEdadAnios.trim()) {
        edadAniosFinal = parseInt(nuevoEdadAnios, 10);
      }
    } else if (pacienteSeleccionado) {
      if (!pacienteSeleccionado.fecha_nacimiento && edadPacienteSeleccionadoManual.trim()) {
        edadAniosFinal = parseInt(edadPacienteSeleccionadoManual, 10);
      }
    }

    const payload: OrdenCreatePayload = {
      id_paciente: pacienteSeleccionado ? pacienteSeleccionado.id : null,
      paciente: pacPayload,
      perfil: perfilActivo || null,
      estudios: estudiosPayload,
      origen_solicitud: null,
      medico_solicitante: medicoSolicitante.trim() || null,
      pieza: pieza.trim() || null,
      fecha_hora_toma_muestra: fechaHoraInicio ? new Date(fechaHoraInicio).toISOString() : null,
      edad_anios: edadAniosFinal,
      edad_meses: 0,
    };

    setGuardando(true);
    try {
      const resp = await crearOrdenApi(payload);
      setModalAbierto(false);
      // Navega directo a la captura de resultados (D36-02 / §6.4)
      navigate(`/ordenes/${resp.orden.id}/captura`, {
        state: { advertencias: resp.advertencias || [] },
      });
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        if (err.status === 409 && err.codigo === "ORDEN_DUPLICADA_EN_CURSO") {
          const det = (err.extra as { detalle?: { autor: { nombres: string; apellido_paterno: string }; estudios: string[] } })?.detalle;
          if (det) {
            setBloqueoDuplicado(det);
          } else {
            setErrorModal(err.message);
          }
        } else if (err.status === 409 && err.codigo === "CONFLICTO") {
          const pacId = (err.extra as { paciente_existente_id?: number })?.paciente_existente_id;
          if (pacId) {
            setConflictoPacienteId(pacId);
          }
          setErrorModal(err.message);
        } else {
          setErrorModal(err.message);
        }
      } else {
        setErrorModal("Error inesperado al registrar la orden.");
      }
    } finally {
      setGuardando(false);
    }
  };

  // Datos calculados para el resumen y confirmación
  const nombreCompleto = pacienteSeleccionado
    ? `${pacienteSeleccionado.apellido_paterno} ${pacienteSeleccionado.apellido_materno || ""}, ${pacienteSeleccionado.nombres}`
    : modoCrearNuevo
    ? `${nuevoPaterno} ${nuevoMaterno}, ${nuevoNombres}`
    : "Sin paciente";

  const ciMostrado = pacienteSeleccionado
    ? pacienteSeleccionado.sin_ci
      ? "Sin CI"
      : `CI ${pacienteSeleccionado.ci}${pacienteSeleccionado.ci_complemento ? `-${pacienteSeleccionado.ci_complemento}` : ""}`
    : modoCrearNuevo
    ? nuevoSinCi
      ? "Sin CI"
      : `CI ${nuevoCi}${nuevoCiComp ? `-${nuevoCiComp}` : ""}`
    : "—";

  const edadAniosCalculada = pacienteSeleccionado
    ? pacienteSeleccionado.fecha_nacimiento
      ? calcularEdadAnios(pacienteSeleccionado.fecha_nacimiento)
      : edadPacienteSeleccionadoManual.trim()
      ? parseInt(edadPacienteSeleccionadoManual, 10)
      : null
    : nuevoFechaNac
    ? calcularEdadAnios(nuevoFechaNac)
    : nuevoEdadAnios.trim()
    ? parseInt(nuevoEdadAnios, 10)
    : null;

  return (
    <div className="lis-page-container" style={{ padding: "0 0 24px 0" }}>
      <form onSubmit={handleContinuar} className="lis-nueva-orden-layout">
        {/* CABECERA SUPERIOR: SECCIÓN 1 (PACIENTE) Y SECCIÓN 2 (DATOS DE LA ORDEN) */}
        <div className="lis-nueva-orden-cabecera">
          {/* SECCIÓN 1: PACIENTE */}
          <section className="lis-cabecera-card lis-cabecera-paciente" aria-label="Sección 1: Paciente">
            <div className="lis-zone-header">
              <h2 className="lis-zone-title">
                <span className="lis-zone-badge">1</span>
                Paciente
              </h2>
              {pacienteSeleccionado && (
                <button
                  type="button"
                  className="lis-btn lis-btn-text lis-btn-sm"
                  onClick={() => {
                    setPacienteSeleccionado(null);
                    setEdadPacienteSeleccionadoManual("");
                  }}
                >
                  Cambiar
                </button>
              )}
            </div>

            <div className="lis-zone-content">
              {/* 1A: Paciente Seleccionado */}
              {pacienteSeleccionado ? (
                <div>
                  <div className="lis-paciente-compact-box">
                    <div className="lis-paciente-compact-header">
                      <span className="lis-paciente-compact-nombre">
                        {pacienteSeleccionado.apellido_paterno} {pacienteSeleccionado.apellido_materno || ""}, {pacienteSeleccionado.nombres}
                      </span>
                    </div>
                    <div className="lis-paciente-compact-meta">
                      <span>{pacienteSeleccionado.sin_ci ? "Sin CI" : `CI: ${pacienteSeleccionado.ci}${pacienteSeleccionado.ci_complemento ? `-${pacienteSeleccionado.ci_complemento}` : ""}`}</span>
                      <span>{pacienteSeleccionado.sexo === "M" ? "Masculino" : "Femenino"}</span>
                      {pacienteSeleccionado.fecha_nacimiento && edadAniosCalculada !== null && (
                        <span>{edadAniosCalculada} años</span>
                      )}
                    </div>
                  </div>

                  {/* Entrada directa y dinámica para edad en años si no tiene fecha de nacimiento */}
                  {!pacienteSeleccionado.fecha_nacimiento && (
                    <div
                      style={{
                        marginTop: "8px",
                        padding: "8px 12px",
                        backgroundColor: "#fff7ed",
                        border: "1.5px solid #fb923c",
                        borderRadius: "var(--radius)",
                        display: "flex",
                        flexDirection: "column",
                        gap: "6px",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "10px" }}>
                        <label
                          htmlFor="edad-paciente-manual-input"
                          style={{ fontSize: "12.5px", fontWeight: 700, color: "#9a3412" }}
                        >
                          Edad del paciente (años) *:
                        </label>
                        <input
                          id="edad-paciente-manual-input"
                          type="number"
                          min={0}
                          max={130}
                          value={edadPacienteSeleccionadoManual}
                          onChange={(e) => setEdadPacienteSeleccionadoManual(e.target.value)}
                          placeholder="Ej. 35"
                          required
                          autoFocus
                          style={{
                            width: "85px",
                            padding: "4px 8px",
                            fontSize: "14px",
                            fontWeight: 700,
                            textAlign: "center",
                            border: "1.5px solid #ea580c",
                            borderRadius: "var(--radius)",
                            backgroundColor: "#ffffff",
                          }}
                        />
                      </div>
                      <span style={{ fontSize: "11px", color: "#c2410c", fontWeight: 500 }}>
                        Paciente sin fecha de nacimiento registrada. Indique su edad en años para habilitar y calcular la orden.
                      </span>
                    </div>
                  )}
                </div>
              ) : !modoCrearNuevo ? (
                /* 1B: Buscador único de paciente */
                <div className="lis-paciente-search-wrap">
                  <label htmlFor="buscador-paciente-input" style={{ fontSize: "12.5px", fontWeight: 600 }}>
                    Buscar paciente existente
                  </label>
                  <input
                    id="buscador-paciente-input"
                    type="search"
                    value={busqueda}
                    onChange={(e) => setBusqueda(e.target.value)}
                    placeholder="CI o apellidos del paciente..."
                    autoComplete="off"
                    autoFocus
                    style={{ width: "100%" }}
                  />

                  {buscando && (
                    <span className="lis-text-muted" style={{ fontSize: "12px", marginTop: "4px" }}>
                      Buscando…
                    </span>
                  )}

                  {/* Dropdown de resultados */}
                  {resultadosBusqueda.length > 0 && (
                    <div className="lis-dropdown-results" role="listbox">
                      {resultadosBusqueda.map((p) => (
                        <div
                          key={p.id}
                          className="lis-dropdown-item"
                          onClick={() => {
                            setPacienteSeleccionado(p);
                            setResultadosBusqueda([]);
                            setBusqueda("");
                          }}
                          role="option"
                          aria-selected="false"
                        >
                          <div>
                            <strong>
                              {p.apellido_paterno} {p.apellido_materno || ""}, {p.nombres}
                            </strong>
                            <div className="lis-text-muted" style={{ fontSize: "11.5px" }}>
                              {p.sin_ci ? "Sin CI" : `CI: ${p.ci}`} • {p.sexo}
                            </div>
                          </div>
                          <span className="lis-btn lis-btn-secondary lis-btn-sm">Elegir</span>
                        </div>
                      ))}
                    </div>
                  )}

                  <div style={{ marginTop: "8px", borderTop: "1px dashed var(--border-light)", paddingTop: "6px" }}>
                    <button
                      type="button"
                      className="lis-btn lis-btn-text"
                      style={{ padding: 0, fontSize: "13px", fontWeight: 600 }}
                      onClick={() => {
                        setModoCrearNuevo(true);
                        setBusqueda("");
                        setResultadosBusqueda([]);
                      }}
                    >
                      + Crear paciente nuevo
                    </button>
                  </div>
                </div>
              ) : (
                /* 1C: Formulario compacto de paciente nuevo integrado */
                <div className="lis-nuevo-paciente-form">
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <strong>Nuevo paciente</strong>
                    <button
                      type="button"
                      className="lis-btn lis-btn-text lis-btn-sm"
                      onClick={() => setModoCrearNuevo(false)}
                    >
                      Volver a buscar
                    </button>
                  </div>

                  {conflictoPacienteId && (
                    <div className="lis-alert lis-alert-warning" style={{ padding: "6px 8px", fontSize: "12px" }}>
                      <span>CI ya registrado.</span>
                      <button
                        type="button"
                        className="lis-btn lis-btn-primary lis-btn-sm"
                        onClick={async () => {
                          const pac = await obtenerPacienteApi(conflictoPacienteId);
                          setPacienteSeleccionado(pac);
                          setModoCrearNuevo(false);
                          setConflictoPacienteId(null);
                        }}
                      >
                        Usar paciente existente
                      </button>
                    </div>
                  )}

                  <label style={{ display: "flex", alignItems: "center", gap: "6px", cursor: "pointer", fontSize: "12.5px" }}>
                    <input
                      type="checkbox"
                      checked={nuevoSinCi}
                      onChange={(e) => {
                        setNuevoSinCi(e.target.checked);
                        if (e.target.checked) {
                          setNuevoCi("");
                          setNuevoCiComp("");
                        }
                      }}
                    />
                    Sin Carnet de Identidad (Sin CI)
                  </label>

                  {!nuevoSinCi && (
                    <div className="lis-form-row">
                      <div>
                        <label style={{ fontSize: "11px" }}>CI *</label>
                        <input
                          type="text"
                          value={nuevoCi}
                          onChange={(e) => setNuevoCi(e.target.value.toUpperCase())}
                          placeholder="Número de CI"
                          required={!nuevoSinCi}
                          style={{ width: "100%", padding: "4px 8px" }}
                        />
                      </div>
                      <div>
                        <label style={{ fontSize: "11px" }}>Comp.</label>
                        <input
                          type="text"
                          value={nuevoCiComp}
                          onChange={(e) => setNuevoCiComp(e.target.value.toUpperCase())}
                          placeholder="Ej. 1A"
                          maxLength={5}
                          style={{ width: "100%", padding: "4px 8px" }}
                        />
                      </div>
                    </div>
                  )}

                  <div className="lis-form-row">
                    <div>
                      <label style={{ fontSize: "11px" }}>Paterno *</label>
                      <input
                        type="text"
                        value={nuevoPaterno}
                        onChange={(e) => setNuevoPaterno(e.target.value)}
                        placeholder="Ap. Paterno"
                        required
                        style={{ width: "100%", padding: "4px 8px" }}
                      />
                    </div>
                    <div>
                      <label style={{ fontSize: "11px" }}>Materno</label>
                      <input
                        type="text"
                        value={nuevoMaterno}
                        onChange={(e) => setNuevoMaterno(e.target.value)}
                        placeholder="Ap. Materno"
                        style={{ width: "100%", padding: "4px 8px" }}
                      />
                    </div>
                  </div>

                  <div>
                    <label style={{ fontSize: "11px" }}>Nombres *</label>
                    <input
                      type="text"
                      value={nuevoNombres}
                      onChange={(e) => setNuevoNombres(e.target.value)}
                      placeholder="Nombres completos"
                      required
                      style={{ width: "100%", padding: "4px 8px" }}
                    />
                  </div>

                  <div className="lis-form-row">
                    <div>
                      <label style={{ fontSize: "11px" }}>Sexo *</label>
                      <select
                        value={nuevoSexo}
                        onChange={(e) => setNuevoSexo(e.target.value as "M" | "F")}
                        style={{ width: "100%", padding: "4px 8px" }}
                      >
                        <option value="M">M</option>
                        <option value="F">F</option>
                      </select>
                    </div>
                    <div>
                      <label style={{ fontSize: "11px" }}>Fecha Nac. o Edad</label>
                      <input
                        type="date"
                        value={nuevoFechaNac}
                        onChange={(e) => setNuevoFechaNac(e.target.value)}
                        max={new Date().toISOString().split("T")[0]}
                        style={{ width: "100%", padding: "4px 8px" }}
                      />
                    </div>
                  </div>

                  {!nuevoFechaNac && (
                    <div>
                      <label style={{ fontSize: "11px" }}>Edad en Años *</label>
                      <input
                        type="number"
                        min={0}
                        max={130}
                        value={nuevoEdadAnios}
                        onChange={(e) => setNuevoEdadAnios(e.target.value)}
                        placeholder="0 - 130"
                        style={{ width: "100%", padding: "4px 8px" }}
                      />
                    </div>
                  )}
                </div>
              )}
            </div>
          </section>

          {/* SECCIÓN 2: DATOS DE LA ORDEN */}
          <section className="lis-cabecera-card lis-cabecera-orden" aria-label="Sección 2: Datos de la orden">
            <div className="lis-zone-header">
              <h2 className="lis-zone-title">
                <span className="lis-zone-badge">2</span>
                Datos de la Orden
              </h2>
              <span className={`lis-chip ${estudiosSeleccionados.size > 0 ? "lis-chip-primary" : ""}`}>
                {estudiosSeleccionados.size} estudios seleccionados
              </span>
            </div>

            <div className="lis-zone-content">
              <div className="lis-form-row" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
                <div className="lis-form-group">
                  <label htmlFor="input-medico" style={{ fontSize: "12px", fontWeight: 600 }}>
                    Médico solicitante
                  </label>
                  <input
                    id="input-medico"
                    type="text"
                    value={medicoSolicitante}
                    onChange={(e) => setMedicoSolicitante(e.target.value)}
                    placeholder="Ej. Dr. Mario Torres"
                    maxLength={150}
                    style={{ padding: "6px 10px", fontSize: "13px" }}
                  />
                </div>

                <div className="lis-form-group">
                  <label htmlFor="input-pieza" style={{ fontSize: "12px", fontWeight: 600 }}>
                    Pieza
                  </label>
                  <input
                    id="input-pieza"
                    type="text"
                    value={pieza}
                    onChange={(e) => setPieza(e.target.value)}
                    placeholder="Ej. Sala 2, Cama 4"
                    maxLength={100}
                    style={{ padding: "6px 10px", fontSize: "13px" }}
                  />
                </div>
              </div>

              {/* Resumen clínico superior */}
              <div className="lis-resumen-box" style={{ marginTop: "4px", padding: "8px 12px" }}>
                <div className="lis-resumen-row">
                  <span className="lis-resumen-label">Paciente:</span>
                  <span className="lis-resumen-val">{nombreCompleto}</span>
                </div>
                <div className="lis-resumen-row">
                  <span className="lis-resumen-label">Documento:</span>
                  <span className="lis-resumen-val">{ciMostrado}</span>
                </div>
              </div>

              {/* Botón principal Continuar en la cabecera */}
              <div style={{ marginTop: "auto", paddingTop: "6px" }}>
                <button
                  type="submit"
                  className="lis-btn lis-btn-primary lis-btn-block"
                  style={{ height: "42px", fontSize: "15px", fontWeight: 700 }}
                  disabled={!puedeContinuar}
                >
                  Continuar a confirmación →
                </button>
              </div>
            </div>
          </section>
        </div>

        {/* SECCIÓN 3: SELECCIÓN COMPLETA DE ESTUDIOS (ABAJO) */}
        <section className="lis-zone-card lis-nueva-orden-estudios" aria-label="Sección 3: Estudios">
          <div className="lis-zone-header">
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <h2 className="lis-zone-title">
                <span className="lis-zone-badge">3</span>
                Selección de Estudios del Laboratorio
              </h2>
              <span className="lis-chip lis-chip-primary">
                {estudiosSeleccionados.size} seleccionados
              </span>
            </div>

            {estudiosSeleccionados.size > 0 && (
              <button
                type="button"
                onClick={() => {
                  setEstudiosSeleccionados(new Set());
                  setGruposInmunosero(new Set());
                  setPerfilActivo("");
                }}
                className="lis-btn lis-btn-text lis-btn-sm"
                style={{ fontSize: "12px", color: "var(--danger)" }}
              >
                Limpiar selección
              </button>
            )}
          </div>

          <div className="lis-zone-content">
            {/* Botones de perfil rápido */}
            <div className="lis-perfiles-bar">
              <span style={{ fontSize: "12.5px", fontWeight: 700, color: "var(--text-muted)", marginRight: "6px" }}>
                Perfiles rápidos:
              </span>
              {perfilesCatalogo.map((perf) => (
                <button
                  key={perf.codigo}
                  type="button"
                  onClick={() => handleSeleccionarPerfil(perf.codigo)}
                  className={`lis-perfil-btn ${perfilActivo === perf.codigo ? "active" : ""}`}
                >
                  {perf.nombre}
                </button>
              ))}
            </div>

            {/* Cuadrícula de 9 interruptores amplios */}
            {cargandoCatalogo ? (
              <p className="lis-text-muted" style={{ fontSize: "13px" }}>
                Cargando catálogo…
              </p>
            ) : (
              <div className="lis-estudios-switches-grid">
                {estudiosCatalogo.map((est) => {
                  const seleccionado = estudiosSeleccionados.has(est.codigo);
                  return (
                    <React.Fragment key={est.codigo}>
                      <div
                        className={`lis-estudio-switch-item ${seleccionado ? "selected" : ""}`}
                        onClick={() => handleToggleEstudio(est.codigo)}
                        role="checkbox"
                        aria-checked={seleccionado}
                        tabIndex={0}
                        onKeyDown={(e) => {
                          if (e.key === " " || e.key === "Enter") {
                            e.preventDefault();
                            handleToggleEstudio(est.codigo);
                          }
                        }}
                      >
                        <div className="lis-switch-header">
                          <span className="lis-switch-code">{est.codigo}</span>
                          <input
                            type="checkbox"
                            checked={seleccionado}
                            onChange={() => {}}
                            tabIndex={-1}
                            style={{ cursor: "pointer" }}
                          />
                        </div>
                        <span className="lis-switch-name">{est.nombre}</span>
                      </div>

                      {/* Inmunoserología desplegada en línea */}
                      {est.codigo === "INMUNOSEROLOGIA" && seleccionado && est.grupos && (
                        <div className="lis-inmunosero-dropdown">
                          <span style={{ fontSize: "12.5px", fontWeight: 700, color: "#701a75" }}>
                            Grupos de Inmunoserología:
                          </span>
                          <div className="lis-inmunosero-grid">
                            {est.grupos.map((g) => {
                              const marcado = gruposInmunosero.has(g.codigo);
                              const etiquetaHumanizada = g.codigo.replace(/_/g, " ");
                              const paramsTexto = g.parametros.map((p) => p.nombre).join(", ");
                              return (
                                <label
                                  key={g.codigo}
                                  className={`lis-inmunosero-item ${marcado ? "selected" : ""}`}
                                  onClick={(e) => e.stopPropagation()}
                                >
                                  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                                    <input
                                      type="checkbox"
                                      checked={marcado}
                                      onChange={() => handleToggleGrupoInmunosero(g.codigo)}
                                    />
                                    <strong>{etiquetaHumanizada}</strong>
                                  </div>
                                  <span style={{ fontSize: "11px", color: "var(--text-muted)", paddingLeft: "20px" }}>
                                    {paramsTexto}
                                  </span>
                                </label>
                              );
                            })}
                          </div>
                        </div>
                      )}
                    </React.Fragment>
                  );
                })}
              </div>
            )}

            {/* Barra de acción inferior */}
            <div className="lis-estudios-footer-bar">
              <span className="lis-text-muted" style={{ fontSize: "13px" }}>
                {estudiosSeleccionados.size === 0
                  ? "Seleccione al menos un estudio clínico o perfil para habilitar la orden."
                  : `${estudiosSeleccionados.size} estudios seleccionados.`}
              </span>
              <button
                type="submit"
                className="lis-btn lis-btn-primary"
                style={{ height: "42px", padding: "0 28px", fontSize: "15px", fontWeight: 700 }}
                disabled={!puedeContinuar}
              >
                Continuar a confirmación →
              </button>
            </div>
          </div>
        </section>
      </form>

      {/* VENTANA MODAL DE CONFIRMACIÓN (§6.4) */}
      {modalAbierto && (
        <div className="lis-modal-overlay" role="dialog" aria-modal="true" aria-labelledby="modal-confirm-title">
          <div className="lis-modal-card lis-modal-confirmacion">
            <div className="lis-modal-header">
              <h3 id="modal-confirm-title">Confirmar y Crear Orden</h3>
              <button
                type="button"
                className="lis-modal-close"
                onClick={() => !guardando && setModalAbierto(false)}
                disabled={guardando}
              >
                ✕
              </button>
            </div>

            <div className="lis-modal-body">
              {/* Tarjeta de Bloqueo por Duplicidad (409 ORDEN_DUPLICADA_EN_CURSO) */}
              {bloqueoDuplicado && (
                <div className="lis-alert lis-alert-error" role="alert">
                  <div>
                    <strong>Trabajo clínico duplicado en curso</strong>
                    <p style={{ marginTop: "4px", fontSize: "12.5px" }}>
                      El colega bioquímico <strong>{bloqueoDuplicado.autor.nombres} {bloqueoDuplicado.autor.apellido_paterno}</strong> ya
                      posee una orden activa que cubre los estudios solicitados:
                    </p>
                    <div className="lis-chips-container" style={{ marginTop: "6px" }}>
                      {bloqueoDuplicado.estudios.map((c) => (
                        <span key={c} className="lis-chip">
                          {c}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {errorModal && !bloqueoDuplicado && (
                <div className="lis-alert lis-alert-error" role="alert">
                  {errorModal}
                </div>
              )}

              {/* Datos de Confirmación */}
              <div className="lis-confirm-summary-grid">
                <span className="lis-confirm-label">CI:</span>
                <span className="lis-confirm-value">{ciMostrado}</span>

                <span className="lis-confirm-label">Paciente:</span>
                <span className="lis-confirm-value">{nombreCompleto}</span>

                <span className="lis-confirm-label">Edad:</span>
                {(!pacienteSeleccionado?.fecha_nacimiento && !nuevoFechaNac) ? (
                  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                    <input
                      type="number"
                      min={0}
                      max={130}
                      value={edadPacienteSeleccionadoManual || nuevoEdadAnios}
                      onChange={(e) => {
                        setEdadPacienteSeleccionadoManual(e.target.value);
                        setNuevoEdadAnios(e.target.value);
                      }}
                      placeholder="Ej. 35"
                      style={{
                        width: "80px",
                        padding: "3px 6px",
                        fontSize: "13px",
                        fontWeight: 700,
                        textAlign: "center",
                        border: "1.5px solid var(--primary)",
                        borderRadius: "var(--radius)",
                      }}
                    />
                    <span style={{ fontSize: "12px", fontWeight: 600 }}>años</span>
                  </div>
                ) : (
                  <span className="lis-confirm-value">
                    {edadAniosCalculada !== null ? `${edadAniosCalculada} años` : "No registrada"}
                  </span>
                )}

                <span className="lis-confirm-label">Estudios:</span>
                <div className="lis-chips-container">
                  {Array.from(estudiosSeleccionados).map((cod) => (
                    <span key={cod} className="lis-chip lis-chip-primary">
                      {cod}
                    </span>
                  ))}
                </div>
              </div>

              {/* Fecha y hora de inicio (editable, precargada con ahora; D36-03) */}
              <div className="lis-form-group" style={{ marginTop: "6px" }}>
                <label htmlFor="input-hora-inicio-modal">
                  Fecha y hora de inicio
                </label>
                <input
                  id="input-hora-inicio-modal"
                  type="datetime-local"
                  value={fechaHoraInicio}
                  onChange={(e) => setFechaHoraInicio(e.target.value)}
                  disabled={guardando}
                  style={{ width: "100%" }}
                />
                <span className="lis-input-hint">
                  Registra el inicio de los estudios en el laboratorio.
                </span>
              </div>
            </div>

            <div className="lis-modal-footer">
              <button
                type="button"
                className="lis-btn lis-btn-secondary"
                onClick={() => setModalAbierto(false)}
                disabled={guardando}
              >
                Volver
              </button>

              {!bloqueoDuplicado && (
                <button
                  ref={botonEmpezarRef}
                  type="button"
                  className="lis-btn lis-btn-primary"
                  onClick={handleEmpezarCalculo}
                  disabled={guardando}
                >
                  {guardando ? "Creando orden…" : "Empezar a calcular"}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
