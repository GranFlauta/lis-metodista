/**
 * Formulario Modal para Alta y Edición de Pacientes.
 * PROMPT_FASE_2.md §8.2, §9:
 * - Regla excluyente: (sin_ci=true y ci=NULL) o (sin_ci=false y ci 5-30 caracteres).
 * - Normalización de mayúsculas en CI / complemento y colapso de espacios.
 * - Validación de fecha de nacimiento (no futura y no > 130 años).
 * - Manejo riguroso de HTTP 409 CONFLICTO con paciente_existente_id.
 */

import React, { useEffect, useState } from "react";
import {
  crearPacienteApi,
  editarPacienteApi,
  PacienteCreatePayload,
  PacienteDetalle,
  PacienteUpdatePayload,
} from "../../api/pacientes";
import { ApiError } from "../../api/client";

interface PacienteFormModalProps {
  abierto: boolean;
  pacienteEditando: PacienteDetalle | null;
  onCerrar: () => void;
  onGuardado: (paciente: PacienteDetalle) => void;
  onVerPacienteExistente?: (idPacienteExistente: number) => void;
}

export const PacienteFormModal: React.FC<PacienteFormModalProps> = ({
  abierto,
  pacienteEditando,
  onCerrar,
  onGuardado,
  onVerPacienteExistente,
}) => {
  const [sinCi, setSinCi] = useState<boolean>(false);
  const [ci, setCi] = useState<string>("");
  const [ciComplemento, setCiComplemento] = useState<string>("");
  const [nombres, setNombres] = useState<string>("");
  const [apellidoPaterno, setApellidoPaterno] = useState<string>("");
  const [apellidoMaterno, setApellidoMaterno] = useState<string>("");
  const [sexo, setSexo] = useState<"M" | "F">("M");
  const [fechaNacimiento, setFechaNacimiento] = useState<string>("");
  const [telefono, setTelefono] = useState<string>("");

  const [guardando, setGuardando] = useState<boolean>(false);
  const [errorValidacion, setErrorValidacion] = useState<string | null>(null);
  const [conflictoId, setConflictoId] = useState<number | null>(null);
  const [conflictoMensaje, setConflictoMensaje] = useState<string | null>(null);

  useEffect(() => {
    if (!abierto) return;

    setErrorValidacion(null);
    setConflictoId(null);
    setConflictoMensaje(null);

    if (pacienteEditando) {
      setSinCi(pacienteEditando.sin_ci);
      setCi(pacienteEditando.ci || "");
      setCiComplemento(pacienteEditando.ci_complemento || "");
      setNombres(pacienteEditando.nombres || "");
      setApellidoPaterno(pacienteEditando.apellido_paterno || "");
      setApellidoMaterno(pacienteEditando.apellido_materno || "");
      setSexo((pacienteEditando.sexo as "M" | "F") || "M");
      setFechaNacimiento(pacienteEditando.fecha_nacimiento || "");
      setTelefono(pacienteEditando.telefono || "");
    } else {
      setSinCi(false);
      setCi("");
      setCiComplemento("");
      setNombres("");
      setApellidoPaterno("");
      setApellidoMaterno("");
      setSexo("M");
      setFechaNacimiento("");
      setTelefono("");
    }
  }, [abierto, pacienteEditando]);

  if (!abierto) return null;

  const handleSinCiToggle = (checked: boolean) => {
    setSinCi(checked);
    if (checked) {
      setCi("");
      setCiComplemento("");
    }
    setErrorValidacion(null);
    setConflictoId(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorValidacion(null);
    setConflictoId(null);
    setConflictoMensaje(null);

    // Normalizaciones previas
    const nomNorm = nombres.trim().replace(/\s+/g, " ");
    const patNorm = apellidoPaterno.trim().replace(/\s+/g, " ");
    const matNorm = apellidoMaterno.trim().replace(/\s+/g, " ");
    const ciNorm = ci.trim().replace(/\s+/g, "").toUpperCase();
    const compNorm = ciComplemento.trim().replace(/\s+/g, "").toUpperCase();
    const telNorm = telefono.trim().replace(/\s+/g, " ");

    // Validaciones locales
    if (!nomNorm) {
      setErrorValidacion("El nombre es obligatorio.");
      return;
    }
    if (!patNorm) {
      setErrorValidacion("El apellido paterno es obligatorio.");
      return;
    }

    if (sinCi) {
      if (ciNorm) {
        setErrorValidacion("Un paciente marcado como 'Sin CI' no puede tener número de documento.");
        return;
      }
    } else {
      if (!ciNorm) {
        setErrorValidacion("El número de CI es obligatorio si el paciente no está marcado como 'Sin CI'.");
        return;
      }
      if (ciNorm.length < 5 || ciNorm.length > 30) {
        setErrorValidacion("El CI debe tener entre 5 y 30 caracteres.");
        return;
      }
      if (compNorm && compNorm.length > 5) {
        setErrorValidacion("El complemento de CI no puede superar 5 caracteres.");
        return;
      }
    }

    if (fechaNacimiento) {
      const hoy = new Date().toISOString().split("T")[0];
      if (fechaNacimiento > hoy) {
        setErrorValidacion("La fecha de nacimiento no puede ser futura.");
        return;
      }
      const anioMinimo = new Date().getFullYear() - 130;
      const anioIngresado = parseInt(fechaNacimiento.split("-")[0], 10);
      if (anioIngresado < anioMinimo) {
        setErrorValidacion("La fecha de nacimiento no puede ser anterior a 130 años.");
        return;
      }
    }

    setGuardando(true);
    try {
      if (pacienteEditando) {
        const payload: PacienteUpdatePayload = {
          sin_ci: sinCi,
          ci: sinCi ? null : ciNorm,
          ci_complemento: sinCi || !compNorm ? null : compNorm,
          nombres: nomNorm,
          apellido_paterno: patNorm,
          apellido_materno: matNorm || null,
          sexo,
          fecha_nacimiento: fechaNacimiento || null,
          telefono: telNorm || null,
        };
        const actualizado = await editarPacienteApi(pacienteEditando.id, payload);
        onGuardado(actualizado);
      } else {
        const payload: PacienteCreatePayload = {
          sin_ci: sinCi,
          ci: sinCi ? null : ciNorm,
          ci_complemento: sinCi || !compNorm ? null : compNorm,
          nombres: nomNorm,
          apellido_paterno: patNorm,
          apellido_materno: matNorm || null,
          sexo,
          fecha_nacimiento: fechaNacimiento || null,
          telefono: telNorm || null,
        };
        const creado = await crearPacienteApi(payload);
        onGuardado(creado);
      }
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        if (err.status === 409 && err.codigo === "CONFLICTO") {
          const idExistente = (err.extra as { paciente_existente_id?: number })?.paciente_existente_id;
          if (idExistente) {
            setConflictoId(idExistente);
            setConflictoMensaje(err.message);
          } else {
            setErrorValidacion(err.message);
          }
        } else {
          setErrorValidacion(err.message);
        }
      } else {
        setErrorValidacion("Ocurrió un error inesperado al guardar los datos del paciente.");
      }
    } finally {
      setGuardando(false);
    }
  };

  return (
    <div className="lis-modal-overlay" role="dialog" aria-modal="true" aria-labelledby="modal-paciente-title">
      <div className="lis-modal-card">
        <div className="lis-modal-header">
          <h3 id="modal-paciente-title">
            {pacienteEditando ? "Editar Ficha de Paciente" : "Registrar Nuevo Paciente"}
          </h3>
          <button type="button" className="lis-modal-close" onClick={onCerrar} aria-label="Cerrar modal">
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="lis-form">
          {errorValidacion && <div className="lis-alert lis-alert-error">{errorValidacion}</div>}

          {conflictoId && (
            <div className="lis-conflict-banner">
              <h4>⚠️ Paciente ya registrado</h4>
              <p>{conflictoMensaje || "Ya existe un paciente con este documento de identidad en el sistema."}</p>
              <div className="lis-conflict-actions">
                {onVerPacienteExistente && (
                  <button
                    type="button"
                    className="lis-btn lis-btn-primary lis-btn-sm"
                    onClick={() => onVerPacienteExistente(conflictoId)}
                  >
                    Usar Ficha del Paciente Existente (#{conflictoId}) →
                  </button>
                )}
                <button
                  type="button"
                  className="lis-btn lis-btn-outline lis-btn-sm"
                  onClick={() => setConflictoId(null)}
                >
                  Corregir Datos
                </button>
              </div>
            </div>
          )}

          {/* Opción Sin CI */}
          <div style={{ backgroundColor: "#f8fafc", padding: "0.75rem 1rem", borderRadius: "var(--radius)", border: "1px solid var(--border-color)" }}>
            <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer", fontWeight: 600 }}>
              <input
                type="checkbox"
                checked={sinCi}
                onChange={(e) => handleSinCiToggle(e.target.checked)}
                style={{ width: "18px", height: "18px" }}
              />
              Paciente sin Carnet de Identidad (Sin CI / Recién nacido / Indocumentado)
            </label>
            <span className="lis-input-hint" style={{ marginTop: "0.25rem", display: "block" }}>
              Al marcar esta casilla, no se exigirá documento y los campos de CI quedarán deshabilitados.
            </span>
          </div>

          {/* Documento de Identidad */}
          <div className="lis-form-row">
            <div className="lis-form-group" style={{ flex: 2 }}>
              <label htmlFor="paciente-ci">
                Cédula de Identidad (CI) {!sinCi && <span style={{ color: "var(--error)" }}>*</span>}
              </label>
              <input
                id="paciente-ci"
                type="text"
                value={ci}
                onChange={(e) => setCi(e.target.value.toUpperCase())}
                disabled={sinCi}
                placeholder={sinCi ? "Deshabilitado por Sin CI" : "Ej. 4839201"}
                maxLength={30}
              />
              <span className="lis-input-hint">Solo números/letras (5–30 caracteres).</span>
            </div>

            <div className="lis-form-group" style={{ flex: 1 }}>
              <label htmlFor="paciente-comp">Complemento (opcional)</label>
              <input
                id="paciente-comp"
                type="text"
                value={ciComplemento}
                onChange={(e) => setCiComplemento(e.target.value.toUpperCase())}
                disabled={sinCi}
                placeholder="Ej. 1A"
                maxLength={5}
              />
              <span className="lis-input-hint">Máx. 5 letras/números.</span>
            </div>
          </div>

          {/* Nombres y Apellidos */}
          <div className="lis-form-row">
            <div className="lis-form-group">
              <label htmlFor="paciente-paterno">
                Apellido Paterno <span style={{ color: "var(--error)" }}>*</span>
              </label>
              <input
                id="paciente-paterno"
                type="text"
                value={apellidoPaterno}
                onChange={(e) => setApellidoPaterno(e.target.value)}
                placeholder="Ej. Morales"
                maxLength={100}
                required
              />
            </div>

            <div className="lis-form-group">
              <label htmlFor="paciente-materno">Apellido Materno (opcional)</label>
              <input
                id="paciente-materno"
                type="text"
                value={apellidoMaterno}
                onChange={(e) => setApellidoMaterno(e.target.value)}
                placeholder="Ej. Rios"
                maxLength={100}
              />
            </div>
          </div>

          <div className="lis-form-group">
            <label htmlFor="paciente-nombres">
              Nombres <span style={{ color: "var(--error)" }}>*</span>
            </label>
            <input
              id="paciente-nombres"
              type="text"
              value={nombres}
              onChange={(e) => setNombres(e.target.value)}
              placeholder="Ej. Juan Carlos"
              maxLength={100}
              required
            />
          </div>

          {/* Sexo, Fecha de Nacimiento y Teléfono */}
          <div className="lis-form-row">
            <div className="lis-form-group" style={{ flex: 1 }}>
              <label htmlFor="paciente-sexo">
                Sexo Biológico <span style={{ color: "var(--error)" }}>*</span>
              </label>
              <select
                id="paciente-sexo"
                value={sexo}
                onChange={(e) => setSexo(e.target.value as "M" | "F")}
                required
              >
                <option value="M">Masculino (M)</option>
                <option value="F">Femenino (F)</option>
              </select>
            </div>

            <div className="lis-form-group" style={{ flex: 1 }}>
              <label htmlFor="paciente-fn">Fecha de Nacimiento</label>
              <input
                id="paciente-fn"
                type="date"
                value={fechaNacimiento}
                onChange={(e) => setFechaNacimiento(e.target.value)}
                max={new Date().toISOString().split("T")[0]}
              />
            </div>
          </div>

          <div className="lis-form-group">
            <label htmlFor="paciente-tel">Teléfono de Contacto (opcional)</label>
            <input
              id="paciente-tel"
              type="text"
              value={telefono}
              onChange={(e) => setTelefono(e.target.value)}
              placeholder="Ej. 70012345"
              maxLength={30}
            />
          </div>

          <div className="lis-modal-footer">
            <button type="button" className="lis-btn lis-btn-secondary" onClick={onCerrar} disabled={guardando}>
              Cancelar
            </button>
            <button type="submit" className="lis-btn lis-btn-primary" disabled={guardando}>
              {guardando ? "Guardando..." : pacienteEditando ? "Guardar Cambios" : "Crear Paciente"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
