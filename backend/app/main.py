from fastapi import FastAPI

app = FastAPI(title="LIS Laboratorio Clínico", version="0.1.0")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
# Fase 1: routers de auth/usuarios.  Ver docs/DECISIONES.md §9 (hoja de ruta).

