from fastapi import FastAPI

from app.api import auth, catalogo, ordenes, pacientes, resultados, usuarios
from app.core.config import settings
from app.core.errors import register_error_handlers

# D35-01: sin CORS (frontend y API comparten origen vía Caddy / proxy de Vite).
# La documentación interactiva solo se expone con ENABLE_DOCS=true.
# La IP real del cliente la resuelven los flags --proxy-headers de uvicorn (Dockerfile);
# el backend no publica puertos y solo lo alcanza Caddy.
app = FastAPI(
    title="LIS Laboratorio Clínico",
    version="0.1.0",
    docs_url="/docs" if settings.enable_docs else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.enable_docs else None,
)

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
