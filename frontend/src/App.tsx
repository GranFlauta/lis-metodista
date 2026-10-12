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
            <Route
              path="admin/usuarios"
              element={
                <RutaProtegida rolRequerido="ADMIN">
                  <UsuariosPage />
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
