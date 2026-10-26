import React, { useState, useEffect } from "react";
import { EstudioCatalogo } from "../../api/catalogo";
import { formatearResultadoClinico } from "../../utils/formatoNumerico";

// --------------------------------------------------------------------------------
// 1. MODAL EDITAR RANGO DE REFERENCIA (Editable por orden en tiempo real)
// --------------------------------------------------------------------------------
interface ModalEditarRangoProps {
  abierto: boolean;
  parametro: {
    codigo: string;
    nombre: string;
    inf: string;
    sup: string;
    txt: string;
    modificada: boolean;
  } | null;
  onCerrar: () => void;
  onGuardar: (codigo: string, inf: string, sup: string, txt: string) => void;
  onReestablecer: (codigo: string) => void;
}

export const ModalEditarRango: React.FC<ModalEditarRangoProps> = ({
  abierto,
  parametro,
  onCerrar,
  onGuardar,
  onReestablecer,
}) => {
  const [inf, setInf] = useState("");
  const [sup, setSup] = useState("");
  const [txt, setTxt] = useState("");

  useEffect(() => {
    if (parametro) {
      setInf(parametro.inf || "");
      setSup(parametro.sup || "");
      setTxt(parametro.txt || "");
    }
  }, [parametro]);

  if (!abierto || !parametro) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onGuardar(parametro.codigo, inf.trim(), sup.trim(), txt.trim());
  };

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: "rgba(0,0,0,0.5)",
        zIndex: 1000,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "16px",
      }}
      onClick={onCerrar}
    >
      <div
        style={{
          backgroundColor: "#ffffff",
          borderRadius: "var(--radius, 8px)",
          padding: "20px",
          width: "100%",
          maxWidth: "480px",
          boxShadow: "0 10px 25px rgba(0,0,0,0.2)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
          <h3 style={{ margin: 0, fontSize: "16px", color: "var(--text-main)" }}>
            Editar Valor de Referencia
          </h3>
          <button
            type="button"
            onClick={onCerrar}
            style={{ border: "none", background: "none", fontSize: "18px", cursor: "pointer" }}
          >
            ✕
          </button>
        </div>

        <div style={{ fontSize: "13px", color: "var(--text-muted)", marginBottom: "16px" }}>
          Parámetro: <strong style={{ color: "var(--text-main)" }}>{parametro.nombre}</strong> ({parametro.codigo})
          <div style={{ fontSize: "12px", color: "#d97706", marginTop: "4px" }}>
            * Esta modificación aplica exclusivamente a esta orden sin alterar el catálogo general.
          </div>
        </div>

        <form onSubmit={handleSubmit}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginBottom: "12px" }}>
            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 600, marginBottom: "4px" }}>
                Límite Inferior:
              </label>
              <input
                type="text"
                className="lis-captura-input"
                style={{ width: "100%" }}
                value={inf}
                onChange={(e) => setInf(e.target.value)}
                placeholder="Ej. 70"
              />
            </div>
            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 600, marginBottom: "4px" }}>
                Límite Superior:
              </label>
              <input
                type="text"
                className="lis-captura-input"
                style={{ width: "100%" }}
                value={sup}
                onChange={(e) => setSup(e.target.value)}
                placeholder="Ej. 100"
              />
            </div>
          </div>

          <div style={{ marginBottom: "16px" }}>
            <label style={{ display: "block", fontSize: "12px", fontWeight: 600, marginBottom: "4px" }}>
              Texto descriptivo alternativo (opcional):
            </label>
            <input
              type="text"
              className="lis-captura-input"
              style={{ width: "100%" }}
              value={txt}
              onChange={(e) => setTxt(e.target.value)}
              placeholder="Ej. 70 - 100 mg/dL"
            />
          </div>

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "8px" }}>
            <button
              type="button"
              className="lis-btn lis-btn-secondary lis-btn-sm"
              onClick={() => onReestablecer(parametro.codigo)}
              title="Volver a los valores predeterminados del catálogo"
              style={{ color: "#b45309", borderColor: "#fde68a", backgroundColor: "#fef3c7" }}
            >
              ↺ Reestablecer al catálogo
            </button>

            <div style={{ display: "flex", gap: "8px" }}>
              <button type="button" className="lis-btn lis-btn-secondary lis-btn-sm" onClick={onCerrar}>
                Cancelar
              </button>
              <button type="submit" className="lis-btn lis-btn-primary lis-btn-sm">
                Guardar referencia
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};


// --------------------------------------------------------------------------------
// 2. MODAL SELECCIONAR SUBESTUDIOS DE INMUNOSEROLOGÍA (Casillas color rosa)
// --------------------------------------------------------------------------------
interface ModalSeleccionarInmunoseroProps {
  abierto: boolean;
  gruposSeleccionados: Set<string>;
  onToggleGrupo: (grupo: string) => void;
  onCerrar: () => void;
  onGuardar: () => void;
  estudioInmunoCatalogo?: EstudioCatalogo | null;
}

export const ModalSeleccionarInmunosero: React.FC<ModalSeleccionarInmunoseroProps> = ({
  abierto,
  gruposSeleccionados,
  onToggleGrupo,
  onCerrar,
  onGuardar,
  estudioInmunoCatalogo,
}) => {
  if (!abierto) return null;

  // Lista canónica de grupos si no viene en catálogo
  const grupos = estudioInmunoCatalogo?.grupos || [
    { codigo: "VIH", parametros: [{ codigo: "VIH", nombre: "Serología para VIH" }] },
    { codigo: "HEPATITIS_A", parametros: [{ codigo: "HEPATITIS_A", nombre: "Hepatitis A" }] },
    { codigo: "HEPATITIS_B", parametros: [{ codigo: "HEPATITIS_B", nombre: "Hepatitis B" }] },
    { codigo: "HEPATITIS_C", parametros: [{ codigo: "HEPATITIS_C", nombre: "Hepatitis C" }] },
    { codigo: "HCG", parametros: [{ codigo: "HCG", nombre: "Gonadotropina coriónica humana" }] },
    { codigo: "SARS_COV2", parametros: [{ codigo: "SARS_COV2_AG", nombre: "Antígeno SARS-CoV-2" }] },
    { codigo: "H_PYLORI_SUERO", parametros: [{ codigo: "H_PYLORI_SUERO", nombre: "H. pylori (suero)" }] },
    { codigo: "H_PYLORI_HECES", parametros: [{ codigo: "H_PYLORI_HECES", nombre: "H. pylori (heces)" }] },
    { codigo: "SANGRE_OCULTA", parametros: [{ codigo: "SANGRE_OCULTA_HECES", nombre: "Sangre oculta en heces" }] },
    { codigo: "PCR_SEMICUANT", parametros: [{ codigo: "PCR_DILUCION", nombre: "PCR Semicuantitativa" }] },
    { codigo: "FACTOR_REUMATOIDEO", parametros: [{ codigo: "FR_DILUCION", nombre: "Factor reumatoideo" }] },
    { codigo: "ASTO", parametros: [{ codigo: "ASTO_DILUCION", nombre: "A.S.T.O." }] },
    { codigo: "VDRL", parametros: [{ codigo: "VDRL_DILUCION", nombre: "V.D.R.L." }] },
    { codigo: "PCR_TURBIDIMETRICA", parametros: [{ codigo: "PCR_CUANTITATIVA", nombre: "PCR Cuantitativa" }] },
    { codigo: "WIDAL", parametros: [{ codigo: "WIDAL_TIFOIDEA_H", nombre: "Reacción de Widal" }] },
  ];

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: "rgba(0,0,0,0.5)",
        zIndex: 1000,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "16px",
      }}
      onClick={onCerrar}
    >
      <div
        style={{
          backgroundColor: "#ffffff",
          borderRadius: "var(--radius, 8px)",
          padding: "20px",
          width: "100%",
          maxWidth: "760px",
          maxHeight: "90vh",
          display: "flex",
          flexDirection: "column",
          boxShadow: "0 10px 25px rgba(0,0,0,0.2)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ fontSize: "20px" }}>🌸</span>
            <h3 style={{ margin: 0, fontSize: "17px", color: "#701a75" }}>
              Subestudios de Inmunoserología
            </h3>
          </div>
          <button
            type="button"
            onClick={onCerrar}
            style={{ border: "none", background: "none", fontSize: "18px", cursor: "pointer" }}
          >
            ✕
          </button>
        </div>

        <p style={{ margin: "0 0 12px 0", fontSize: "12.5px", color: "var(--text-muted)" }}>
          Marque o desmarque los subestudios analíticos que deben realizarse e imprimirse en esta orden:
        </p>

        {/* Casillas rosas (lis-inmunosero-dropdown y lis-inmunosero-grid) */}
        <div
          className="lis-inmunosero-dropdown"
          style={{ overflowY: "auto", flex: 1, maxHeight: "60vh", padding: "12px", border: "1px solid #f0abfc" }}
        >
          <div className="lis-inmunosero-grid">
            {grupos.map((g) => {
              const marcado = gruposSeleccionados.has(g.codigo);
              const etiqueta = g.codigo.replace(/_/g, " ");
              const paramsTexto = g.parametros.map((p) => p.nombre).join(", ");

              return (
                <label
                  key={g.codigo}
                  className={`lis-inmunosero-item ${marcado ? "selected" : ""}`}
                  style={{ cursor: "pointer", userSelect: "none" }}
                  onClick={(e) => {
                    e.stopPropagation();
                    onToggleGrupo(g.codigo);
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                    <input
                      type="checkbox"
                      checked={marcado}
                      onChange={() => onToggleGrupo(g.codigo)}
                      onClick={(e) => e.stopPropagation()}
                    />
                    <strong style={{ color: marcado ? "#701a75" : "inherit" }}>{etiqueta}</strong>
                  </div>
                  <span style={{ fontSize: "11px", color: "var(--text-muted)", paddingLeft: "20px" }}>
                    {paramsTexto}
                  </span>
                </label>
              );
            })}
          </div>
        </div>

        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginTop: "16px",
            paddingTop: "12px",
            borderTop: "1px solid var(--border-light)",
          }}
        >
          <span style={{ fontSize: "12.5px", color: "var(--text-muted)" }}>
            {gruposSeleccionados.size} subestudio(s) seleccionado(s)
          </span>

          <div style={{ display: "flex", gap: "8px" }}>
            <button type="button" className="lis-btn lis-btn-secondary" onClick={onCerrar}>
              Cancelar
            </button>
            <button
              type="button"
              className="lis-btn lis-btn-primary"
              style={{ backgroundColor: "#c026d3", borderColor: "#a21caf" }}
              onClick={onGuardar}
            >
              Guardar Subestudios
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};


// --------------------------------------------------------------------------------
// 3. MODAL CALCULADOR INTERACTIVO PCR SEMICUANTITATIVA
// --------------------------------------------------------------------------------
interface ModalCalculadorPcrProps {
  abierto: boolean;
  separadorDecimal: string;
  onCerrar: () => void;
  onAplicar: (resultadoTexto: string) => void;
}

export const ModalCalculadorPcr: React.FC<ModalCalculadorPcrProps> = ({
  abierto,
  separadorDecimal,
  onCerrar,
  onAplicar,
}) => {
  const [criterio, setCriterio] = useState<"Negativo" | "Positivo">("Negativo");
  const [reactivo, setReactivo] = useState<"MONLAB" | "TECO" | "CUSTOM">("MONLAB");
  const [sensibilidadCustom, setSensibilidadCustom] = useState<string>("6");
  const [dilucion, setDilucion] = useState<string>("1/8");

  if (!abierto) return null;

  // Factores inversos
  const dilucionesFactores: Record<string, number> = {
    "1/2": 2,
    "1/4": 4,
    "1/8": 8,
    "1/16": 16,
    "1/32": 32,
    "1/64": 64,
  };

  let sensibilidad = 6;
  let unidad = "mg/L";
  if (reactivo === "MONLAB") {
    sensibilidad = 6;
    unidad = "mg/L";
  } else if (reactivo === "TECO") {
    sensibilidad = 0.8;
    unidad = "mg/dL";
  } else {
    sensibilidad = parseFloat(sensibilidadCustom.replace(",", ".")) || 0;
    unidad = "mg/L";
  }

  const factor = dilucionesFactores[dilucion] || 1;
  const tituloCalculado = factor * sensibilidad;
  const tituloFormateado = formatearResultadoClinico(tituloCalculado.toString(), separadorDecimal);

  const resultadoFinal =
    criterio === "Negativo"
      ? `Negativo (< ${sensibilidad} ${unidad})`
      : `Positivo ${dilucion} (${tituloFormateado} ${unidad})`;

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: "rgba(0,0,0,0.5)",
        zIndex: 1000,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "16px",
      }}
      onClick={onCerrar}
    >
      <div
        style={{
          backgroundColor: "#ffffff",
          borderRadius: "var(--radius, 8px)",
          padding: "20px",
          width: "100%",
          maxWidth: "480px",
          boxShadow: "0 10px 25px rgba(0,0,0,0.2)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
          <h3 style={{ margin: 0, fontSize: "16px", color: "var(--text-main)" }}>
            ⚡ Calculador PCR Semicuantitativa
          </h3>
          <button
            type="button"
            onClick={onCerrar}
            style={{ border: "none", background: "none", fontSize: "18px", cursor: "pointer" }}
          >
            ✕
          </button>
        </div>

        {/* 1. Criterio de reactividad */}
        <div style={{ marginBottom: "12px" }}>
          <label style={{ display: "block", fontSize: "12px", fontWeight: 600, marginBottom: "4px" }}>
            1. Reactividad inicial:
          </label>
          <div style={{ display: "flex", gap: "10px" }}>
            <label style={{ display: "flex", alignItems: "center", gap: "4px", cursor: "pointer" }}>
              <input
                type="radio"
                name="criterio_pcr"
                checked={criterio === "Negativo"}
                onChange={() => setCriterio("Negativo")}
              />
              <span>Negativo</span>
            </label>
            <label style={{ display: "flex", alignItems: "center", gap: "4px", cursor: "pointer" }}>
              <input
                type="radio"
                name="criterio_pcr"
                checked={criterio === "Positivo"}
                onChange={() => setCriterio("Positivo")}
              />
              <span style={{ fontWeight: 600, color: "var(--error)" }}>Positivo</span>
            </label>
          </div>
        </div>

        {/* 2. Si es positivo, seleccionar reactivo y dilución */}
        {criterio === "Positivo" && (
          <div style={{ padding: "10px", backgroundColor: "#f8fafc", borderRadius: "var(--radius)", marginBottom: "12px", border: "1px solid var(--border-light)" }}>
            <div style={{ marginBottom: "10px" }}>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 600, marginBottom: "4px" }}>
                2. Marca del reactivo (Sensibilidad):
              </label>
              <select
                className="lis-captura-input"
                style={{ width: "100%" }}
                value={reactivo}
                onChange={(e) => setReactivo(e.target.value as any)}
              >
                <option value="MONLAB">MONLAB (Sensibilidad: 6 mg/L)</option>
                <option value="TECO">TECO (Sensibilidad: 0.8 mg/dL)</option>
                <option value="CUSTOM">Personalizada...</option>
              </select>
            </div>

            {reactivo === "CUSTOM" && (
              <div style={{ marginBottom: "10px" }}>
                <label style={{ display: "block", fontSize: "12px", fontWeight: 600, marginBottom: "4px" }}>
                  Sensibilidad personalizada (mg/L):
                </label>
                <input
                  type="text"
                  className="lis-captura-input"
                  value={sensibilidadCustom}
                  onChange={(e) => setSensibilidadCustom(e.target.value)}
                  placeholder="Ej. 6"
                />
              </div>
            )}

            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 600, marginBottom: "4px" }}>
                3. Dilución máxima observada:
              </label>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "6px" }}>
                {Object.keys(dilucionesFactores).map((dil) => (
                  <button
                    key={dil}
                    type="button"
                    className={`lis-btn ${dilucion === dil ? "lis-btn-primary" : "lis-btn-outline"} lis-btn-sm`}
                    style={{ fontSize: "12px" }}
                    onClick={() => setDilucion(dil)}
                  >
                    {dil} (x{dilucionesFactores[dil]})
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Vista previa del resultado calculado */}
        <div
          style={{
            padding: "10px",
            backgroundColor: criterio === "Positivo" ? "#fef2f2" : "#f0fdf4",
            borderRadius: "var(--radius)",
            marginBottom: "16px",
            border: `1px solid ${criterio === "Positivo" ? "#fecaca" : "#bbf7d0"}`,
          }}
        >
          <div style={{ fontSize: "11px", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700 }}>
            Resultado final a registrar:
          </div>
          <div style={{ fontSize: "15px", fontWeight: 700, color: criterio === "Positivo" ? "#b91c1c" : "#15803d", marginTop: "2px" }}>
            {resultadoFinal}
          </div>
          {criterio === "Positivo" && (
            <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "2px" }}>
              Cálculo: Factor {factor} × {sensibilidad} = {tituloFormateado} {unidad}
            </div>
          )}
        </div>

        <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px" }}>
          <button type="button" className="lis-btn lis-btn-secondary" onClick={onCerrar}>
            Cancelar
          </button>
          <button
            type="button"
            className="lis-btn lis-btn-primary"
            onClick={() => {
              onAplicar(resultadoFinal);
              onCerrar();
            }}
          >
            Aplicar resultado
          </button>
        </div>
      </div>
    </div>
  );
};
