import { CargaLaboratorio } from "../../components/MarcaLaboratorio";
import React, { useCallback, useEffect, useState } from "react";
import { getSesionConfigApi, SesionConfig } from "../../api/auth";
import { ApiError } from "../../api/client";

export const ConfiguracionSesionPage: React.FC = () => {
  const [config, setConfig] = useState<SesionConfig | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(true);

  const cargarConfig = useCallback(async () => {
    setCargando(true);
    setError(null);
    try {
      setConfig(await getSesionConfigApi());
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "No se pudo cargar la política de sesión.");
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    void cargarConfig();
  }, [cargarConfig]);

  return (
    <main className="lis-page-container" style={{ maxWidth: 800, margin: "0 auto", padding: 16 }}>
      <header className="lis-page-header" style={{ marginBottom: 20 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, margin: "0 0 4px", color: "var(--text-main)" }}>
          Política de sesión
        </h1>
        <p style={{ fontSize: 14, color: "var(--text-muted)", margin: 0 }}>
          La política se configura en el entorno del backend y requiere reiniciarlo.
        </p>
      </header>

      {error && (
        <div role="alert" style={{ color: "var(--error)", backgroundColor: "var(--error-bg)", padding: 12, marginBottom: 16 }}>
          {error}
        </div>
      )}

      {cargando ? (
        <CargaLaboratorio mensaje="Cargando política vigente…" />
      ) : config ? (
        <section
          aria-label="Valores efectivos de sesión"
          style={{ border: "1px solid var(--border-color)", borderRadius: 4, padding: 16 }}
        >
          <dl style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 16, margin: 0 }}>
            <div>
              <dt style={{ color: "var(--text-muted)" }}>Modo</dt>
              <dd style={{ margin: "4px 0 0", fontWeight: 600 }}>
                {config.modo_produccion ? "Producción" : "Desarrollo"}
              </dd>
            </div>
            <div>
              <dt style={{ color: "var(--text-muted)" }}>Expiración por inactividad</dt>
              <dd style={{ margin: "4px 0 0", fontWeight: 600 }}>
                {config.inactividad_min === null ? "Desactivada" : `${config.inactividad_min} minutos`}
              </dd>
            </div>
            <div>
              <dt style={{ color: "var(--text-muted)" }}>Tope absoluto</dt>
              <dd style={{ margin: "4px 0 0", fontWeight: 600 }}>
                {config.tope_absoluto_horas} horas
              </dd>
            </div>
            <div>
              <dt style={{ color: "var(--text-muted)" }}>Frecuencia de verificación</dt>
              <dd style={{ margin: "4px 0 0", fontWeight: 600 }}>
                Cada {config.intervalo_latido_seg} segundos
              </dd>
            </div>
          </dl>
          <p style={{ margin: "20px 0 0", color: "var(--text-muted)", fontSize: 13 }}>
            El vencimiento del access token es independiente: el cliente lo renueva con la cookie HttpOnly mientras la sesión siga vigente.
          </p>
        </section>
      ) : null}
    </main>
  );
};
