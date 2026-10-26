/**
 * Vista de Detalle e Impresión del Informe Clínico Oficial (Fase 4).
 * Presenta el documento oficial inmutable generado a partir del snapshot JSON con huella SHA-256.
 * Optimizado para impresión física (@media print) con diseño sobrio y profesional.
 */
import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { getInforme, InformeDetalle } from "../../api/informes";
import { formatearResultadoClinico } from "../../utils/formatoNumerico";

export const InformeDetallePage: React.FC = () => {
  const { folio } = useParams<{ folio: string }>();

  const [informe, setInforme] = useState<InformeDetalle | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Versión seleccionada (si hay múltiples)
  const [versionSeleccionada, setVersionSeleccionada] = useState<number | undefined>(undefined);

  // Modal de Historial de Auditoría
  const [modalHistorialAbierto, setModalHistorialAbierto] = useState(false);

  const cargarDatos = async (v?: number) => {
    if (!folio) return;
    setCargando(true);
    setError(null);
    try {
      const data = await getInforme(folio, v);
      setInforme(data);
    } catch (err: any) {
      setError(err?.mensaje || "Error al cargar el informe clínico oficial.");
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => {
    cargarDatos(versionSeleccionada);
  }, [folio, versionSeleccionada]);

  if (cargando) {
    return (
      <div className="lis-page-container">
        <div style={{ padding: "60px", textAlign: "center", color: "var(--text-muted)" }}>
          Cargando informe oficial {folio}…
        </div>
      </div>
    );
  }

  if (error || !informe) {
    return (
      <div className="lis-page-container">
        <div className="lis-alert lis-alert-error" style={{ margin: "20px" }}>
          {error || "Informe no encontrado."}
        </div>
        <div style={{ padding: "0 20px" }}>
          <Link to="/informes" className="lis-btn lis-btn-outline">
            ← Volver a Informes
          </Link>
        </div>
      </div>
    );
  }

  const snapshot = informe.snapshot_json;
  const paciente = snapshot.paciente || {};
  const orden = snapshot.orden || {};
  const firmante = snapshot.firmante || {};
  const publicador = snapshot.publicador || {};
  const estudios = snapshot.estudios || [];

  const handleImprimir = () => {
    window.print();
  };

  const puedeImprimir = informe.estado === "VIGENTE";

  return (
    <div className="lis-page-container lis-informe-view">
      {/* Barra de Acciones Superior (Oculta en Impresión) */}
      <div className="lis-informe-actions-bar lis-no-print">
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <Link to="/informes" className="lis-btn lis-btn-outline lis-btn-sm">
            ← Volver
          </Link>

          {/* Selector de versión si existen múltiples */}
          {informe.versiones_disponibles.length > 1 && (
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <span style={{ fontSize: "12.5px", fontWeight: 600 }}>Versión:</span>
              <select
                className="lis-select"
                style={{ padding: "3px 8px", fontSize: "12.5px" }}
                value={informe.numero_version}
                onChange={(e) => setVersionSeleccionada(Number(e.target.value))}
              >
                {informe.versiones_disponibles.map((v) => (
                  <option key={v.numero_version} value={v.numero_version}>
                    V{v.numero_version} ({v.estado})
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Insignia de Estado */}
          <span
            className="lis-badge"
            style={{
              backgroundColor:
                informe.estado === "VIGENTE"
                  ? "#dcfce7"
                  : informe.estado === "RECICLAJE"
                  ? "#fef3c7"
                  : "#fee2e2",
              color:
                informe.estado === "VIGENTE"
                  ? "#166534"
                  : informe.estado === "RECICLAJE"
                  ? "#92400e"
                  : "#991b1b",
              fontWeight: 700,
            }}
          >
            {informe.estado}
          </span>

          {informe.es_urgencia && (
            <span className="lis-badge" style={{ backgroundColor: "#fee2e2", color: "#991b1b" }}>
              ⚠️ URGENCIA
            </span>
          )}
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <button
            type="button"
            className="lis-btn lis-btn-outline lis-btn-sm"
            onClick={() => setModalHistorialAbierto(true)}
            title="Ver auditoría y traza de cambios"
          >
            📜 Trazabilidad ({informe.eventos.length})
          </button>

          {puedeImprimir ? (
            <button
              type="button"
              className="lis-btn lis-btn-primary lis-btn-sm"
              onClick={handleImprimir}
              title="Imprimir informe oficial (Ctrl + P)"
            >
              🖨️ Imprimir Informe
            </button>
          ) : (
            <span
              style={{ fontSize: "12px", color: "var(--text-muted)", fontStyle: "italic" }}
              title="La impresión oficial está restringida para informes no vigentes"
            >
              Impresión bloqueada ({informe.estado})
            </span>
          )}
        </div>
      </div>

      {/* Documento Clínico Formal (A4 / Carta Listo para Imprimir) */}
      <div className="lis-informe-hoja">
        {/* Cabecera Institucional Metodista */}
        <header className="lis-informe-header">
          <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
            <img
              src="/logo-metodista.svg"
              alt="Hospital Metodista"
              style={{ width: "54px", height: "54px", objectFit: "contain" }}
            />
            <div>
              <h1
                style={{
                  fontFamily: "'Bernard MT Condensed', 'Arial Narrow', sans-serif, system-ui",
                  fontSize: "24px",
                  fontWeight: 700,
                  color: "#991b1b",
                  letterSpacing: "0.04em",
                  textTransform: "uppercase",
                  lineHeight: 1.1,
                }}
              >
                Hospital Metodista
              </h1>
              <div style={{ fontSize: "12px", color: "#475569", fontWeight: 600 }}>
                Departamento de Laboratorio Clínico y Análisis Bioquímicos
              </div>
              <div style={{ fontSize: "11px", color: "#64748b" }}>
                La Paz, Bolivia · Servicio 24 Horas
              </div>
            </div>
          </div>

          <div style={{ textAlign: "right" }}>
            <div
              style={{
                fontSize: "18px",
                fontWeight: 800,
                color: "#0f172a",
                fontFamily: "monospace",
                letterSpacing: "0.05em",
              }}
            >
              FOLIO: {informe.folio}
            </div>
            <div style={{ fontSize: "11.5px", fontWeight: 600, color: "#64748b" }}>
              Versión: V{informe.numero_version} ({informe.estado})
            </div>
            <div style={{ fontSize: "11px", color: "#64748b" }}>
              Emitido: {new Date(informe.publicado_en).toLocaleString("es-BO")}
            </div>
          </div>
        </header>

        <hr style={{ border: "none", borderTop: "2px solid #991b1b", margin: "10px 0" }} />

        {/* Ficha de Identificación del Paciente y la Muestra */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, 1fr)",
            gap: "8px 16px",
            backgroundColor: "#f8fafc",
            border: "1px solid #e2e8f0",
            borderRadius: "4px",
            padding: "10px 14px",
            fontSize: "12.5px",
            marginBottom: "16px",
          }}
        >
          <div>
            <span style={{ color: "#64748b", fontWeight: 600 }}>Paciente:</span>{" "}
            <strong>
              {paciente.nombres} {paciente.apellido_paterno} {paciente.apellido_materno || ""}
            </strong>
          </div>
          <div>
            <span style={{ color: "#64748b", fontWeight: 600 }}>C.I.:</span>{" "}
            <strong>{paciente.ci || "Sin documento"}</strong>
          </div>
          <div>
            <span style={{ color: "#64748b", fontWeight: 600 }}>Sexo / Edad:</span>{" "}
            <strong>
              {paciente.sexo === "M" ? "Masculino" : paciente.sexo === "F" ? "Femenino" : "—"} /{" "}
              {orden.edad_anios ? `${orden.edad_anios} años` : `${orden.edad_meses || 0} meses`}
            </strong>
          </div>

          <div>
            <span style={{ color: "#64748b", fontWeight: 600 }}>Médico Solicitante:</span>{" "}
            <span>{orden.medico_solicitante || "No especificado"}</span>
          </div>
          <div>
            <span style={{ color: "#64748b", fontWeight: 600 }}>Origen / Servicio:</span>{" "}
            <span>{orden.origen_solicitud || "Consulta Externa"}</span>
          </div>
          <div>
            <span style={{ color: "#64748b", fontWeight: 600 }}>Toma de Muestra:</span>{" "}
            <span>
              {orden.fecha_hora_toma_muestra
                ? new Date(orden.fecha_hora_toma_muestra).toLocaleString("es-BO")
                : "No registrada"}
            </span>
          </div>
        </div>

        {/* Resultados Clínicos por Estudio */}
        <main className="lis-informe-content">
          {estudios.map((est: any) => (
            <div key={est.codigo} style={{ marginBottom: "20px", pageBreakInside: "avoid" }}>
              <div
                style={{
                  backgroundColor: "#f1f5f9",
                  borderLeft: "4px solid #991b1b",
                  padding: "6px 12px",
                  fontSize: "13.5px",
                  fontWeight: 700,
                  color: "#0f172a",
                  textTransform: "uppercase",
                  marginBottom: "6px",
                }}
              >
                {est.nombre}
              </div>

              {est.secciones?.map((sec: any) => (
                <div key={sec.grupo} style={{ marginBottom: "10px" }}>
                  {sec.grupo !== "GENERAL" && (
                    <div
                      style={{
                        fontSize: "12px",
                        fontWeight: 700,
                        color: "#475569",
                        padding: "2px 6px",
                        backgroundColor: "#f8fafc",
                        borderBottom: "1px solid #e2e8f0",
                        marginBottom: "4px",
                      }}
                    >
                      {sec.grupo}
                    </div>
                  )}

                  <table
                    className="lis-table"
                    style={{ width: "100%", fontSize: "12px", marginBottom: "6px" }}
                  >
                    <thead>
                      <tr style={{ backgroundColor: "#f8fafc" }}>
                        <th style={{ width: "35%", textAlign: "left", padding: "4px 8px" }}>Análisis</th>
                        <th style={{ width: "22%", textAlign: "right", padding: "4px 8px" }}>Resultado</th>
                        <th style={{ width: "15%", textAlign: "left", padding: "4px 8px" }}>Unidad</th>
                        <th style={{ width: "20%", textAlign: "left", padding: "4px 8px" }}>Valores de Referencia</th>
                        <th style={{ width: "8%", textAlign: "center", padding: "4px 8px" }}>Alerta</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sec.parametros?.map((param: any) => {
                        const esAlerta = param.bandera === "ALTO" || param.bandera === "BAJO";
                        return (
                          <tr key={param.codigo} style={{ borderBottom: "1px solid #f1f5f9" }}>
                            <td style={{ fontWeight: 600, padding: "4px 8px" }}>{param.nombre}</td>
                            <td
                              style={{
                                textAlign: "right",
                                fontWeight: esAlerta ? 700 : 500,
                                color: esAlerta ? "#991b1b" : "inherit",
                                padding: "4px 8px",
                              }}
                            >
                              {param.valor !== null && param.valor !== undefined
                                ? formatearResultadoClinico(String(param.valor), ",")
                                : "—"}
                            </td>
                            <td style={{ color: "#64748b", padding: "4px 8px" }}>{param.unidad || "—"}</td>
                            <td style={{ color: "#475569", fontSize: "11px", padding: "4px 8px" }}>
                              {param.referencia?.texto || "—"}
                            </td>
                            <td style={{ textAlign: "center", padding: "4px 8px" }}>
                              {param.bandera === "ALTO" && (
                                <span style={{ color: "#991b1b", fontWeight: 700, fontSize: "11px" }}>
                                  ▲ ALTO
                                </span>
                              )}
                              {param.bandera === "BAJO" && (
                                <span style={{ color: "#1e40af", fontWeight: 700, fontSize: "11px" }}>
                                  ▼ BAJO
                                </span>
                              )}
                              {param.bandera === "NORMAL" && (
                                <span style={{ color: "#166534", fontSize: "11px" }}>Normal</span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ))}

              {/* Observaciones específicas del estudio si existen */}
              {est.observaciones && (
                <div
                  style={{
                    fontSize: "11.5px",
                    fontStyle: "italic",
                    backgroundColor: "#fefce8",
                    padding: "4px 8px",
                    borderRadius: "3px",
                    border: "1px dashed #fde047",
                    marginTop: "4px",
                  }}
                >
                  <strong>Observación ({est.nombre}):</strong> {est.observaciones}
                </div>
              )}
            </div>
          ))}

          {/* Observaciones Generales Obligatorias del Informe */}
          <div
            style={{
              marginTop: "16px",
              padding: "10px 14px",
              backgroundColor: "#f8fafc",
              border: "1px solid #cbd5e1",
              borderRadius: "4px",
              pageBreakInside: "avoid",
            }}
          >
            <div style={{ fontSize: "12px", fontWeight: 700, color: "#0f172a", marginBottom: "4px" }}>
              OBSERVACIONES CLÍNICAS Y CONCLUSIONES DEL INFORME:
            </div>
            <div style={{ fontSize: "12.5px", color: "#1e293b", whiteSpace: "pre-wrap" }}>
              {orden.observaciones || "Sin observaciones adicionales registradas."}
            </div>
          </div>
        </main>

        {/* Pie de Firma y Sello Digital */}
        <footer
          style={{
            marginTop: "36px",
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "24px",
            alignItems: "flex-end",
            pageBreakInside: "avoid",
          }}
        >
          {/* Huella Criptográfica SHA-256 */}
          <div style={{ fontSize: "10.5px", color: "#64748b", lineHeight: 1.4 }}>
            <div style={{ display: "flex", alignItems: "center", gap: "4px", fontWeight: 600, color: "#0f172a" }}>
              <span>🔒 Verificación Criptográfica de Autenticidad:</span>
            </div>
            <div style={{ fontFamily: "monospace", fontSize: "9.5px", wordBreak: "break-all", marginTop: "2px" }}>
              SHA-256: {informe.snapshot_sha256}
            </div>
            <div style={{ marginTop: "4px" }}>
              Firmante legal: <strong>{firmante.nombres} {firmante.apellido_paterno}</strong> · Matrícula:{" "}
              {firmante.matricula_profesional || "S/M"}
            </div>
          </div>

          {/* Recuadro de Firma y Sello */}
          <div style={{ textAlign: "center" }}>
            <div style={{ width: "240px", margin: "0 auto", borderBottom: "1px solid #0f172a", marginBottom: "6px" }} />
            <div style={{ fontSize: "12px", fontWeight: 700, color: "#0f172a" }}>
              {firmante.nombres} {firmante.apellido_paterno}
            </div>
            <div style={{ fontSize: "11px", color: "#475569" }}>
              Bioquímico(a) Responsable · Mat. {firmante.matricula_profesional || "S/M"}
            </div>
            <div style={{ fontSize: "10px", color: "#94a3b8" }}>Firma y Sello Profesional</div>
          </div>
        </footer>
      </div>

      {/* Modal Historial de Auditoría */}
      {modalHistorialAbierto && (
        <div className="lis-modal-overlay">
          <div className="lis-modal-card" style={{ maxWidth: "600px" }}>
            <div className="lis-modal-header">
              <h3 className="lis-modal-title">Traza de Auditoría del Folio {informe.folio}</h3>
              <button
                type="button"
                className="lis-btn-icon"
                onClick={() => setModalHistorialAbierto(false)}
              >
                ✕
              </button>
            </div>

            <div className="lis-modal-body">
              <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                {informe.eventos.map((ev, idx) => (
                  <div
                    key={ev.id_evento}
                    style={{
                      borderLeft: "3px solid var(--primary)",
                      padding: "6px 12px",
                      backgroundColor: "#f8fafc",
                      borderRadius: "0 4px 4px 0",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span className="lis-badge" style={{ fontWeight: 700, fontSize: "11px" }}>
                        {ev.accion}
                      </span>
                      <span style={{ fontSize: "11.5px", color: "var(--text-muted)" }}>
                        {new Date(ev.creado_en).toLocaleString("es-BO")}
                      </span>
                    </div>
                    <div style={{ fontSize: "12.5px", marginTop: "4px" }}>
                      <strong>Usuario:</strong> {ev.usuario_nombre}
                      {ev.numero_version && <span> · Versión V{ev.numero_version}</span>}
                    </div>
                    {ev.justificativo && (
                      <div style={{ fontSize: "12px", color: "#334155", fontStyle: "italic", marginTop: "2px" }}>
                        "{ev.justificativo}"
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>

            <div className="lis-modal-footer">
              <button
                type="button"
                className="lis-btn lis-btn-outline"
                onClick={() => setModalHistorialAbierto(false)}
              >
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
