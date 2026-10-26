/**
 * Aplicación principal LIS Laboratorio Clínico.
 * PROMPT_FASE_1.md §9:
 * Rutas: /login, /cambiar-password, / (inicio), /admin/usuarios (solo ADMIN).
 */

import React from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./features/auth/AuthProvider";
import { RutaProtegida } from "./features/auth/RutaProtegida";
import { LoginPage } from "./features/auth/LoginPage";
import { CambiarPasswordPage } from "./features/auth/CambiarPasswordPage";
import { HomePage } from "./features/home/HomePage";
import { UsuariosPage } from "./features/admin/UsuariosPage";
import { ConfiguracionSesionPage } from "./features/admin/ConfiguracionSesionPage";
import { PacientesPage } from "./features/pacientes/PacientesPage";
import { PacienteDetallePage } from "./features/pacientes/PacienteDetallePage";
import { OrdenesPage } from "./features/ordenes/OrdenesPage";
import { NuevaOrdenPage } from "./features/ordenes/NuevaOrdenPage";
import { OrdenDetallePage } from "./features/ordenes/OrdenDetallePage";
import { CapturaResultadosPage } from "./features/ordenes/CapturaResultadosPage";
import { InformesPage } from "./features/informes/InformesPage";
import { InformeDetallePage } from "./features/informes/InformeDetallePage";
import { PapeleraPage } from "./features/informes/PapeleraPage";
import { Layout } from "./components/Layout";
import "./index.css";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Ruta pública de login */}
          <Route path="/login" element={<LoginPage />} />

          {/* Cambio de contraseña (protegida para usuarios autenticados) */}
          <Route
            path="/cambiar-password"
            element={
              <RutaProtegida>
                <CambiarPasswordPage />
              </RutaProtegida>
            }
          />

          {/* Rutas con Layout clínico */}
          <Route
            path="/"
            element={
              <RutaProtegida>
                <Layout />
              </RutaProtegida>
            }
          >
            <Route index element={<HomePage />} />
            <Route path="pacientes" element={<PacientesPage />} />
            <Route path="pacientes/:id" element={<PacienteDetallePage />} />
            <Route path="ordenes" element={<OrdenesPage />} />
            <Route
              path="ordenes/nueva"
              element={
                <RutaProtegida rolRequerido="BIOQUIMICO">
                  <NuevaOrdenPage />
                </RutaProtegida>
              }
            />
            <Route path="ordenes/:id" element={<OrdenDetallePage />} />
            <Route path="ordenes/:id/captura" element={<CapturaResultadosPage />} />
            <Route path="informes" element={<InformesPage />} />
            <Route path="informes/:folio" element={<InformeDetallePage />} />
            <Route path="papelera" element={<PapeleraPage />} />
            <Route
              path="admin/usuarios"
              element={
                <RutaProtegida rolRequerido="ADMIN">
                  <UsuariosPage />
                </RutaProtegida>
              }
            />
            <Route
              path="admin/configuracion"
              element={
                <RutaProtegida rolRequerido="ADMIN">
                  <ConfiguracionSesionPage />
                </RutaProtegida>
              }
            />
          </Route>

          {/* Redirección por defecto */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
