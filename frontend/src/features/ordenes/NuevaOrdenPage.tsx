/**
 * Asistente de Creación de Órdenes Clínicas (Fase 2 Bloque 5).
 * PROMPT_FASE_2.md §8.3, §9:
 * 1. Paciente: buscar existente o alta integrada con regla CI vs Sin CI.
 * 2. Perfil opcional con preselección de estudios y libertad de marcado/desmarcado.
 * 3. Selección granular por grupos para Inmunoserología (etiqueta provisional D2-09).
 * 4. Datos de la orden y cálculo automático de edad con fecha de nacimiento (D2-08).
 * 5. Detección de duplicados D2-04:
 *    - Advertencias de solapamiento parcial (revela autor y códigos).
 *    - Bloqueo 409 ORDEN_DUPLICADA_EN_CURSO (nombre de colega, sin saltarse bloqueo).
 */

import React, { useEffect, useState } from "react";
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
  AdvertenciaSolapamiento,
  crearOrdenApi,
  EstudioItemCreate,
  OrdenCreatePayload,
  OrdenDetalle,
} from "../../api/ordenes";
import { ApiError } from "../../api/client";

export const NuevaOrdenPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const idPacienteParam = searchParams.get("id_paciente");

  // Catálogo clínico
  const [estudiosCatalogo, setEstudiosCatalogo] = useState<EstudioCatalogo[]>([]);
  const [perfilesCatalogo, setPerfilesCatalogo] = useState<PerfilCatalogo[]>([]);
  const [cargandoCatalogo, setCargandoCatalogo] = useState<boolean>(true);

  // Sección 1: Paciente
  const [modoPaciente, setModoPaciente] = useState<"existente" | "nuevo">("existente");
  const [pacienteSeleccionado, setPacienteSeleccionado] = useState<PacienteDetalle | null>(null);

  // Búsqueda de paciente existente
  const [busquedaPaciente, setBusquedaPaciente] = useState<string>("");
  const [resultadosPacientes, setResultadosPacientes] = useState<PacienteDetalle[]>([]);
  const [buscandoPacientes, setBuscandoPacientes] = useState<boolean>(false);

  // Formulario de paciente nuevo integrado
  const [nuevoSinCi, setNuevoSinCi] = useState<boolean>(false);
  const [nuevoCi, setNuevoCi] = useState<string>("");
  const [nuevoCiComp, setNuevoCiComp] = useState<string>("");
  const [nuevoNombres, setNuevoNombres] = useState<string>("");
  const [nuevoPaterno, setNuevoPaterno] = useState<string>("");
  const [nuevoMaterno, setNuevoMaterno] = useState<string>("");
  const [nuevoSexo, setNuevoSexo] = useState<"M" | "F">("M");
  const [nuevoFechaNac, setNuevoFechaNac] = useState<string>("");
  const [nuevoTelefono, setNuevoTelefono] = useState<string>("");
  const [conflictoPacienteId, setConflictoPacienteId] = useState<number | null>(null);

  // Sección 2: Perfil y Estudios
  const [perfilSeleccionado, setPerfilSeleccionado] = useState<string>("");
  const [estudiosSeleccionados, setEstudiosSeleccionados] = useState<Set<string>>(new Set());
  const [gruposInmunosero, setGruposInmunosero] = useState<Set<string>>(new Set());

  // Sección 3: Datos de la Orden
  const [origenSolicitud, setOrigenSolicitud] = useState<string>("");
  const [medicoSolicitante, setMedicoSolicitante] = useState<string>("");
  const [pieza, setPieza] = useState<string>("");
  const [fechaTomaMuestra, setFechaTomaMuestra] = useState<string>("");
  const [edadAnios, setEdadAnios] = useState<string>("");
  const [edadMeses, setEdadMeses] = useState<string>("0");

  // Estado del proceso de creación
  const [enviando, setEnviando] = useState<boolean>(false);
  const [errorGlobal, setErrorGlobal] = useState<string | null>(null);

  // Estados de respuesta especial (D2-04 / D2-05)
  const [bloqueoDuplicado, setBloqueoDuplicado] = useState<{
    autor: { nombres: string; apellido_paterno: string };
    estudios: string[];
  } | null>(null);

  const [ordenCreadaExito, setOrdenCreadaExito] = useState<{
    orden: OrdenDetalle;
    advertencias: AdvertenciaSolapamiento[];
  } | null>(null);

  // 1. Cargar catálogo clínico al montar
  useEffect(() => {
    const cargarCat = async () => {
      setCargandoCatalogo(true);
      try {
        const [estData, perfData] = await Promise.all([
          obtenerEstudiosCatalogoApi(),
          obtenerPerfilesCatalogoApi(),
        ]);
        setEstudiosCatalogo(estData);
        setPerfilesCatalogo(perfData);
      } catch {
        setErrorGlobal("Error al cargar el catálogo de estudios y perfiles.");
      } finally {
        setCargandoCatalogo(false);
      }
    };
    cargarCat();
  }, []);

  // 2. Cargar paciente si viene en parámetro de URL
  useEffect(() => {
    if (idPacienteParam) {
      const cargarPac = async () => {
        try {
          const pac = await obtenerPacienteApi(Number(idPacienteParam));
          setPacienteSeleccionado(pac);
          setModoPaciente("existente");
        } catch {
          // Si falla, queda en modo normal
        }
      };
      cargarPac();
    }
  }, [idPacienteParam]);

  // 3. Debounce para búsqueda de paciente existente (300 ms)
  useEffect(() => {
    if (modoPaciente !== "existente" || pacienteSeleccionado) return;
    if (!busquedaPaciente.trim()) {
      setResultadosPacientes([]);
      return;
    }

    const timer = setTimeout(async () => {
      setBuscandoPacientes(true);
      try {
        const resp = await listarPacientesApi({ q: busquedaPaciente.trim(), limit: 5 });
        setResultadosPacientes(resp.items);
      } catch {
        setResultadosPacientes([]);
      } finally {
        setBuscandoPacientes(false);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [busquedaPaciente, modoPaciente, pacienteSeleccionado]);

  // Manejo de selección de perfil preconfigurado
  const handleSeleccionarPerfil = (codigoPerfil: string) => {
    setPerfilSeleccionado(codigoPerfil);
    if (!codigoPerfil) return;

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
    const copia = new Set(estudiosSeleccionados);
    if (copia.has(codigoEstudio)) {
      copia.delete(codigoEstudio);
      if (codigoEstudio === "INMUNOSEROLOGIA") {
        setGruposInmunosero(new Set());
      }
    } else {
      copia.add(codigoEstudio);
      // Si activa Inmunoserología y no tiene grupos, premarcar todos los grupos disponibles
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

    // Si tiene al menos un grupo marcado, asegura que Inmunoserología esté marcada
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

  // Determinar si el paciente tiene fecha de nacimiento
  const tieneFechaNacimiento = Boolean(
    (modoPaciente === "existente" && pacienteSeleccionado?.fecha_nacimiento) ||
    (modoPaciente === "nuevo" && nuevoFechaNac)
  );

  // Enviar formulario de creación de orden
  const handleSubmitOrden = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorGlobal(null);
    setBloqueoDuplicado(null);
    setConflictoPacienteId(null);

    // Validar selección de paciente
    if (modoPaciente === "existente" && !pacienteSeleccionado) {
      setErrorGlobal("Debe buscar y seleccionar un paciente para la orden.");
      return;
    }

    if (modoPaciente === "nuevo") {
      const nom = nuevoNombres.trim();
      const pat = nuevoPaterno.trim();
      if (!nom || !pat) {
        setErrorGlobal("Los nombres y apellido paterno son obligatorios para el paciente nuevo.");
        return;
      }
      if (!nuevoSinCi && (!nuevoCi.trim() || nuevoCi.trim().length < 5)) {
        setErrorGlobal("El número de CI debe tener entre 5 y 30 caracteres.");
        return;
      }
    }

    // Validar estudios
    if (estudiosSeleccionados.size === 0) {
      setErrorGlobal("Debe seleccionar al menos un estudio clínico para crear la orden.");
      return;
    }

    if (estudiosSeleccionados.has("INMUNOSEROLOGIA") && gruposInmunosero.size === 0) {
      setErrorGlobal("Debe marcar al menos un grupo para el estudio de Inmunoserología.");
      return;
    }

    // Validar edad si no tiene fecha de nacimiento
    if (!tieneFechaNacimiento) {
      const aniosNum = parseInt(edadAnios, 10);
      if (isNaN(aniosNum) || aniosNum < 0 || aniosNum > 130) {
        setErrorGlobal("La edad en años es obligatoria (entre 0 y 130) cuando el paciente no tiene fecha de nacimiento.");
        return;
      }
    }

    // Construir lista de estudios para el payload
    const estudiosPayload: EstudioItemCreate[] = Array.from(estudiosSeleccionados).map((codigo) => {
      if (codigo === "INMUNOSEROLOGIA") {
        return {
          codigo,
          grupos: Array.from(gruposInmunosero),
        };
      }
      return { codigo };
    });

    // Construir payload de paciente nuevo si aplica
    let pacientePayload: PacienteCreatePayload | null = null;
    if (modoPaciente === "nuevo") {
      pacientePayload = {
        sin_ci: nuevoSinCi,
        ci: nuevoSinCi ? null : nuevoCi.trim().replace(/\s+/g, "").toUpperCase(),
        ci_complemento: nuevoSinCi || !nuevoCiComp.trim() ? null : nuevoCiComp.trim().toUpperCase(),
        nombres: nuevoNombres.trim().replace(/\s+/g, " "),
        apellido_paterno: nuevoPaterno.trim().replace(/\s+/g, " "),
        apellido_materno: nuevoMaterno.trim() ? nuevoMaterno.trim().replace(/\s+/g, " ") : null,
        sexo: nuevoSexo,
        fecha_nacimiento: nuevoFechaNac || null,
        telefono: nuevoTelefono.trim() || null,
      };
    }

    const payload: OrdenCreatePayload = {
      id_paciente: modoPaciente === "existente" && pacienteSeleccionado ? pacienteSeleccionado.id : null,
      paciente: pacientePayload,
      perfil: perfilSeleccionado || null,
      estudios: estudiosPayload,
      origen_solicitud: origenSolicitud.trim() || null,
      medico_solicitante: medicoSolicitante.trim() || null,
      pieza: pieza.trim() || null,
      fecha_hora_toma_muestra: fechaTomaMuestra || null,
      edad_anios: tieneFechaNacimiento ? null : parseInt(edadAnios, 10),
      edad_meses: tieneFechaNacimiento ? null : parseInt(edadMeses, 10) || 0,
    };

    setEnviando(true);
    try {
      const resp = await crearOrdenApi(payload);
      if (resp.advertencias && resp.advertencias.length > 0) {
        setOrdenCreadaExito(resp);
      } else {
        navigate(`/ordenes/${resp.orden.id}`);
      }
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        if (err.status === 409 && err.codigo === "ORDEN_DUPLICADA_EN_CURSO") {
          const det = (err.extra as { detalle?: { autor: { nombres: string; apellido_paterno: string }; estudios: string[] } })?.detalle;
          if (det) {
            setBloqueoDuplicado(det);
          } else {
            setErrorGlobal(err.message);
          }
        } else if (err.status === 409 && err.codigo === "CONFLICTO") {
          const pacId = (err.extra as { paciente_existente_id?: number })?.paciente_existente_id;
          if (pacId) {
            setConflictoPacienteId(pacId);
          }
          setErrorGlobal(err.message);
        } else {
          setErrorGlobal(err.message);
        }
      } else {
        setErrorGlobal("Ocurrió un error inesperado al procesar la orden.");
      }
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div className="lis-page-container">
      <div className="lis-wizard-container">
        {/* Encabezado */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "1rem" }}>
          <div>
            <Link to="/ordenes" className="lis-btn lis-btn-text" style={{ paddingLeft: 0, marginBottom: "0.25rem", display: "inline-block" }}>
              ← Volver a Órdenes
            </Link>
            <h2>Asistente de Creación de Orden</h2>
            <p className="lis-page-sub">
              Solicitud de determinaciones clínicas, asignación de perfiles y verificación de duplicidad (D2-04).
            </p>
          </div>
        </div>

        {/* Banner de Bloqueo Estricto 409 ORDEN_DUPLICADA_EN_CURSO (D2-04) */}
        {bloqueoDuplicado && (
          <div className="lis-block-duplicate-card" role="alert">
            <h4>⛔ Trabajo Clínico Duplicado en Curso</h4>
            <p>
              El colega bioquímico <strong>{bloqueoDuplicado.autor.nombres} {bloqueoDuplicado.autor.apellido_paterno}</strong> ya tiene una orden activa
              en curso para este paciente que cubre los estudios solicitados:
            </p>
            <div className="lis-chips-container" style={{ margin: "0.25rem 0" }}>
              {bloqueoDuplicado.estudios.map((c) => (
                <span key={c} className="lis-chip" style={{ backgroundColor: "#fee2e2", color: "#991b1b", borderColor: "#fca5a5" }}>
                  {c}
                </span>
              ))}
            </div>
            <p style={{ fontSize: "0.85rem", marginTop: "0.25rem" }}>
              Por directiva clínica institucional (D2-04), la creación de esta orden ha sido bloqueada para evitar duplicación de trabajo y reactivos.
              Espere a que el autor responsable complete o descarte su borrador.
            </p>
          </div>
        )}

        {/* Banner de Advertencia de Solapamiento con Éxito (D2-04 / D2-05) */}
        {ordenCreadaExito && (
          <div className="lis-overlap-banner" role="status">
            <h4>⚠️ Advertencia de Solapamiento Clínico</h4>
            <p>
              La orden <strong>#{ordenCreadaExito.orden.numero_orden_paciente}</strong> fue registrada exitosamente como borrador, pero se detectaron estudios concurrentes
              en órdenes de otros colegas bioquímicos:
            </p>
            <ul style={{ paddingLeft: "1.2rem", margin: "0.25rem 0" }}>
              {ordenCreadaExito.advertencias.map((adv, idx) => (
                <li key={idx}>
                  Bioquímico(a) <strong>{adv.autor.nombres} {adv.autor.apellido_paterno}</strong> tiene en proceso:{" "}
                  <strong>{adv.estudios.join(", ")}</strong>.
                </li>
              ))}
            </ul>
            <div style={{ marginTop: "0.5rem" }}>
              <button
                type="button"
                className="lis-btn lis-btn-primary"
                onClick={() => navigate(`/ordenes/${ordenCreadaExito.orden.id}`)}
              >
                Continuar a la Orden Creada →
              </button>
            </div>
          </div>
        )}

        {/* Alerta de Error General */}
        {errorGlobal && <div className="lis-alert lis-alert-error">{errorGlobal}</div>}

        <form onSubmit={handleSubmitOrden} style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          {/* SECCIÓN 1: PACIENTE */}
          <div className="lis-wizard-card">
            <div className="lis-wizard-header">
              <span className="lis-step-number">1</span>
              <h3>Identificación del Paciente</h3>
            </div>

            {/* Selector de Modo */}
            <div style={{ display: "flex", gap: "0.75rem", borderBottom: "1px solid #f1f5f9", paddingBottom: "0.75rem" }}>
              <label style={{ display: "flex", alignItems: "center", gap: "0.4rem", cursor: "pointer", fontWeight: 600 }}>
                <input
                  type="radio"
                  name="modo_paciente"
                  checked={modoPaciente === "existente"}
                  onChange={() => {
                    setModoPaciente("existente");
                    setErrorGlobal(null);
                  }}
                />
                Paciente Existente
              </label>

              <label style={{ display: "flex", alignItems: "center", gap: "0.4rem", cursor: "pointer", fontWeight: 600 }}>
                <input
                  type="radio"
                  name="modo_paciente"
                  checked={modoPaciente === "nuevo"}
                  onChange={() => {
                    setModoPaciente("nuevo");
                    setErrorGlobal(null);
                  }}
                />
                Nuevo Paciente (Alta Integrada en 1 Transacción)
              </label>
            </div>

            {/* Modo 1A: Paciente Existente */}
            {modoPaciente === "existente" && (
              <div>
                {pacienteSeleccionado ? (
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "1rem", backgroundColor: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: "var(--radius)" }}>
                    <div>
                      <span className="lis-status-badge lis-status-active" style={{ marginRight: "0.5rem" }}>
                        Seleccionado
                      </span>
                      <strong>{pacienteSeleccionado.apellido_paterno} {pacienteSeleccionado.apellido_materno || ""}, {pacienteSeleccionado.nombres}</strong>
                      <div style={{ fontSize: "0.85rem", color: "var(--text-muted)", marginTop: "0.2rem" }}>
                        {pacienteSeleccionado.sin_ci ? "Sin CI" : `CI: ${pacienteSeleccionado.ci}${pacienteSeleccionado.ci_complemento ? `-${pacienteSeleccionado.ci_complemento}` : ""}`} |{" "}
                        Sexo: {pacienteSeleccionado.sexo === "M" ? "Masculino" : "Femenino"} |{" "}
                        F. Nac: {pacienteSeleccionado.fecha_nacimiento || "No registrada"}
                      </div>
                    </div>
                    <button
                      type="button"
                      className="lis-btn lis-btn-outline lis-btn-sm"
                      onClick={() => setPacienteSeleccionado(null)}
                    >
                      Cambiar
                    </button>
                  </div>
                ) : (
                  <div>
                    <div className="lis-form-group">
                      <label htmlFor="input-buscar-paciente-orden">Buscar Paciente por CI o Nombre</label>
                      <input
                        id="input-buscar-paciente-orden"
                        type="search"
                        value={busquedaPaciente}
                        onChange={(e) => setBusquedaPaciente(e.target.value)}
                        placeholder="Escriba número de documento o apellidos..."
                        autoComplete="off"
                      />
                    </div>

                    {buscandoPacientes && <p style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>Buscando pacientes...</p>}

                    {resultadosPacientes.length > 0 && (
                      <div style={{ border: "1px solid var(--border-color)", borderRadius: "var(--radius)", marginTop: "0.5rem", overflow: "hidden" }}>
                        {resultadosPacientes.map((p) => (
                          <div
                            key={p.id}
                            style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0.65rem 1rem", borderBottom: "1px solid #f1f5f9" }}
                          >
                            <div>
                              <strong>{p.apellido_paterno} {p.apellido_materno || ""}, {p.nombres}</strong>
                              <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginLeft: "0.5rem" }}>
                                ({p.sin_ci ? "Sin CI" : `CI: ${p.ci}`})
                              </span>
                            </div>
                            <button
                              type="button"
                              className="lis-btn lis-btn-primary lis-btn-sm"
                              onClick={() => {
                                setPacienteSeleccionado(p);
                                setResultadosPacientes([]);
                                setBusquedaPaciente("");
                              }}
                            >
                              Seleccionar
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Modo 1B: Nuevo Paciente Integrado */}
            {modoPaciente === "nuevo" && (
              <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                {conflictoPacienteId && (
                  <div className="lis-conflict-banner">
                    <h4>⚠️ Cédula de Identidad ya registrada</h4>
                    <p>Ya existe un paciente con este CI. ¿Desea asociar la nueva orden al paciente existente?</p>
                    <button
                      type="button"
                      className="lis-btn lis-btn-primary lis-btn-sm"
                      onClick={async () => {
                        const pac = await obtenerPacienteApi(conflictoPacienteId);
                        setPacienteSeleccionado(pac);
                        setModoPaciente("existente");
                        setConflictoPacienteId(null);
                        setErrorGlobal(null);
                      }}
                    >
                      Usar Paciente Existente (#{conflictoPacienteId}) →
                    </button>
                  </div>
                )}

                <div style={{ backgroundColor: "#f8fafc", padding: "0.65rem 0.85rem", borderRadius: "var(--radius)", border: "1px solid var(--border-color)" }}>
                  <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer", fontWeight: 600 }}>
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
                    Paciente sin Carnet de Identidad (Sin CI)
                  </label>
                </div>

                <div className="lis-form-row">
                  <div className="lis-form-group" style={{ flex: 2 }}>
                    <label>CI {!nuevoSinCi && "*"}</label>
                    <input
                      type="text"
                      value={nuevoCi}
                      onChange={(e) => setNuevoCi(e.target.value.toUpperCase())}
                      disabled={nuevoSinCi}
                      placeholder={nuevoSinCi ? "Deshabilitado" : "Ej. 4839201"}
                      maxLength={30}
                    />
                  </div>
                  <div className="lis-form-group" style={{ flex: 1 }}>
                    <label>Complemento</label>
                    <input
                      type="text"
                      value={nuevoCiComp}
                      onChange={(e) => setNuevoCiComp(e.target.value.toUpperCase())}
                      disabled={nuevoSinCi}
                      placeholder="Ej. 1A"
                      maxLength={5}
                    />
                  </div>
                </div>

                <div className="lis-form-row">
                  <div className="lis-form-group">
                    <label>Apellido Paterno *</label>
                    <input
                      type="text"
                      value={nuevoPaterno}
                      onChange={(e) => setNuevoPaterno(e.target.value)}
                      placeholder="Ej. Flores"
                      maxLength={100}
                    />
                  </div>
                  <div className="lis-form-group">
                    <label>Apellido Materno</label>
                    <input
                      type="text"
                      value={nuevoMaterno}
                      onChange={(e) => setNuevoMaterno(e.target.value)}
                      placeholder="Ej. Vargas"
                      maxLength={100}
                    />
                  </div>
                </div>

                <div className="lis-form-group">
                  <label>Nombres *</label>
                  <input
                    type="text"
                    value={nuevoNombres}
                    onChange={(e) => setNuevoNombres(e.target.value)}
                    placeholder="Ej. Roberto"
                    maxLength={100}
                  />
                </div>

                <div className="lis-form-row">
                  <div className="lis-form-group">
                    <label>Sexo Biológico *</label>
                    <select value={nuevoSexo} onChange={(e) => setNuevoSexo(e.target.value as "M" | "F")}>
                      <option value="M">Masculino (M)</option>
                      <option value="F">Femenino (F)</option>
                    </select>
                  </div>
                  <div className="lis-form-group">
                    <label>Fecha de Nacimiento</label>
                    <input
                      type="date"
                      value={nuevoFechaNac}
                      onChange={(e) => setNuevoFechaNac(e.target.value)}
                      max={new Date().toISOString().split("T")[0]}
                    />
                  </div>
                  <div className="lis-form-group">
                    <label>Teléfono</label>
                    <input
                      type="text"
                      value={nuevoTelefono}
                      onChange={(e) => setNuevoTelefono(e.target.value)}
                      placeholder="Ej. 70012345"
                      maxLength={30}
                    />
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* SECCIÓN 2: PERFIL Y ESTUDIOS */}
          <div className="lis-wizard-card">
            <div className="lis-wizard-header">
              <span className="lis-step-number">2</span>
              <div style={{ flex: 1, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h3>Estudios Clínicos Solicitados</h3>
                <span className="lis-chip lis-chip-primary">
                  {estudiosSeleccionados.size} estudio(s) seleccionado(s)
                </span>
              </div>
            </div>

            {/* Selector de Perfil Opcional */}
            <div className="lis-form-group">
              <label htmlFor="select-perfil-asistente">Preseleccionar desde Perfil Clínico (Opcional)</label>
              <select
                id="select-perfil-asistente"
                value={perfilSeleccionado}
                onChange={(e) => handleSeleccionarPerfil(e.target.value)}
              >
                <option value="">— Selección Personalizada / Ningún perfil —</option>
                {perfilesCatalogo.map((perf) => (
                  <option key={perf.codigo} value={perf.codigo}>
                    {perf.nombre} ({perf.codigo})
                  </option>
                ))}
              </select>
              <span className="lis-input-hint">
                Al elegir un perfil se preseleccionan sus análisis, pudiendo marcar o desmarcar estudios de forma libre.
              </span>
            </div>

            {/* Cuadrícula de 9 Estudios */}
            {cargandoCatalogo ? (
              <p>Cargando estudios del catálogo...</p>
            ) : (
              <div className="lis-study-selection-grid">
                {estudiosCatalogo.map((est) => {
                  const estaMarcado = estudiosSeleccionados.has(est.codigo);
                  return (
                    <div
                      key={est.codigo}
                      className={`lis-study-checkbox-card ${estaMarcado ? "selected" : ""}`}
                      onClick={() => handleToggleEstudio(est.codigo)}
                    >
                      <div style={{ display: "flex", alignItems: "flex-start", gap: "0.6rem" }}>
                        <input
                          type="checkbox"
                          checked={estaMarcado}
                          onChange={() => {}} // Manejado por el onClick del contenedor
                          style={{ marginTop: "3px", width: "17px", height: "17px" }}
                        />
                        <div style={{ flex: 1 }}>
                          <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--text-muted)" }}>
                            {est.codigo}
                          </span>
                          <div style={{ fontWeight: 600, fontSize: "0.95rem" }}>{est.nombre}</div>
                          <span style={{ fontSize: "0.75rem", color: "var(--primary)" }}>{est.categoria}</span>
                        </div>
                      </div>

                      {/* Grupos de Inmunoserología (Etiqueta provisional D2-09) */}
                      {est.seleccion_parcial && est.grupos && estaMarcado && (
                        <div
                          className="lis-study-groups-box"
                          onClick={(e) => e.stopPropagation()} // Evita togglear el estudio al hacer clic en un grupo
                        >
                          <strong style={{ fontSize: "0.8rem", color: "var(--text-main)" }}>
                            Selección de Grupos (D2-09):
                          </strong>
                          {est.grupos.map((g) => {
                            const grupoMarcado = gruposInmunosero.has(g.codigo);
                            const etiquetaHumanizada = g.codigo.replace(/_/g, " ");
                            const nombresParametros = g.parametros.map((p) => p.nombre).join(", ");
                            return (
                              <label
                                key={g.codigo}
                                style={{
                                  display: "flex",
                                  flexDirection: "column",
                                  cursor: "pointer",
                                  padding: "0.3rem 0.4rem",
                                  backgroundColor: grupoMarcado ? "#f3e8ff" : "#f8fafc",
                                  borderRadius: "4px",
                                  border: "1px solid",
                                  borderColor: grupoMarcado ? "#d8b4fe" : "#e2e8f0",
                                }}
                              >
                                <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                                  <input
                                    type="checkbox"
                                    checked={grupoMarcado}
                                    onChange={() => handleToggleGrupoInmunosero(g.codigo)}
                                  />
                                  <span style={{ fontWeight: 600, fontSize: "0.85rem" }}>
                                    {etiquetaHumanizada}
                                  </span>
                                </div>
                                <span className="lis-input-hint" style={{ paddingLeft: "1.4rem", fontSize: "0.72rem" }}>
                                  {nombresParametros}
                                </span>
                              </label>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* SECCIÓN 3: DATOS DE LA ORDEN */}
          <div className="lis-wizard-card">
            <div className="lis-wizard-header">
              <span className="lis-step-number">3</span>
              <h3>Detalles Clínicos de la Solicitud</h3>
            </div>

            <div className="lis-form-row">
              <div className="lis-form-group">
                <label htmlFor="input-origen-orden">Origen de Solicitud</label>
                <input
                  id="input-origen-orden"
                  type="text"
                  value={origenSolicitud}
                  onChange={(e) => setOrigenSolicitud(e.target.value)}
                  placeholder="Ej. Emergencias, Consulta Externa, Sala 3..."
                  maxLength={100}
                />
              </div>

              <div className="lis-form-group">
                <label htmlFor="input-medico-orden">Médico Solicitante</label>
                <input
                  id="input-medico-orden"
                  type="text"
                  value={medicoSolicitante}
                  onChange={(e) => setMedicoSolicitante(e.target.value)}
                  placeholder="Ej. Dr. Carlos Fernández"
                  maxLength={150}
                />
              </div>
            </div>

            <div className="lis-form-row">
              <div className="lis-form-group">
                <label htmlFor="input-pieza-orden">Pieza / Cama</label>
                <input
                  id="input-pieza-orden"
                  type="text"
                  value={pieza}
                  onChange={(e) => setPieza(e.target.value)}
                  placeholder="Ej. Cama 12B"
                  maxLength={100}
                />
              </div>

              <div className="lis-form-group">
                <label htmlFor="input-toma-muestra-orden">Fecha y Hora de Toma de Muestra</label>
                <input
                  id="input-toma-muestra-orden"
                  type="datetime-local"
                  value={fechaTomaMuestra}
                  onChange={(e) => setFechaTomaMuestra(e.target.value)}
                />
              </div>
            </div>

            {/* Regla de Edad D2-08 */}
            {tieneFechaNacimiento ? (
              <div style={{ backgroundColor: "#f0f9ff", padding: "0.75rem 1rem", borderRadius: "var(--radius)", border: "1px solid #bae6fd", fontSize: "0.85rem", color: "#0369a1" }}>
                ℹ️ <strong>Cálculo de Edad Automático (D2-08):</strong> El paciente cuenta con fecha de nacimiento registrada.
                El servidor calculará automáticamente los años y meses cumplidos al momento de la orden.
              </div>
            ) : (
              <div className="lis-form-row">
                <div className="lis-form-group">
                  <label htmlFor="input-edad-anios">
                    Edad en Años <span style={{ color: "var(--error)" }}>*</span>
                  </label>
                  <input
                    id="input-edad-anios"
                    type="number"
                    min={0}
                    max={130}
                    value={edadAnios}
                    onChange={(e) => setEdadAnios(e.target.value)}
                    placeholder="0 - 130"
                    required
                  />
                  <span className="lis-input-hint">Obligatorio al no tener fecha de nacimiento.</span>
                </div>

                <div className="lis-form-group">
                  <label htmlFor="input-edad-meses">Edad en Meses (0–11)</label>
                  <input
                    id="input-edad-meses"
                    type="number"
                    min={0}
                    max={11}
                    value={edadMeses}
                    onChange={(e) => setEdadMeses(e.target.value)}
                    placeholder="0"
                  />
                </div>
              </div>
            )}
          </div>

          {/* Botones de Envío */}
          <div style={{ display: "flex", justifyContent: "flex-end", gap: "1rem" }}>
            <Link to="/ordenes" className="lis-btn lis-btn-secondary">
              Cancelar
            </Link>
            <button
              type="submit"
              className="lis-btn lis-btn-primary"
              disabled={enviando || estudiosSeleccionados.size === 0}
            >
              {enviando ? "Verificando y Creando..." : "Crear Orden de Laboratorio"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
