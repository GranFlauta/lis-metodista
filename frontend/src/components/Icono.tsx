import React from "react";

const trazos = {
  mas: <path d="M12 5v14M5 12h14" />,
  sol: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5" /></>,
  luna: <path d="M20.8 13.2A9 9 0 0 1 10.8 3.2a9 9 0 1 0 10 10Z" />,
  flecha: <path d="M5 12h14m-5-5 5 5-5 5" />,
  usuario: <><circle cx="12" cy="8" r="4" /><path d="M4 21v-2a6 6 0 0 1 6-6h4a6 6 0 0 1 6 6v2" /></>,
  candado: <><rect x="5" y="10" width="14" height="11" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 5v2" /></>,
  ojo: <><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" /><circle cx="12" cy="12" r="3" /></>,
  ojoCerrado: <><path d="m3 3 18 18M10.5 5.1 12 5c6.5 0 10 7 10 7a21 21 0 0 1-3 4M6.2 6.2A22 22 0 0 0 2 12s3.5 7 10 7a11 11 0 0 0 5.8-1.7M10 10a3 3 0 0 0 4 4" /></>,
  editar: <><path d="m15 5 4 4M4 20l4-1L20 7a2.8 2.8 0 0 0-4-4L4 15l-1 6Z" /></>,
  restaurar: <><path d="M3 4v5h5M3.5 9a9 9 0 1 1 .5 7M12 7v5l3 2" /></>,
  ajustes: <><path d="M4 3v8m0 4v6M12 3v3m0 4v11M20 3v12m0 4v2M1 11h6m2-5h6m2 9h6" /></>,
  eliminar: <><path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7" /></>,
  publicar: <><path d="M12 16V3m-5 5 5-5 5 5M4 14v7h16v-7" /></>,
  tabla: <><rect x="3" y="3" width="18" height="18" rx="2" /><path d="M3 9h18M3 15h18M10 3v18" /></>,
  calcular: <><rect x="5" y="2" width="14" height="20" rx="2" /><path d="M8 6h8M8 11h1m6 0h1m-8 4h1m6 0h1m-8 4h1m6 0h1" /></>,
  documento: <><path d="M14 2H5v20h14V7l-5-5Zm0 0v5h5M8 12h8m-8 4h8" /></>,
  imprimir: <><path d="M6 9V3h12v6M6 18H3V9h18v9h-3" /><rect x="6" y="14" width="12" height="7" /><path d="M17 11h1" /></>,
  ampliar: <path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5" />,
  correcto: <path d="m5 12 4 4L19 6" />,
  alerta: <><path d="m12 3 10 18H2L12 3Zm0 6v5m0 3v.5" /></>,
  catalogo: <><path d="M12 5v16M3 3h5a4 4 0 0 1 4 2 4 4 0 0 1 4-2h5v16h-5a4 4 0 0 0-4 2 4 4 0 0 0-4-2H3Z" /></>,
  estadisticas: <><path d="M3 3v18h18M7 17v-5m5 5V7m5 10V4" /></>,
  reloj: <><circle cx="12" cy="12" r="9" /><path d="M12 6v6l4 2" /></>,
  descargar: <><path d="M12 3v12m-4-4 4 4 4-4M4 17v4h16v-4" /></>,
};

export function Icono({ nombre, size = 18, ...props }: React.SVGProps<SVGSVGElement> & { nombre: keyof typeof trazos; size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>{trazos[nombre]}</svg>;
}
