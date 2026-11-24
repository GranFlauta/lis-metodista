import { useEffect, useState } from "react";
import logoMetal from "../assets/labmet-login-light.svg"; // fondo claro: metalizado
import logoCristal from "../assets/labmet-login-dark.svg"; // fondo oscuro: cristal

type Props = {
  /** Fuerza el tema. Si no lo pasas, se detecta solo (clase "dark" en <html>
   *  como usa shadcn/ui, o el modo oscuro del sistema). */
  theme?: "light" | "dark";
  size?: number;
  className?: string;
};

function detectarTema(): "light" | "dark" {
  if (document.documentElement.classList.contains("dark")) return "dark";
  if (document.documentElement.classList.contains("light")) return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export default function LabmetLoginLogo({ theme, size = 280, className = "" }: Props) {
  const [auto, setAuto] = useState<"light" | "dark">(detectarTema);

  useEffect(() => {
    if (theme) return;
    const actualizar = () => setAuto(detectarTema());
    const obs = new MutationObserver(actualizar);
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener("change", actualizar);
    return () => {
      obs.disconnect();
      mq.removeEventListener("change", actualizar);
    };
  }, [theme]);

  const tema = theme ?? auto;

  return (
    <img
      src={tema === "dark" ? logoCristal : logoMetal}
      width={size}
      height={Math.round((size * 1110) / 1155)}
      alt="LABMET - Laboratorio de Diagnóstico Clínico"
      decoding="async"
      className={className}
    />
  );
}
