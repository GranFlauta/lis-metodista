"""
Modelos ORM para sesiones de usuario y registro de eventos de seguridad.
Alineado con el esquema 001_schema.sql (tablas `sesiones` y `log_seguridad`).
"""

from sqlalchemy import Column, BigInteger, String, DateTime, Text, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import relationship

from app.core.database import Base


class Sesion(Base):
    """
    Sesiones de usuario con latido y tope absoluto según docs/DECISIONES.md §6.
    """
    __tablename__ = "sesiones"
    __table_args__ = {"schema": "laboratorio"}

    id_sesion = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    id_usuario = Column(
        BigInteger,
        ForeignKey("laboratorio.usuarios.id_usuario"),
        nullable=False,
        index=True,
    )
    refresh_hash = Column(String(64), nullable=False)
    ip = Column(INET)
    user_agent = Column(Text)
    creada_en = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    ultimo_latido = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    ultima_actividad = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    expira_en = Column(DateTime(timezone=True), nullable=False)
    revocada_en = Column(DateTime(timezone=True))

    usuario = relationship("Usuario", foreign_keys=[id_usuario])


class LogSeguridad(Base):
    """
    Registro auditable de eventos de seguridad (LOGIN_OK, LOGIN_FALLIDO, LOGOUT, etc.).
    """
    __tablename__ = "log_seguridad"
    __table_args__ = {"schema": "laboratorio"}

    id_log = Column(BigInteger, primary_key=True, autoincrement=True, index=True)
    id_usuario = Column(BigInteger, ForeignKey("laboratorio.usuarios.id_usuario"), nullable=True)
    id_objetivo = Column(BigInteger, ForeignKey("laboratorio.usuarios.id_usuario"), nullable=True)
    accion = Column(String(40), nullable=False)
    ip = Column(INET)
    detalle = Column(JSONB, nullable=True)
    creado_en = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    usuario = relationship("Usuario", foreign_keys=[id_usuario])
    objetivo = relationship("Usuario", foreign_keys=[id_objetivo])
