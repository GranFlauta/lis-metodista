"""
Modelos ORM para Órdenes en borrador y tablas hijas.
Alineados estrictamente con db/init/001_schema.sql.
"""
from sqlalchemy import (
    Boolean,
    Column,
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class Orden(Base):
    __tablename__ = "ordenes"

    id_orden = Column(BigInteger, primary_key=True, index=True)
    id_paciente = Column(BigInteger, ForeignKey("pacientes.id_paciente"), nullable=False, index=True)
    numero_orden_paciente = Column(Integer, nullable=False)
    id_usuario_autor = Column(BigInteger, ForeignKey("laboratorio.usuarios.id_usuario"), nullable=False, index=True)
    id_perfil = Column(BigInteger, ForeignKey("perfiles.id_perfil"))
    origen_solicitud = Column(String(100))
    medico_solicitante = Column(String(150))
    pieza = Column(String(100))
    edad_anios = Column(SmallInteger)
    edad_meses = Column(SmallInteger)
    fecha_solicitud = Column(Date, server_default=func.current_date(), nullable=False)
    fecha_hora_toma_muestra = Column(DateTime(timezone=True))
    estado_trabajo = Column(String(20), nullable=False, default="INCOMPLETO")
    bloqueada = Column(Boolean, nullable=False, default=False)
    bloqueada_por_informe = Column(BigInteger)
    bloqueada_en = Column(DateTime(timezone=True))
    fila_version = Column(Integer, nullable=False, default=1)
    observaciones = Column(Text)
    creado_en = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    actualizado_en = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    paciente = relationship("Paciente", back_populates="ordenes")
    autor = relationship("Usuario", foreign_keys=[id_usuario_autor])
    perfil = relationship("Perfil")
    estudios = relationship("OrdenEstudio", back_populates="orden", cascade="all, delete-orphan")


class OrdenEstudio(Base):
    __tablename__ = "orden_estudios"

    id_orden_estudio = Column(BigInteger, primary_key=True, index=True)
    id_orden = Column(BigInteger, ForeignKey("ordenes.id_orden", ondelete="CASCADE"), nullable=False)
    id_estudio = Column(BigInteger, ForeignKey("estudios.id_estudio"), nullable=False)
    id_estudio_version = Column(BigInteger, ForeignKey("estudio_versiones.id_estudio_version"), nullable=False)
    observaciones = Column(Text)

    orden = relationship("Orden", back_populates="estudios")
    estudio = relationship("Estudio")
    estudio_version = relationship("EstudioVersion")
    grupos = relationship("OrdenEstudioGrupo", back_populates="orden_estudio", cascade="all, delete-orphan")
    resultados = relationship("ResultadoBorrador", back_populates="orden_estudio", cascade="all, delete-orphan")


class OrdenEstudioGrupo(Base):
    __tablename__ = "orden_estudio_grupos"

    id_orden_estudio = Column(BigInteger, ForeignKey("orden_estudios.id_orden_estudio", ondelete="CASCADE"), primary_key=True)
    grupo = Column(String(60), primary_key=True)

    orden_estudio = relationship("OrdenEstudio", back_populates="grupos")


class BorradorDescartado(Base):
    __tablename__ = "borradores_descartados"

    id_descarte = Column(BigInteger, primary_key=True, index=True)
    id_orden = Column(BigInteger, nullable=False)
    id_paciente = Column(BigInteger, nullable=False)
    id_usuario = Column(BigInteger, ForeignKey("laboratorio.usuarios.id_usuario"), nullable=False)
    estado_trabajo = Column(String(20), nullable=False)
    estaba_bloqueada = Column(Boolean, nullable=False)
    folio_causa = Column(String(20))
    descartado_en = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    usuario = relationship("Usuario", foreign_keys=[id_usuario])
