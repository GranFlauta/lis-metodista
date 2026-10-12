/**
 * Pantalla de Administración de Usuarios (Exclusiva para ADMIN).
 * Implementa estrictamente PROMPT_FASE_1.md §6.3 y §9:
 * - Tabla con usuario, nombre completo, CI, rol, estado (con texto).
 * - Filtros por texto (q), estado y rol.
 * - Modal para creación y edición de usuarios.
 * - Acciones con confirmación: desactivar (baja lógica), reactivar y reset de contraseña.
 * - Modal para visualización única de la contraseña temporal generada con botón copiar.
 */

import React, { useEffect, useState, useCallback } from "react";
import {
  crearUsuarioApi,
  desactivarUsuarioApi,
  editarUsuarioApi,
  listarUsuariosApi,
  reactivarUsuarioApi,
  resetPasswordUsuarioApi,
  UsuarioCreatePayload,
  UsuarioDetalle,
  UsuarioUpdatePayload,
} from "../../api/usuarios";
import { useAuth } from "../auth/AuthProvider";
import { ApiError } from "../../api/client";

export const UsuariosPage: React.FC = () => {
  const { usuario: usuarioActual } = useAuth();

  const [usuarios, setUsuarios] = useState<UsuarioDetalle[]>([]);
  const [cargando, setCargando] = useState<boolean>(true);
  const [errorGlobal, setErrorGlobal] = useState<string | null>(null);

  // Filtros
  const [filtroTexto, setFiltroTexto] = useState<string>("");
  const [filtroEstado, setFiltroEstado] = useState<string>("todos");
  const [filtroRol, setFiltroRol] = useState<string>("todos");

  // Modal de Crear / Editar
  const [modalAbierto, setModalAbierto] = useState<boolean>(false);
  const [usuarioEditando, setUsuarioEditando] = useState<UsuarioDetalle | null>(null);
  const [formularioError, setFormularioError] = useState<string | null>(null);
  const [guardando, setGuardando] = useState<boolean>(false);

  // Campos del formulario
  const [formLogin, setFormLogin] = useState<string>("");
  const [formCi, setFormCi] = useState<string>("");
  const [formNombres, setFormNombres] = useState<string>("");
  const [formPaterno, setFormPaterno] = useState<string>("");
  const [formMaterno, setFormMaterno] = useState<string>("");
  const [formCorreo, setFormCorreo] = useState<string>("");
  const [formMatricula, setFormMatricula] = useState<string>("");
  const [formRol, setFormRol] = useState<"ADMIN" | "BIOQUIMICO">("BIOQUIMICO");

  // Modal de Contraseña Temporal (se muestra una sola vez y se borra del estado al cerrar §9)
  const [modalClaveAbierto, setModalClaveAbierto] = useState<boolean>(false);
  const [passwordTemporal, setPasswordTemporal] = useState<string | null>(null);
  const [usuarioClaveDestino, setUsuarioClaveDestino] = useState<string>("");
  const [copiado, setCopiado] = useState<boolean>(false);

  // Cargar lista de usuarios
  const cargarUsuarios = useCallback(async () => {
    setCargando(true);
    setErrorGlobal(null);
    try {
      const params: { activo?: boolean; rol?: string; q?: string } = {};
      if (filtroEstado === "activos") params.activo = true;
      if (filtroEstado === "inactivos") params.activo = false;
      if (filtroRol !== "todos") params.rol = filtroRol;
      if (filtroTexto.trim()) params.q = filtroTexto.trim();

      const data = await listarUsuariosApi(params);
      setUsuarios(data);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setErrorGlobal(err.message);
      } else {
        setErrorGlobal("Error al cargar la lista de usuarios.");
      }
    } finally {
      setCargando(false);
    }
  }, [filtroEstado, filtroRol, filtroTexto]);

  useEffect(() => {
    cargarUsuarios();
  }, [cargarUsuarios]);

  // Abrir modal de creación
  const handleAbrirCrear = () => {
    setUsuarioEditando(null);
    setFormLogin("");
    setFormCi("");
    setFormNombres("");
    setFormPaterno("");
    setFormMaterno("");
    setFormCorreo("");
    setFormMatricula("");
    setFormRol("BIOQUIMICO");
    setFormularioError(null);
    setModalAbierto(true);
  };

  // Abrir modal de edición
  const handleAbrirEditar = (u: UsuarioDetalle) => {
    setUsuarioEditando(u);
    setFormLogin(u.usuario);
    setFormCi(u.ci);
    setFormNombres(u.nombres);
    setFormPaterno(u.apellido_paterno);
    setFormMaterno(u.apellido_materno || "");
    setFormCorreo(u.correo || "");
    setFormMatricula(u.matricula_profesional || "");
    setFormRol(u.rol);
    setFormularioError(null);
    setModalAbierto(true);
  };

  // Guardar formulario (crear o editar)
  const handleGuardarFormulario = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormularioError(null);
    setGuardando(true);

    try {
      if (usuarioEditando) {
        // PATCH /api/usuarios/{id}
        const payload: UsuarioUpdatePayload = {
          nombres: formNombres.trim(),
          apellido_paterno: formPaterno.trim(),
          apellido_materno: formMaterno.trim() || null,
          correo: formCorreo.trim() || null,
          matricula_profesional: formMatricula.trim() || null,
          rol: formRol,
          ci: formCi.trim(),
        };

        await editarUsuarioApi(usuarioEditando.id, payload);
        setModalAbierto(false);
        cargarUsuarios();
      } else {
        // POST /api/usuarios
        const payload: UsuarioCreatePayload = {
          usuario: formLogin.trim().toLowerCase(),
          ci: formCi.trim(),
          nombres: formNombres.trim(),
          apellido_paterno: formPaterno.trim(),
          apellido_materno: formMaterno.trim() || null,
          correo: formCorreo.trim() || null,
          matricula_profesional: formMatricula.trim() || null,
          rol: formRol,
        };

        const resp = await crearUsuarioApi(payload);
        setModalAbierto(false);

        // Mostrar contraseña temporal una sola vez (§9)
        setUsuarioClaveDestino(resp.usuario);
        setPasswordTemporal(resp.password_temporal);
        setCopiado(false);
        setModalClaveAbierto(true);

        cargarUsuarios();
      }
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setFormularioError(err.message);
      } else {
        setFormularioError("Error al procesar la solicitud.");
      }
    } finally {
      setGuardando(false);
    }
  };

  // Desactivar usuario (baja lógica con confirmación)
  const handleDesactivar = async (u: UsuarioDetalle) => {
    if (u.id === usuarioActual?.id) {
      alert("No puede desactivar su propia cuenta de administrador.");
      return;
    }

    const confirmado = window.confirm(
      `¿Está seguro de desactivar al usuario '${u.usuario}'?\nEsta acción revocará inmediatamente todas sus sesiones activas.`
    );
    if (!confirmado) return;

    try {
      await desactivarUsuarioApi(u.id);
      cargarUsuarios();
    } catch (err: unknown) {
      alert(err instanceof ApiError ? err.message : "Error al desactivar usuario.");
    }
  };

  // Reactivar usuario
  const handleReactivar = async (u: UsuarioDetalle) => {
    const confirmado = window.confirm(`¿Desea reactivar la cuenta de '${u.usuario}'?`);
    if (!confirmado) return;

    try {
      await reactivarUsuarioApi(u.id);
      cargarUsuarios();
    } catch (err: unknown) {
      alert(err instanceof ApiError ? err.message : "Error al reactivar usuario.");
    }
  };

  // Reset de contraseña (con confirmación y muestra de clave temporal única)
  const handleResetPassword = async (u: UsuarioDetalle) => {
    const confirmado = window.confirm(
      `¿Desea restablecer la contraseña de '${u.usuario}'?\nSe generará una nueva contraseña temporal y se cerrarán sus sesiones activas.`
    );
    if (!confirmado) return;

    try {
      const resp = await resetPasswordUsuarioApi(u.id);
      setUsuarioClaveDestino(u.usuario);
      setPasswordTemporal(resp.password_temporal);
      setCopiado(false);
      setModalClaveAbierto(true);
      cargarUsuarios();
    } catch (err: unknown) {
      alert(err instanceof ApiError ? err.message : "Error al resetear contraseña.");
    }
  };

  // Copiar contraseña al portapapeles
  const handleCopiarClave = () => {
    if (passwordTemporal) {
      navigator.clipboard.writeText(passwordTemporal);
      setCopiado(true);
    }
  };

  // Cerrar modal de clave temporal y ELIMINAR el valor del estado (§9)
  const handleCerrarModalClave = () => {
    setPasswordTemporal(null);
    setUsuarioClaveDestino("");
    setCopiado(false);
    setModalClaveAbierto(false);
  };

  return (
    <div className="lis-page-container">
      <div className="lis-page-header">
        <div>
          <h2>Gestión de Usuarios</h2>
          <p className="lis-page-sub">
            Administración de cuentas clínicas, roles y control de acceso seguro.
          </p>
        </div>
        <button
          type="button"
          className="lis-btn lis-btn-primary"
          onClick={handleAbrirCrear}
        >
          ➕ Nuevo Usuario
        </button>
      </div>

      {errorGlobal && (
        <div className="lis-alert lis-alert-error" role="alert">
          <span>{errorGlobal}</span>
        </div>
      )}

      {/* Barra de Filtros */}
      <div className="lis-filter-bar">
        <div className="lis-filter-group lis-search-input">
          <label htmlFor="filtro-buscar">Buscar usuario o CI</label>
          <input
            id="filtro-buscar"
            type="search"
            placeholder="Buscar por usuario, nombres, apellidos o CI..."
            value={filtroTexto}
            onChange={(e) => setFiltroTexto(e.target.value)}
          />
        </div>

        <div className="lis-filter-group">
          <label htmlFor="filtro-estado">Estado</label>
          <select
            id="filtro-estado"
            value={filtroEstado}
            onChange={(e) => setFiltroEstado(e.target.value)}
          >
            <option value="todos">Todos los estados</option>
            <option value="activos">Solo Activos</option>
            <option value="inactivos">Solo Inactivos</option>
          </select>
        </div>

        <div className="lis-filter-group">
          <label htmlFor="filtro-rol">Rol</label>
          <select
            id="filtro-rol"
            value={filtroRol}
            onChange={(e) => setFiltroRol(e.target.value)}
          >
            <option value="todos">Todos los roles</option>
            <option value="ADMIN">ADMIN</option>
            <option value="BIOQUIMICO">BIOQUIMICO</option>
          </select>
        </div>
      </div>

      {/* Tabla de Usuarios */}
      <div className="lis-table-card">
        {cargando ? (
          <div className="lis-table-loading">Cargando usuarios...</div>
        ) : usuarios.length === 0 ? (
          <div className="lis-table-empty">No se encontraron usuarios con los filtros indicados.</div>
        ) : (
          <div className="lis-table-responsive">
            <table className="lis-table">
              <thead>
                <tr>
                  <th>Usuario</th>
                  <th>Nombre Completo</th>
                  <th>Cédula (CI)</th>
                  <th>Rol</th>
                  <th>Estado</th>
                  <th>Último Login</th>
                  <th className="lis-text-right">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {usuarios.map((u) => {
                  const esPropioUsuario = u.id === usuarioActual?.id;
                  return (
                    <tr key={u.id} className={!u.activo ? "lis-row-inactive" : ""}>
                      <td className="lis-cell-bold">{u.usuario}</td>
                      <td>
                        <div>{u.nombre_completo}</div>
                        {u.correo && <small className="lis-text-muted">{u.correo}</small>}
                      </td>
                      <td>{u.ci}</td>
                      <td>
                        <span className={`lis-role-badge lis-role-${u.rol.toLowerCase()}`}>
                          {u.rol}
                        </span>
                      </td>
                      <td>
                        <span
                          className={`lis-status-badge ${
                            u.activo ? "lis-status-active" : "lis-status-inactive"
                          }`}
                        >
                          {u.activo ? "● Activo" : "○ Inactivo"}
                        </span>
                      </td>
                      <td className="lis-text-muted">
                        {u.ultimo_login
                          ? new Date(u.ultimo_login).toLocaleString("es-ES", {
                              dateStyle: "short",
                              timeStyle: "short",
                            })
                          : "Nunca"}
                      </td>
                      <td className="lis-text-right lis-actions-cell">
                        <button
                          type="button"
                          className="lis-btn lis-btn-sm lis-btn-secondary"
                          onClick={() => handleAbrirEditar(u)}
                          title="Editar información"
                        >
                          Editar
                        </button>

                        <button
                          type="button"
                          className="lis-btn lis-btn-sm lis-btn-secondary"
                          onClick={() => handleResetPassword(u)}
                          title="Resetear contraseña temporal"
                        >
                          Reset Clave
                        </button>

                        {u.activo ? (
                          <button
                            type="button"
                            className="lis-btn lis-btn-sm lis-btn-danger"
                            onClick={() => handleDesactivar(u)}
                            disabled={esPropioUsuario}
                            title={
                              esPropioUsuario
                                ? "No puede desactivar su propia cuenta"
                                : "Desactivar usuario (baja lógica)"
                            }
                          >
                            Desactivar
                          </button>
                        ) : (
                          <button
                            type="button"
                            className="lis-btn lis-btn-sm lis-btn-success"
                            onClick={() => handleReactivar(u)}
                            title="Reactivar cuenta de usuario"
                          >
                            Reactivar
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modal de Creación / Edición */}
      {modalAbierto && (
        <div className="lis-modal-overlay" role="dialog" aria-modal="true">
          <div className="lis-modal-card">
            <div className="lis-modal-header">
              <h3>{usuarioEditando ? "Editar Usuario" : "Crear Nuevo Usuario"}</h3>
              <button
                type="button"
                className="lis-modal-close"
                onClick={() => setModalAbierto(false)}
              >
                ✕
              </button>
            </div>

            {formularioError && (
              <div className="lis-alert lis-alert-error" role="alert">
                <span>{formularioError}</span>
              </div>
            )}

            <form onSubmit={handleGuardarFormulario} className="lis-form">
              <div className="lis-form-row">
                <div className="lis-form-group">
                  <label htmlFor="form-login">Usuario (Login) *</label>
                  <input
                    id="form-login"
                    type="text"
                    required
                    disabled={!!usuarioEditando || guardando}
                    value={formLogin}
                    onChange={(e) => setFormLogin(e.target.value)}
                    placeholder="ej. cvega"
                  />
                  {usuarioEditando && (
                    <small className="lis-input-hint">El login de acceso no puede modificarse.</small>
                  )}
                </div>

                <div className="lis-form-group">
                  <label htmlFor="form-ci">Documento de Identidad (CI) *</label>
                  <input
                    id="form-ci"
                    type="text"
                    required
                    disabled={guardando}
                    value={formCi}
                    onChange={(e) => setFormCi(e.target.value)}
                    placeholder="ej. 8392102"
                  />
                </div>
              </div>

              <div className="lis-form-row">
                <div className="lis-form-group">
                  <label htmlFor="form-nombres">Nombres *</label>
                  <input
                    id="form-nombres"
                    type="text"
                    required
                    disabled={guardando}
                    value={formNombres}
                    onChange={(e) => setFormNombres(e.target.value)}
                  />
                </div>

                <div className="lis-form-group">
                  <label htmlFor="form-paterno">Primer Apellido *</label>
                  <input
                    id="form-paterno"
                    type="text"
                    required
                    disabled={guardando}
                    value={formPaterno}
                    onChange={(e) => setFormPaterno(e.target.value)}
                  />
                </div>
              </div>

              <div className="lis-form-row">
                <div className="lis-form-group">
                  <label htmlFor="form-materno">Segundo Apellido (opcional)</label>
                  <input
                    id="form-materno"
                    type="text"
                    disabled={guardando}
                    value={formMaterno}
                    onChange={(e) => setFormMaterno(e.target.value)}
                  />
                </div>

                <div className="lis-form-group">
                  <label htmlFor="form-rol">Rol *</label>
                  <select
                    id="form-rol"
                    value={formRol}
                    disabled={guardando || (usuarioEditando?.id === usuarioActual?.id)}
                    onChange={(e) => setFormRol(e.target.value as "ADMIN" | "BIOQUIMICO")}
                  >
                    <option value="BIOQUIMICO">BIOQUIMICO</option>
                    <option value="ADMIN">ADMIN</option>
                  </select>
                </div>
              </div>

              <div className="lis-form-row">
                <div className="lis-form-group">
                  <label htmlFor="form-correo">Correo Electrónico (opcional)</label>
                  <input
                    id="form-correo"
                    type="email"
                    disabled={guardando}
                    value={formCorreo}
                    onChange={(e) => setFormCorreo(e.target.value)}
                    placeholder="usuario@dominio.com"
                  />
                </div>

                <div className="lis-form-group">
                  <label htmlFor="form-matricula">Matrícula Profesional (opcional)</label>
                  <input
                    id="form-matricula"
                    type="text"
                    disabled={guardando}
                    value={formMatricula}
                    onChange={(e) => setFormMatricula(e.target.value)}
                    placeholder="ej. MP-4819"
                  />
                </div>
              </div>

              <div className="lis-modal-footer">
                <button
                  type="button"
                  className="lis-btn lis-btn-secondary"
                  onClick={() => setModalAbierto(false)}
                  disabled={guardando}
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="lis-btn lis-btn-primary"
                  disabled={guardando}
                >
                  {guardando ? "Guardando..." : "Guardar"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal para Visualización Única de Contraseña Temporal (§9) */}
      {modalClaveAbierto && passwordTemporal && (
        <div className="lis-modal-overlay" role="dialog" aria-modal="true">
          <div className="lis-modal-card lis-modal-alert">
            <div className="lis-modal-header">
              <h3>Contraseña Temporal Generada</h3>
            </div>

            <div className="lis-modal-body">
              <p>
                Se ha generado una contraseña temporal para el usuario{" "}
                <strong>{usuarioClaveDestino}</strong>:
              </p>

              <div className="lis-temp-password-box">
                <code className="lis-temp-code">{passwordTemporal}</code>
                <button
                  type="button"
                  className="lis-btn lis-btn-secondary lis-btn-sm"
                  onClick={handleCopiarClave}
                >
                  {copiado ? "✓ Copiado" : "📋 Copiar"}
                </button>
              </div>

              <div className="lis-alert lis-alert-warning">
                <span className="lis-alert-icon">⚠️</span>
                <span>
                  <strong>IMPORTANTE:</strong> Esta contraseña se muestra{" "}
                  <strong>UNA SOLA VEZ</strong>. Debe entregarse al usuario; el sistema le exigirá
                  cambiarla de forma obligatoria al iniciar sesión. Al cerrar esta ventana, el valor
                  no volverá a mostrarse.
                </span>
              </div>
            </div>

            <div className="lis-modal-footer">
              <button
                type="button"
                className="lis-btn lis-btn-primary"
                onClick={handleCerrarModalClave}
              >
                Entendido y Cerrar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
