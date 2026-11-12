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
  PerfilRapido,
  listarPerfilesRapidosApi,
  crearPerfilRapidoApi,
  actualizarPerfilRapidoApi,
  eliminarPerfilRapidoApi,
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
  const [perfilesRapidos, setPerfilesRapidos] = useState<PerfilRapido[]>([]);
  const [nombrePerfilRapido, setNombrePerfilRapido] = useState("");
  const [estudiosPerfilRapido, setEstudiosPerfilRapido] = useState<Record<string, string[]>>({});
  const [perfilRapidoEditando, setPerfilRapidoEditando] = useState<number | null>(null);
  const [cargando, setCargando] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!abierto) return;

    const cargar = async () => {
      setCargando(true);
      setError(null);
      try {
        const [estData, perfData, rapidos] = await Promise.all([
          obtenerEstudiosCatalogoApi(),
          obtenerPerfilesCatalogoApi(),
          listarPerfilesRapidosApi(),
        ]);
        setEstudios(estData);
        setPerfiles(perfData);
        setPerfilesRapidos(rapidos);
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

  const cargarEditorPerfil = (perfil?: PerfilRapido) => {
    setNombrePerfilRapido(perfil?.nombre || "");
    setPerfilRapidoEditando(perfil?.id ?? null);
    setEstudiosPerfilRapido(Object.fromEntries((perfil?.estudios || []).map((item) => [item.codigo, item.grupos || []])));
  };

  const guardarPerfilRapido = async () => {
    const payload = {
      nombre: nombrePerfilRapido,
      estudios: Object.entries(estudiosPerfilRapido).map(([codigo, grupos]) => ({ codigo, grupos: grupos.length ? grupos : null })),
    };
    try {
      const saved = perfilRapidoEditando
        ? await actualizarPerfilRapidoApi(perfilRapidoEditando, payload)
        : await crearPerfilRapidoApi(payload);
      setPerfilesRapidos((prev) => perfilRapidoEditando ? prev.map((item) => item.id === saved.id ? saved : item) : [...prev, saved]);
      cargarEditorPerfil();
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo guardar el perfil rápido.");
    }
  };

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
            <div>
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
            <section className="lis-quick-profile-editor">
              <h4>Perfiles rápidos personalizados</h4>
              <div className="lis-quick-profile-list">
                {perfilesRapidos.map((perfil) => <div key={perfil.id} className="lis-quick-profile-row">
                  <strong>{perfil.nombre}</strong><span>{perfil.estudios.length} estudios</span>
                  <button type="button" className="lis-btn lis-btn-text" onClick={() => cargarEditorPerfil(perfil)}>Editar</button>
                  <button type="button" className="lis-btn lis-btn-text" onClick={async () => {
                    if (!window.confirm(`¿Eliminar el perfil “${perfil.nombre}”?`)) return;
                    try { await eliminarPerfilRapidoApi(perfil.id); setPerfilesRapidos((prev) => prev.filter((p) => p.id !== perfil.id)); }
                    catch (err) { setError(err instanceof ApiError ? err.message : "No se pudo eliminar el perfil rápido."); }
                  }}>Eliminar</button>
                </div>)}
              </div>
              <label className="lis-form-field">Nombre del perfil
                <input value={nombrePerfilRapido} maxLength={100} onChange={(e) => setNombrePerfilRapido(e.target.value)} />
              </label>
              <div className="lis-quick-profile-studies">
                {estudios.map((estudio) => {
                  const gruposActuales = estudiosPerfilRapido[estudio.codigo];
                  return <div className="lis-quick-profile-study" key={estudio.codigo}>
                    <label><input type="checkbox" checked={gruposActuales !== undefined} onChange={(e) => setEstudiosPerfilRapido((prev) => {
                      const next = { ...prev };
                      if (e.target.checked) next[estudio.codigo] = estudio.seleccion_parcial ? [] : [];
                      else delete next[estudio.codigo];
                      return next;
                    })} /> {estudio.nombre}</label>
                    {gruposActuales !== undefined && estudio.seleccion_parcial && <div className="lis-quick-profile-groups">
                      {estudio.grupos?.map((grupo) => <label key={grupo.codigo}><input type="checkbox" checked={gruposActuales.includes(grupo.codigo)} onChange={(e) => setEstudiosPerfilRapido((prev) => ({ ...prev, [estudio.codigo]: e.target.checked ? [...(prev[estudio.codigo] || []), grupo.codigo] : (prev[estudio.codigo] || []).filter((item) => item !== grupo.codigo) }))} /> {grupo.codigo.replace(/_/g, " ")}</label>)}
                    </div>}
                  </div>;
                })}
              </div>
              <div className="lis-quick-profile-actions">
                <button type="button" className="lis-btn lis-btn-secondary" onClick={() => cargarEditorPerfil()}>Limpiar</button>
                <button type="button" className="lis-btn lis-btn-primary" disabled={!nombrePerfilRapido.trim() || !Object.keys(estudiosPerfilRapido).length || Object.entries(estudiosPerfilRapido).some(([codigo, grupos]) => estudios.find((item) => item.codigo === codigo)?.seleccion_parcial && !grupos.length)} onClick={guardarPerfilRapido}>{perfilRapidoEditando ? "Guardar cambios" : "Crear perfil rápido"}</button>
              </div>
            </section>
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
