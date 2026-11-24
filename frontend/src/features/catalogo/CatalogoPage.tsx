/**
 * Consulta del catálogo y gestión de perfiles rápidos, con acceso propio.
 * PROMPT_FASE_2.md §8.1:
 * - Consulta GET /api/catalogo/estudios y GET /api/catalogo/perfiles.
 * - Muestra los estudios activos, sus grupos/parámetros y los 2 perfiles preconfigurados.
 */

import React, { useEffect, useState } from "react";
import { CargaLaboratorio } from "../../components/MarcaLaboratorio";
import { EstudiosPerfil } from "../../components/EstudiosPerfil";
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

export const CatalogoPage: React.FC = () => {
  const [pestana, setPestana] = useState<"estudios" | "perfiles">("estudios");
  const [estudios, setEstudios] = useState<EstudioCatalogo[]>([]);
  const [perfiles, setPerfiles] = useState<PerfilCatalogo[]>([]);
  const [perfilesRapidos, setPerfilesRapidos] = useState<PerfilRapido[]>([]);
  const [nombrePerfilRapido, setNombrePerfilRapido] = useState("");
  const [estudiosPerfilRapido, setEstudiosPerfilRapido] = useState<Record<string, string[]>>({});
  const [perfilRapidoEditando, setPerfilRapidoEditando] = useState<number | null>(null);
  const [cargando, setCargando] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [guardando, setGuardando] = useState(false);
  const [mensaje, setMensaje] = useState("");
  const [recarga, setRecarga] = useState(0);

  useEffect(() => {
    let activo = true;
    const cargar = async () => {
      setCargando(true);
      setError(null);
      try {
        const [estData, perfData, rapidos] = await Promise.all([
          obtenerEstudiosCatalogoApi(),
          obtenerPerfilesCatalogoApi(),
          listarPerfilesRapidosApi(),
        ]);
        if (!activo) return;
        setEstudios(estData);
        setPerfiles(perfData);
        setPerfilesRapidos(rapidos);
      } catch (err: unknown) {
        if (!activo) return;
        if (err instanceof ApiError) {
          setError(err.message);
        } else {
          setError("Error al cargar la información del catálogo clínico.");
        }
      } finally {
        if (activo) setCargando(false);
      }
    };

    cargar();
    return () => { activo = false; };
  }, [recarga]);

  const cargarEditorPerfil = (perfil?: PerfilRapido) => {
    setNombrePerfilRapido(perfil?.nombre || "");
    setPerfilRapidoEditando(perfil?.id ?? null);
    setEstudiosPerfilRapido(Object.fromEntries((perfil?.estudios || []).map((item) => [item.codigo, item.grupos || []])));
  };

  const guardarPerfilRapido = async () => {
    if (guardando) return;
    setGuardando(true);
    setMensaje("");
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
      setMensaje(`Perfil “${saved.nombre}” guardado con ${saved.estudios.length} estudios.`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo guardar el perfil rápido.");
    } finally {
      setGuardando(false);
    }
  };

  return (
    <div className="lis-catalog-page">
        <div className="lis-page-header">
          <div><h2>Catálogo clínico</h2><p className="lis-page-sub">Consulta los estudios disponibles y organiza tus perfiles rápidos.</p></div>
        </div>

        <div className="lis-catalog-tabs" aria-label="Secciones del catálogo">
          <button
            type="button"
            onClick={() => setPestana("estudios")}
            className={`lis-btn ${pestana === "estudios" ? "lis-btn-primary" : "lis-btn-text"}`}
            aria-pressed={pestana === "estudios"}
          >
            Estudios Activos ({estudios.length})
          </button>
          <button
            type="button"
            onClick={() => setPestana("perfiles")}
            className={`lis-btn ${pestana === "perfiles" ? "lis-btn-primary" : "lis-btn-text"}`}
            aria-pressed={pestana === "perfiles"}
          >
            Perfiles y accesos rápidos ({perfiles.length + perfilesRapidos.length})
          </button>
        </div>

        <div className="lis-catalog-body">
          {cargando && (
            <div className="lis-table-loading">
              <CargaLaboratorio mensaje="Cargando catálogo clínico…" />
            </div>
          )}

          {error && <div className="lis-alert lis-alert-error" role="alert">{error} {!estudios.length && <button type="button" className="lis-btn lis-btn-secondary" onClick={() => setRecarga((valor) => valor + 1)}>Reintentar</button>}</div>}
          {mensaje && <div className="lis-alert lis-alert-success" role="status">{mensaje}</div>}

          {!cargando && pestana === "estudios" && (
            <div className="lis-catalog-accordion" aria-label="Estudios por sección">
              {[...new Set(estudios.map((estudio) => estudio.categoria))].map((categoria) => {
                const items = estudios.filter((estudio) => estudio.categoria === categoria);
                return <details key={categoria}>
                  <summary>{categoria} · {items.length} {items.length === 1 ? "estudio" : "estudios"}</summary>
                  <div className="lis-catalog-accordion-content">
                    {items.map((estudio) => <details key={estudio.codigo} className="lis-catalog-study-fields">
                      <summary><span className="lis-chip">{estudio.codigo}</span> {estudio.nombre}</summary>
                      {estudio.seleccion_parcial && estudio.grupos?.length ? <div className="lis-catalog-groups">
                        {estudio.grupos.map((grupo) => <details key={grupo.codigo}>
                          <summary>{grupo.codigo.replace(/_/g, " ")} · {grupo.parametros.length} campos</summary>
                          <ul>{grupo.parametros.map((parametro) => <li key={parametro.codigo}>{parametro.nombre}</li>)}</ul>
                        </details>)}
                      </div> : <ul className="lis-catalog-field-list">
                        {(estudio.parametros || []).map((parametro) => <li key={parametro.codigo}>{parametro.nombre}</li>)}
                      </ul>}
                    </details>)}
                  </div>
                </details>;
              })}
            </div>
          )}

          {!cargando && pestana === "perfiles" && (
            <div>
            <div className="lis-catalog-accordion" aria-label="Perfiles predefinidos">
              {perfiles.map((perfil) => <details key={perfil.codigo}>
                <summary><span className="lis-chip">{perfil.codigo}</span> {perfil.nombre} · {perfil.estudios.length} estudios</summary>
                <div className="lis-catalog-accordion-content">
                  <EstudiosPerfil items={perfil.estudios} catalogo={estudios} />
                </div>
              </details>)}
            </div>
            <section className="lis-quick-profile-editor">
              <h4>Perfiles rápidos personalizados</h4>
              {!perfilesRapidos.length ? <p className="lis-text-muted">Aún no hay perfiles personalizados.</p> : (
                <div className="lis-quick-profile-list" aria-label="Perfiles rápidos personalizados">
                  {perfilesRapidos.map((perfil) => <article className="lis-quick-profile-item" key={perfil.id}>
                    <details className="lis-quick-profile-details">
                      <summary>
                        <strong>{perfil.nombre}</strong>
                        <span>{perfil.estudios.length} {perfil.estudios.length === 1 ? "estudio" : "estudios"}</span>
                        {perfilRapidoEditando === perfil.id && <span className="lis-chip lis-chip-primary">Editando</span>}
                      </summary>
                      <EstudiosPerfil items={perfil.estudios} catalogo={estudios} />
                    </details>
                    <div className="lis-quick-profile-actions lis-quick-profile-card-actions">
                      <button type="button" className="lis-btn lis-btn-text" onClick={() => cargarEditorPerfil(perfil)}>Editar</button>
                      <button type="button" className="lis-btn lis-btn-text" onClick={async () => {
                        if (!window.confirm(`¿Eliminar el perfil “${perfil.nombre}”?`)) return;
                        try {
                          await eliminarPerfilRapidoApi(perfil.id);
                          setPerfilesRapidos((prev) => prev.filter((item) => item.id !== perfil.id));
                          if (perfilRapidoEditando === perfil.id) cargarEditorPerfil();
                          setMensaje("Perfil rápido eliminado.");
                          setError(null);
                        } catch (err) {
                          setError(err instanceof ApiError ? err.message : "No se pudo eliminar el perfil rápido.");
                        }
                      }}>Eliminar</button>
                    </div>
                  </article>)}
                </div>
              )}
              <label className="lis-form-field">Nombre del perfil
                <input value={nombrePerfilRapido} maxLength={100} onChange={(e) => setNombrePerfilRapido(e.target.value)} />
              </label>
              <div className="lis-catalog-accordion lis-catalog-profile-editor" aria-label="Seleccionar estudios y campos del perfil">
                {[...new Set(estudios.map((estudio) => estudio.categoria))].map((categoria) => {
                  const items = estudios.filter((estudio) => estudio.categoria === categoria);
                  return <details key={categoria}>
                    <summary>{categoria} · {items.length} estudios</summary>
                    <div className="lis-catalog-accordion-content">
                      {items.map((estudio) => {
                        const gruposActuales = estudiosPerfilRapido[estudio.codigo];
                        return <div className="lis-catalog-study-row" key={estudio.codigo}>
                          <label><input type="checkbox" checked={gruposActuales !== undefined} onChange={(e) => setEstudiosPerfilRapido((prev) => {
                            const next = { ...prev };
                            if (e.target.checked) next[estudio.codigo] = [];
                            else delete next[estudio.codigo];
                            return next;
                          })} /> {estudio.nombre}</label>
                          <details className="lis-catalog-study-fields">
                            <summary>{estudio.seleccion_parcial ? "Seleccionar grupos y ver campos" : `Ver campos (${estudio.parametros?.length || 0})`}</summary>
                            {estudio.seleccion_parcial ? <div className="lis-catalog-groups">
                              {estudio.grupos?.map((grupo) => <details key={grupo.codigo}>
                                <summary>{grupo.codigo.replace(/_/g, " ")} · {grupo.parametros.length} campos</summary>
                                <div className="lis-catalog-group-choice">
                                  <label><input type="checkbox" checked={gruposActuales?.includes(grupo.codigo) || false} disabled={gruposActuales === undefined} onChange={(e) => setEstudiosPerfilRapido((prev) => ({
                                  ...prev,
                                  [estudio.codigo]: e.target.checked
                                    ? [...(prev[estudio.codigo] || []), grupo.codigo]
                                    : (prev[estudio.codigo] || []).filter((item) => item !== grupo.codigo),
                                }))} /> Incluir grupo</label>
                                <ul>{grupo.parametros.map((parametro) => <li key={parametro.codigo}>{parametro.nombre}</li>)}</ul>
                                </div>
                              </details>)}
                            </div> : <ul className="lis-catalog-field-list">
                              {(estudio.parametros || []).map((parametro) => <li key={parametro.codigo}>{parametro.nombre}</li>)}
                            </ul>}
                          </details>
                        </div>;
                      })}
                    </div>
                  </details>;
                })}
              </div>
              <div className="lis-quick-profile-actions">
                <button type="button" className="lis-btn lis-btn-secondary" onClick={() => cargarEditorPerfil()}>Limpiar</button>
                <button type="button" className="lis-btn lis-btn-primary" disabled={guardando || !nombrePerfilRapido.trim() || !Object.keys(estudiosPerfilRapido).length || Object.entries(estudiosPerfilRapido).some(([codigo, grupos]) => estudios.find((item) => item.codigo === codigo)?.seleccion_parcial && !grupos.length)} onClick={guardarPerfilRapido}>{guardando ? "Guardando…" : perfilRapidoEditando ? "Guardar cambios" : "Crear perfil rápido"}</button>
              </div>
            </section>
            </div>
          )}
        </div>

    </div>
  );
};
