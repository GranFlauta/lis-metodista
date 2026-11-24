import React, { createContext, useContext, useEffect, useLayoutEffect, useState } from "react";
import { Icono } from "./Icono";

const TemaContext = createContext({ oscuro: false, alternar: () => {} });

export const useTema = () => useContext(TemaContext);

/** Preferencia en memoria: no persiste sesión ni datos en el navegador. */
export function TemaProvider({ children }: { children: React.ReactNode }) {
  const [eleccion, setEleccion] = useState<boolean | null>(null);
  const [sistemaOscuro, setSistemaOscuro] = useState(() => window.matchMedia("(prefers-color-scheme: dark)").matches);
  const oscuro = eleccion ?? sistemaOscuro;
  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const actualizar = () => setSistemaOscuro(media.matches);
    media.addEventListener("change", actualizar);
    return () => media.removeEventListener("change", actualizar);
  }, []);
  useLayoutEffect(() => {
    document.documentElement.dataset.theme = oscuro ? "dark" : "light";
  }, [oscuro]);
  return <TemaContext.Provider value={{ oscuro, alternar: () => setEleccion(!oscuro) }}>{children}</TemaContext.Provider>;
}

export function BotonTema({ soloIcono = false }: { soloIcono?: boolean }) {
  const { oscuro, alternar } = useTema();
  return <button type="button" className="lis-theme-toggle-btn" onClick={alternar} aria-label={oscuro ? "Cambiar a modo claro" : "Cambiar a modo oscuro"} title={oscuro ? "Cambiar a modo claro" : "Cambiar a modo oscuro"}>
    <Icono nombre={oscuro ? "sol" : "luna"} size={16} />{!soloIcono && <span>Modo {oscuro ? "claro" : "oscuro"}</span>}
  </button>;
}
