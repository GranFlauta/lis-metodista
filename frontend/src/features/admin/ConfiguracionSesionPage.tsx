/**
 * Pantalla de Configuración de Sesión Dinámica (Solo ADMIN).
 * PROMPT_FASE_3_5_CORRECCIONES.md T5 punto 8:
 * - 4 campos con unidades, rango y ayuda breve.
 * - Guarda con confirmación y muestra los valores vigentes.
 * - Sin almacenamiento persistente en cliente (token en memoria).
 * - Diseñado según docs/UX_GUIDE.md (minimalista, funcional, sin emojis).
 */

import React, { useEffect, useState, useCallback } from "react";
import { getSesionConfigApi, updateSesionConfigApi, SesionConfig } from "../../api/auth";
import { ApiError } from "../../api/client";

export const ConfiguracionSesionPage: React.FC = () => {
  const [configVigente, setConfigVigente] = useState<SesionConfig | null>(null);
  const [cargando, setCargando] = useState<boolean>(true);
  const [guardando, setGuardando] = useState<boolean>(false);
  const [mensajeExito, setMensajeExito] = useState<string | null>(null);
  const [mensajeError, setMensajeError] = useState<string | null>(null);

  // Valores del formulario
  const [intervaloSeg, setIntervaloSeg] = useState<number>(30);
  const [muertaSeg, setMuertaSeg] = useState<number>(150);
  const [inactividadMin, setInactividadMin] = useState<number>(30);
  const [topeHoras, setTopeHoras] = useState<number>(12);

  // Diálogo de confirmación
  const [mostrarConfirmacion, setMostrarConfirmacion] = useState<boolean>(false);

  const cargarConfig = useCallback(async () => {
    setCargando(true);
    setMensajeError(null);
    try {
      const data = await getSesionConfigApi();
      setConfigVigente(data);
      setIntervaloSeg(data.sesion_intervalo_latido_seg);
      setMuertaSeg(data.sesion_muerta_tras_seg);
      setInactividadMin(data.sesion_inactividad_min);
      setTopeHoras(data.sesion_tope_absoluto_horas);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setMensajeError(err.message);
      } else {
        setMensajeError("Error al cargar la configuración de sesión.");
      }
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    cargarConfig();
  }, [cargarConfig]);

  const validarFormularioLocal = (): string | null => {
    if (intervaloSeg < 10 || intervaloSeg > 120) {
      return "El intervalo de latido debe estar comprendido entre 10 y 120 segundos.";
    }
    const minimoMuerta = 3 * intervaloSeg;
    if (muertaSeg < minimoMuerta || muertaSeg > 1800) {
      return `El tiempo de sesión muerta debe ser mayor o igual a 3 veces el intervalo (${minimoMuerta} s) y menor o igual a 1800 s.`;
    }
    if (inactividadMin < 5 || inactividadMin > 480) {
      return "El límite de inactividad debe estar comprendido entre 5 y 480 minutos.";
    }
    if (topeHoras < 1 || topeHoras > 24) {
      return "El tope absoluto de sesión debe estar comprendido entre 1 y 24 horas.";
    }
    return null;
  };

  const handlePreGuardar = (e: React.FormEvent) => {
    e.preventDefault();
    setMensajeExito(null);
    setMensajeError(null);

    const errorValidacion = validarFormularioLocal();
    if (errorValidacion) {
      setMensajeError(errorValidacion);
      return;
    }

    setMostrarConfirmacion(true);
  };

  const handleConfirmarGuardado = async () => {
    setMostrarConfirmacion(false);
    setGuardando(true);
    setMensajeError(null);
    setMensajeExito(null);

    const payload: SesionConfig = {
      sesion_intervalo_latido_seg: Number(intervaloSeg),
      sesion_muerta_tras_seg: Number(muertaSeg),
      sesion_inactividad_min: Number(inactividadMin),
      sesion_tope_absoluto_horas: Number(topeHoras),
    };

    try {
      const dataActualizada = await updateSesionConfigApi(payload);
      setConfigVigente(dataActualizada);
      setIntervaloSeg(dataActualizada.sesion_intervalo_latido_seg);
      setMuertaSeg(dataActualizada.sesion_muerta_tras_seg);
      setInactividadMin(dataActualizada.sesion_inactividad_min);
      setTopeHoras(dataActualizada.sesion_tope_absoluto_horas);
      setMensajeExito("Configuración de sesión guardada correctamente y vigente en el sistema.");
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setMensajeError(err.message);
      } else {
        setMensajeError("Error al guardar la configuración de sesión.");
      }
    } finally {
      setGuardando(false);
    }
  };

  return (
    <div className="lis-page-container" style={{ maxWidth: "960px", margin: "0 auto", padding: "16px" }}>
      <header className="lis-page-header" style={{ marginBottom: "20px" }}>
        <h1 style={{ fontSize: "20px", fontWeight: 700, margin: "0 0 4px 0", color: "#111827" }}>
          Configuración de Tiempos de Sesión
        </h1>
        <p style={{ fontSize: "14px", color: "#4B5563", margin: 0 }}>
          Parámetros dinámicos de latido, inactividad y expiración de sesiones clínicas (Regla D35-02).
        </p>
      </header>

      {/* Alertas */}
      {mensajeExito && (
        <div
          role="status"
          style={{
            backgroundColor: "#DCFCE7",
            color: "#166534",
            border: "1px solid #86EFAC",
            borderRadius: "4px",
            padding: "10px 14px",
            marginBottom: "16px",
            fontSize: "14px",
          }}
        >
          {mensajeExito}
        </div>
      )}

      {mensajeError && (
        <div
          role="alert"
          style={{
            backgroundColor: "#FEE2E2",
            color: "#991B1B",
            border: "1px solid #FCA5A5",
            borderRadius: "4px",
            padding: "10px 14px",
            marginBottom: "16px",
            fontSize: "14px",
          }}
        >
          {mensajeError}
        </div>
      )}

      {cargando ? (
        <p style={{ fontSize: "14px", color: "#6B7280" }}>Cargando configuración vigente...</p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
          {/* Panel de Valores Vigentes */}
          <section
            style={{
              backgroundColor: "#F9FAFB",
              border: "1px solid #E5E7EB",
              borderRadius: "4px",
              padding: "16px",
            }}
          >
            <h2 style={{ fontSize: "15px", fontWeight: 600, margin: "0 0 12px 0", color: "#374151" }}>
              Valores Vigentes en Base de Datos
            </h2>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                gap: "12px",
                fontSize: "14px",
              }}
            >
              <div>
                <span style={{ color: "#6B7280", display: "block" }}>Intervalo de latido:</span>
                <strong style={{ color: "#111827" }}>
                  {configVigente?.sesion_intervalo_latido_seg ?? 30} s
                </strong>
              </div>
              <div>
                <span style={{ color: "#6B7280", display: "block" }}>Sesión muerta sin latido:</span>
                <strong style={{ color: "#111827" }}>
                  {configVigente?.sesion_muerta_tras_seg ?? 150} s
                </strong>
              </div>
              <div>
                <span style={{ color: "#6B7280", display: "block" }}>Límite de inactividad:</span>
                <strong style={{ color: "#111827" }}>
                  {configVigente?.sesion_inactividad_min ?? 30} min
                </strong>
              </div>
              <div>
                <span style={{ color: "#6B7280", display: "block" }}>Tope absoluto de sesión:</span>
                <strong style={{ color: "#111827" }}>
                  {configVigente?.sesion_tope_absoluto_horas ?? 12} h
                </strong>
              </div>
            </div>
          </section>

          {/* Formulario de Modificación */}
          <form
            onSubmit={handlePreGuardar}
            style={{
              backgroundColor: "#FFFFFF",
              border: "1px solid #E5E7EB",
              borderRadius: "4px",
              padding: "16px",
            }}
          >
            <h2 style={{ fontSize: "15px", fontWeight: 600, margin: "0 0 16px 0", color: "#374151" }}>
              Editar Parámetros de Sesión
            </h2>

            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              {/* Campo 1 */}
              <div>
                <label
                  htmlFor="intervalo_latido"
                  style={{ display: "block", fontSize: "14px", fontWeight: 600, color: "#374151", marginBottom: "4px" }}
                >
                  Intervalo de latido (segundos)
                </label>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <input
                    id="intervalo_latido"
                    type="number"
                    min={10}
                    max={120}
                    value={intervaloSeg}
                    onChange={(e) => setIntervaloSeg(parseInt(e.target.value, 10) || 0)}
                    required
                    style={{
                      width: "120px",
                      padding: "6px 8px",
                      fontSize: "14px",
                      border: "1px solid #D1D5DB",
                      borderRadius: "4px",
                    }}
                  />
                  <span style={{ fontSize: "14px", color: "#6B7280" }}>s (Rango permitido: 10 – 120 s)</span>
                </div>
                <small style={{ display: "block", color: "#6B7280", marginTop: "4px", fontSize: "13px" }}>
                  Frecuencia periódica de verificación de conexión activa que envía el navegador al servidor.
                </small>
              </div>

              {/* Campo 2 */}
              <div>
                <label
                  htmlFor="muerta_tras"
                  style={{ display: "block", fontSize: "14px", fontWeight: 600, color: "#374151", marginBottom: "4px" }}
                >
                  Muerte de sesión por falta de latido (segundos)
                </label>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <input
                    id="muerta_tras"
                    type="number"
                    min={30}
                    max={1800}
                    value={muertaSeg}
                    onChange={(e) => setMuertaSeg(parseInt(e.target.value, 10) || 0)}
                    required
                    style={{
                      width: "120px",
                      padding: "6px 8px",
                      fontSize: "14px",
                      border: "1px solid #D1D5DB",
                      borderRadius: "4px",
                    }}
                  />
                  <span style={{ fontSize: "14px", color: "#6B7280" }}>
                    s (Rango permitido: ≥ 3× intervalo [mínimo {Math.max(30, 3 * intervaloSeg)} s] y ≤ 1800 s)
                  </span>
                </div>
                <small style={{ display: "block", color: "#6B7280", marginTop: "4px", fontSize: "13px" }}>
                  Tiempo máximo que la sesión permanece viva sin recibir latidos (ej. tras cerrar la pestaña).
                </small>
              </div>

              {/* Campo 3 */}
              <div>
                <label
                  htmlFor="inactividad_min"
                  style={{ display: "block", fontSize: "14px", fontWeight: 600, color: "#374151", marginBottom: "4px" }}
                >
                  Límite de inactividad del usuario (minutos)
                </label>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <input
                    id="inactividad_min"
                    type="number"
                    min={5}
                    max={480}
                    value={inactividadMin}
                    onChange={(e) => setInactividadMin(parseInt(e.target.value, 10) || 0)}
                    required
                    style={{
                      width: "120px",
                      padding: "6px 8px",
                      fontSize: "14px",
                      border: "1px solid #D1D5DB",
                      borderRadius: "4px",
                    }}
                  />
                  <span style={{ fontSize: "14px", color: "#6B7280" }}>min (Rango permitido: 5 – 480 min)</span>
                </div>
                <small style={{ display: "block", color: "#6B7280", marginTop: "4px", fontSize: "13px" }}>
                  Tiempo máximo sin interacción física real (ratón, teclado o toque) antes de expirar la sesión.
                </small>
              </div>

              {/* Campo 4 */}
              <div>
                <label
                  htmlFor="tope_horas"
                  style={{ display: "block", fontSize: "14px", fontWeight: 600, color: "#374151", marginBottom: "4px" }}
                >
                  Tope absoluto de sesión (horas)
                </label>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <input
                    id="tope_horas"
                    type="number"
                    min={1}
                    max={24}
                    value={topeHoras}
                    onChange={(e) => setTopeHoras(parseInt(e.target.value, 10) || 0)}
                    required
                    style={{
                      width: "120px",
                      padding: "6px 8px",
                      fontSize: "14px",
                      border: "1px solid #D1D5DB",
                      borderRadius: "4px",
                    }}
                  />
                  <span style={{ fontSize: "14px", color: "#6B7280" }}>h (Rango permitido: 1 – 24 h)</span>
                </div>
                <small style={{ display: "block", color: "#6B7280", marginTop: "4px", fontSize: "13px" }}>
                  Tiempo de vida total máximo de la sesión; este nuevo tope se aplica a sesiones creadas tras el guardado.
                </small>
              </div>
            </div>

            <div style={{ marginTop: "20px", display: "flex", gap: "12px" }}>
              <button
                type="submit"
                disabled={guardando}
                className="lis-btn lis-btn-primary"
                style={{
                  backgroundColor: "#2563EB",
                  color: "#FFFFFF",
                  border: "none",
                  padding: "8px 16px",
                  borderRadius: "4px",
                  fontWeight: 600,
                  fontSize: "14px",
                  cursor: guardando ? "not-allowed" : "pointer",
                }}
              >
                {guardando ? "Guardando..." : "Guardar cambios"}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Modal accesible de confirmación antes de guardar */}
      {mostrarConfirmacion && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="titulo_confirmacion"
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(0, 0, 0, 0.4)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 10000,
          }}
        >
          <div
            style={{
              backgroundColor: "#FFFFFF",
              borderRadius: "4px",
              padding: "16px",
              maxWidth: "460px",
              width: "90%",
              boxShadow: "0 4px 6px -1px rgba(0,0,0,0.1)",
            }}
          >
            <h3
              id="titulo_confirmacion"
              style={{ fontSize: "16px", fontWeight: 700, margin: "0 0 12px 0", color: "#111827" }}
            >
              Confirmar cambio de configuración
            </h3>
            <p style={{ fontSize: "14px", color: "#4B5563", margin: "0 0 16px 0", lineHeight: "1.5" }}>
              ¿Confirma que desea aplicar los siguientes tiempos a las sesiones del laboratorio?
            </p>
            <ul style={{ fontSize: "13px", color: "#374151", margin: "0 0 16px 20px", padding: 0 }}>
              <li>Intervalo de latido: <strong>{intervaloSeg} s</strong></li>
              <li>Sesión muerta tras: <strong>{muertaSeg} s</strong></li>
              <li>Inactividad máxima: <strong>{inactividadMin} min</strong></li>
              <li>Tope absoluto: <strong>{topeHoras} h</strong></li>
            </ul>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px" }}>
              <button
                type="button"
                onClick={() => setMostrarConfirmacion(false)}
                className="lis-btn lis-btn-secondary"
                style={{
                  backgroundColor: "#E5E7EB",
                  color: "#374151",
                  border: "none",
                  padding: "6px 12px",
                  borderRadius: "4px",
                  fontSize: "14px",
                  fontWeight: 500,
                  cursor: "pointer",
                }}
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={handleConfirmarGuardado}
                className="lis-btn lis-btn-primary"
                style={{
                  backgroundColor: "#2563EB",
                  color: "#FFFFFF",
                  border: "none",
                  padding: "6px 12px",
                  borderRadius: "4px",
                  fontSize: "14px",
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                Confirmar y guardar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
