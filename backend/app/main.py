from fastapi import FastAPI
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.api import auth, usuarios
from app.core.errors import register_error_handlers

app = FastAPI(
    title="LIS Laboratorio Clínico",
    version="0.1.0",
    docs_url="/docs",
    redoc_url=None,
)

# Resolver IP del cliente desde el proxy inverso (Caddy) en request.client.host
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

# Registrar manejadores de excepciones para formato {"codigo": "...", "mensaje": "..."}
register_error_handlers(app)


# Healthcheck
@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}

# Routers de la Fase 1
app.include_router(auth.router)
app.include_router(usuarios.router)
