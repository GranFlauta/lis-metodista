"""
Modelo ORM para Pacientes.
Alineado con db/init/001_schema.sql (tabla `pacientes`).
"""
from sqlalchemy import (
    Boolean,
    Column,
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    String,
    func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class Paciente(Base):
    __tablename__ = "pacientes"

    id_paciente = Column(BigInteger, primary_key=True, index=True)
    ci = Column(String(30))
    ci_complemento = Column(String(5))
    sin_ci = Column(Boolean, nullable=False, default=False)
    nombres = Column(String(100), nullable=False)
    apellido_paterno = Column(String(100), nullable=False)
    apellido_materno = Column(String(100))
    fecha_nacimiento = Column(Date)
    sexo = Column(String(1), nullable=False)
    telefono = Column(String(30))
    creado_por = Column(BigInteger, ForeignKey("laboratorio.usuarios.id_usuario"), nullable=False)
    creado_en = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    actualizado_en = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    usuario_creador = relationship("Usuario", foreign_keys=[creado_por])
    ordenes = relationship("Orden", back_populates="paciente")
