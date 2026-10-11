"""
Configuración de la base de datos con SQLAlchemy (FastAPI + PostgreSQL).
Provee engine, SessionLocal, Base declarativa y dependencia get_db.
"""

from collections.abc import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from app.core.config import settings

# Engine configurado con pool_pre_ping para reconexiones transparentes
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    echo=False,
)

# Fábrica de sesiones
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# Base declarativa para todos los modelos ORM
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    Dependencia FastAPI que proporciona una sesión de base de datos por petición
    y garantiza su cierre automático al finalizar.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
