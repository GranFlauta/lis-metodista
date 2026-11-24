import React, { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { useTema } from "./TemaProvider";
import { observarActividadRed } from "../api/client";

/** SVG originales de LABMET, alojados en el frontend y sincronizados con el tema. */
export function MarcaLaboratorio({ className = "", apariencia = "roja" }: { className?: string; apariencia?: "roja" | "tema" }) {
  const { oscuro } = useTema();
  const vista = useLocation().key;
  const recurso = apariencia === "roja" ? "labmet-loader" : `labmet-login-${oscuro ? "dark" : "light"}`;
  return <span className={`lis-lab-mark ${className}`} aria-hidden="true">
    <img key={vista} className="lis-lab-mark-image" src={`/branding/${recurso}.svg?vista=${encodeURIComponent(vista)}`} width={1155} height={1110} alt="" draggable={false} decoding="async" />
  </span>;
}

/** Una única señal para peticiones lentas, canceladas o todavía pendientes. */
export function IndicadorActividad() {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    let espera: ReturnType<typeof setTimeout> | undefined;
    const cancelar = observarActividadRed((pendientes) => {
      if (!pendientes) { clearTimeout(espera); espera = undefined; setVisible(false); }
      else if (!espera) espera = setTimeout(() => setVisible(true), 450);
    });
    return () => { cancelar(); clearTimeout(espera); };
  }, []);
  return visible ? <aside className="lis-network-activity"><CargaLaboratorio compacta mensaje="Procesando…" /></aside> : null;
}

export function CargaLaboratorio({ mensaje = "Cargando…", pantalla = false, compacta = false }: { mensaje?: string; pantalla?: boolean; compacta?: boolean }) {
  return <div className={`${pantalla ? "lis-loading-screen" : "lis-loading-inline"}${compacta ? " lis-loading-compact" : ""}`} role="status" aria-live="polite">
    <img className="lis-loading-logo" src="/branding/labmet-loader.svg" width={1155} height={1110} alt="" draggable={false} decoding="async" />
    <p>{mensaje}</p>
  </div>;
}
