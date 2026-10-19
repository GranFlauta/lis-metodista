import sys
from pathlib import Path
from fastapi import FastAPI

from app.api import auth, catalogo, ordenes, pacientes, resultados, usuarios
from app.core.config import es_modo_demo, settings
from app.core.errors import register_error_handlers

# Determinar si el modo demo está activo (MODO_DEMO=true fuera de ejecución de tests)
modo_demo_activo = es_modo_demo()

# D35-01: sin CORS en producción (frontend y API comparten origen vía Caddy / proxy de Vite).
# MODO_DEMO=true rehabilita docs, CORS y frontend SPA en puerto 8000 para presentaciones con ngrok.
app = FastAPI(
    title="LIS Laboratorio Clínico",
    version="0.1.0",
    docs_url="/docs" if (settings.enable_docs or modo_demo_activo) else None,
    redoc_url=None,
    openapi_url="/openapi.json" if (settings.enable_docs or modo_demo_activo) else None,
)

if modo_demo_activo:
    from fastapi.middleware.cors import CORSMiddleware
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^https?://.*",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

# Registrar manejadores de excepciones para formato {"codigo": "...", "mensaje": "..."}
register_error_handlers(app)


# Healthcheck
@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}

# Routers de la Fase 1, 2 y 3
app.include_router(auth.router)
app.include_router(auth.admin_config_router)
app.include_router(usuarios.router)
app.include_router(catalogo.router)
app.include_router(pacientes.router)
app.include_router(ordenes.router)
app.include_router(resultados.router)

if modo_demo_activo:
    from fastapi.responses import FileResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles

    FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
    if (FRONTEND_DIST / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_frontend_or_spa(full_path: str):
        # No interceptar rutas de API ni documentación
        if full_path.startswith("api") or full_path.startswith("docs") or full_path.startswith("openapi.json"):
            return JSONResponse(status_code=404, content={"codigo": "NO_ENCONTRADO", "mensaje": "Ruta no encontrada."})

        index_html = FRONTEND_DIST / "index.html"
        if index_html.exists():
            return FileResponse(str(index_html))

        return {
            "status": "ok",
            "sistema": "LIS Laboratorio Clínico API (Modo Demo)",
            "documentacion": "/docs",
            "salud": "/api/health",
            "mensaje": "Servidor activo en Modo Demo. Abra /docs para la documentación interactiva o compile el frontend para la interfaz web.",
        }
