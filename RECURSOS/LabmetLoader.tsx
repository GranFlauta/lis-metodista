import { useEffect, useState } from "react";
import logoRojo from "../assets/labmet-loader.svg";

type Props = {
  /** "icon" = ícono pequeño fijo abajo a la derecha (por defecto)
   *  "fullscreen" = cubre toda la pantalla con fondo oscuro */
  variant?: "icon" | "fullscreen";
  /** Ancho en px del logo. Por defecto: 56 (icon) / 240 (fullscreen). */
  size?: number;
  /** Texto para lectores de pantalla. */
  label?: string;
  /** No mostrar nada si la carga dura menos de N ms (evita parpadeos). */
  delayMs?: number;
};

export default function LabmetLoader({
  variant = "icon",
  size,
  label = "Cargando…",
  delayMs = 150,
}: Props) {
  const [visible, setVisible] = useState(delayMs === 0);

  useEffect(() => {
    if (delayMs === 0) return;
    const t = setTimeout(() => setVisible(true), delayMs);
    return () => clearTimeout(t);
  }, [delayMs]);

  if (!visible) return null;

  const width = size ?? (variant === "icon" ? 56 : 240);
  const height = Math.round((width * 1110) / 1155);
  const wrapper =
    variant === "icon"
      ? "pointer-events-none fixed bottom-4 right-4 z-50"
      : "fixed inset-0 z-50 grid place-items-center bg-[#07070b]";

  return (
    <div className={wrapper} role="status" aria-live="polite">
      <img src={logoRojo} width={width} height={height} alt="" decoding="async" />
      <span className="sr-only">{label}</span>
    </div>
  );
}
