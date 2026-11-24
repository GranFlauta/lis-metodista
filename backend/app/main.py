from fastapi import FastAPI

from app.api import auth, catalogo, estadisticas, informes, ordenes, pacientes, resultados, usuarios
from app.core.config import settings
from app.core.errors import register_error_handlers

app = FastAPI(
    title="LIS Laboratorio Clínico",
    version="0.1.0",
    docs_url="/docs" if settings.enable_docs else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.enable_docs else None,
)

register_error_handlers(app)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(auth.admin_config_router)
app.include_router(usuarios.router)
app.include_router(catalogo.router)
app.include_router(pacientes.router)
app.include_router(ordenes.router)
app.include_router(resultados.router)
app.include_router(informes.router)
app.include_router(estadisticas.router)
