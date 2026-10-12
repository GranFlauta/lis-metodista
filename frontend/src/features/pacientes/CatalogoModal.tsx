/**
 * Modal de Consulta del Catálogo Clínico de Estudios y Perfiles.
 * PROMPT_FASE_2.md §8.1:
 * - Consulta GET /api/catalogo/estudios y GET /api/catalogo/perfiles.
 * - Muestra los 9 estudios activos, sus grupos/parámetros y los 2 perfiles preconfigurados.
 */

import React, { useEffect, useState } from "react";
import {
  EstudioCatalogo,
  obtenerEstudiosCatalogoApi,
  obtenerPerfilesCatalogoApi,
  PerfilCatalogo,
} from "../../api/catalogo";
import { ApiError } from "../../api/client";

interface CatalogoModalProps {
  abierto: boolean;
  onCerrar: () => void;
}

export const CatalogoModal: React.FC<CatalogoModalProps> = ({ abierto, onCerrar }) => {
  const [pestana, setPestana] = useState<"estudios" | "perfiles">("estudios");
  const [estudios, setEstudios] = useState<EstudioCatalogo[]>([]);
  const [perfiles, setPerfiles] = useState<PerfilCatalogo[]>([]);
  const [cargando, setCargando] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!abierto) return;

    const cargar = async () => {
      setCargando(true);
      setError(null);
      try {
        const [estData, perfData] = await Promise.all([
          obtenerEstudiosCatalogoApi(),
          obtenerPerfilesCatalogoApi(),
        ]);
        setEstudios(estData);
        setPerfiles(perfData);
      } catch (err: unknown) {
        if (err instanceof ApiError) {
          setError(err.message);
        } else {
          setError("Error al cargar la información del catálogo clínico.");
        }
      } finally {
        setCargando(false);
      }
    };

    cargar();
  }, [abierto]);

  if (!abierto) return null;

  return (
    <div className="lis-modal-overlay" role="dialog" aria-modal="true" aria-labelledby="modal-catalogo-title">
      <div className="lis-modal-card" style={{ maxWidth: "780px" }}>
        <div className="lis-modal-header">
          <h3 id="modal-catalogo-title">Catálogo Clínico Oficial</h3>
          <button
            type="button"
            className="lis-modal-close"
            onClick={onCerrar}
            aria-label="Cerrar modal de catálogo"
          >
            ✕
          </button>
        </div>

        <div style={{ display: "flex", gap: "0.5rem", padding: "1rem 1.5rem 0", borderBottom: "1px solid var(--border-color)" }}>
          <button
            type="button"
            onClick={() => setPestana("estudios")}
            className={`lis-btn ${pestana === "estudios" ? "lis-btn-primary" : "lis-btn-text"}`}
          >
            Estudios Activos ({estudios.length})
          </button>
          <button
            type="button"
            onClick={() => setPestana("perfiles")}
            className={`lis-btn ${pestana === "perfiles" ? "lis-btn-primary" : "lis-btn-text"}`}
          >
            Perfiles Preconfigurados ({perfiles.length})
          </button>
        </div>

        <div className="lis-modal-body" style={{ maxHeight: "65vh" }}>
          {cargando && (
            <div className="lis-table-loading">
              <div className="lis-spinner" style={{ margin: "0 auto 0.5rem" }} />
              <p>Cargando catálogo clínico...</p>
            </div>
          )}

          {error && <div className="lis-alert lis-alert-error">{error}</div>}

          {!cargando && !error && pestana === "estudios" && (
            <div className="lis-catalog-grid">
              {estudios.map((est) => (
                <div key={est.codigo} className="lis-catalog-card">
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "0.5rem" }}>
                    <span className="lis-catalog-tag">{est.categoria}</span>
                    <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--text-muted)" }}>
                      {est.codigo}
                    </span>
                  </div>
                  <h4 style={{ fontSize: "1rem", fontWeight: 700, color: "var(--text-main)" }}>
                    {est.nombre}
                  </h4>
                  {est.seleccion_parcial ? (
                    <div style={{ marginTop: "0.25rem", fontSize: "0.85rem", color: "var(--primary)" }}>
                      <span style={{ fontWeight: 600 }}>Selección parcial habilitada:</span>
                      <ul style={{ paddingLeft: "1.2rem", marginTop: "0.25rem", color: "var(--text-main)" }}>
                        {est.grupos?.map((g) => (
                          <li key={g.codigo}>
                            <strong>{g.codigo.replace(/_/g, " ")}</strong>:{" "}
                            <span style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>
                              {g.parametros.map((p) => p.nombre).join(", ")}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : (
                    <p style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                      Estudio estándar con parámetros clínicos indivisibles.
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}

          {!cargando && !error && pestana === "perfiles" && (
            <div className="lis-catalog-grid">
              {perfiles.map((perf) => (
                <div key={perf.codigo} className="lis-catalog-card">
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "0.5rem" }}>
                    <span className="lis-catalog-tag">PERFIL</span>
                    <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--text-muted)" }}>
                      {perf.codigo}
                    </span>
                  </div>
                  <h4 style={{ fontSize: "1rem", fontWeight: 700, color: "var(--text-main)" }}>
                    {perf.nombre}
                  </h4>
                  <div style={{ fontSize: "0.85rem", marginTop: "0.25rem" }}>
                    <strong style={{ color: "var(--text-muted)" }}>Estudios incluidos:</strong>
                    <ul style={{ paddingLeft: "1.2rem", marginTop: "0.25rem" }}>
                      {perf.estudios.map((pe) => (
                        <li key={pe.codigo}>
                          <code>{pe.codigo}</code>
                          {pe.grupos && pe.grupos.length > 0 && (
                            <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                              {" "}(Grupos: {pe.grupos.join(", ")})
                            </span>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="lis-modal-footer" style={{ padding: "1rem 1.5rem" }}>
          <button type="button" className="lis-btn lis-btn-secondary" onClick={onCerrar}>
            Cerrar
          </button>
        </div>
      </div>
    </div>
  );
};
