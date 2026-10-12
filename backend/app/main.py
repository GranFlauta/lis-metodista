from fastapi import FastAPI

from app.api import auth, usuarios
from app.core.errors import register_error_handlers

app = FastAPI(
    title="LIS Laboratorio Clínico",
    version="0.1.0",
    docs_url="/docs",
    redoc_url=None,
)

# Registrar manejadores de excepciones para formato {"codigo": "...", "mensaje": "..."}
register_error_handlers(app)

# Healthcheck
@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}

# Routers de la Fase 1
app.include_router(auth.router)
app.include_router(usuarios.router)
