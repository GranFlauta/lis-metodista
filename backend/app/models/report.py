"""
Modelos ORM para Folios, Informes oficiales, Edición de versiones, Eventos de auditoría y Delegación.
Alineados estrictamente con db/init/001_schema.sql.
"""
from sqlalchemy import (
    Boolean,
    Column,
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class ContadorFolio(Base):
    __tablename__ = "contadores_folio"

    anio = Column(SmallInteger, primary_key=True)
    ultimo = Column(Integer, nullable=False, default=0)


class Folio(Base):
    __tablename__ = "folios"

    folio = Column(String(20), primary_key=True)
    anio = Column(SmallInteger, nullable=False)
    correlativo = Column(Integer, nullable=False)
    creado_en = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Informe(Base):
    __tablename__ = "informes"

    id_informe = Column(BigInteger, primary_key=True, index=True)
    folio = Column(String(20), ForeignKey("folios.folio"), nullable=False, index=True)
    numero_version = Column(SmallInteger, nullable=False)
    id_orden = Column(BigInteger, ForeignKey("ordenes.id_orden"), nullable=False, index=True)
    estado = Column(String(12), nullable=False, default="VIGENTE")
    id_usuario_firmante = Column(BigInteger, ForeignKey("laboratorio.usuarios.id_usuario"), nullable=False, index=True)
    id_usuario_publicador = Column(BigInteger, ForeignKey("laboratorio.usuarios.id_usuario"), nullable=False)
    es_urgencia = Column(Boolean, nullable=False, default=False)
    justificativo = Column(Text, nullable=True)
    snapshot_json = Column(JSONB, nullable=False)
    snapshot_sha256 = Column(String(64), nullable=False)
    publicado_en = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    reemplaza_a_folio = Column(String(20), ForeignKey("folios.folio"), nullable=True)

    folio_rel = relationship("Folio", foreign_keys=[folio])
    orden = relationship("Orden", foreign_keys=[id_orden])
    firmante = relationship("Usuario", foreign_keys=[id_usuario_firmante])
    publicador = relationship("Usuario", foreign_keys=[id_usuario_publicador])


class EdicionInforme(Base):
    __tablename__ = "ediciones_informe"

    id_edicion = Column(BigInteger, primary_key=True, index=True)
    id_informe_base = Column(BigInteger, ForeignKey("informes.id_informe"), nullable=False, unique=True)
    id_usuario = Column(BigInteger, ForeignKey("laboratorio.usuarios.id_usuario"), nullable=False)
    justificativo = Column(Text, nullable=False)
    creada_en = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    informe_base = relationship("Informe", foreign_keys=[id_informe_base])
    usuario = relationship("Usuario", foreign_keys=[id_usuario])


class InformeEvento(Base):
    __tablename__ = "informe_eventos"

    id_evento = Column(BigInteger, primary_key=True, index=True)
    folio = Column(String(20), ForeignKey("folios.folio"), nullable=False, index=True)
    numero_version = Column(SmallInteger, nullable=True)
    id_usuario = Column(BigInteger, ForeignKey("laboratorio.usuarios.id_usuario"), nullable=False)
    accion = Column(String(20), nullable=False)
    justificativo = Column(Text, nullable=True)
    detalle = Column(JSONB, nullable=True)
    creado_en = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    usuario = relationship("Usuario", foreign_keys=[id_usuario])


class Delegacion(Base):
    __tablename__ = "delegaciones"

    id_delegacion = Column(BigInteger, primary_key=True, index=True)
    id_orden = Column(BigInteger, ForeignKey("ordenes.id_orden", ondelete="CASCADE"), nullable=False)
    id_usuario_autor = Column(BigInteger, ForeignKey("laboratorio.usuarios.id_usuario"), nullable=False)
    id_usuario_colaborador = Column(BigInteger, ForeignKey("laboratorio.usuarios.id_usuario"), nullable=False)
    estado = Column(String(12), nullable=False, default="SOLICITADA")
    solicitada_en = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    respondida_en = Column(DateTime(timezone=True), nullable=True)
    finalizada_en = Column(DateTime(timezone=True), nullable=True)

    orden = relationship("Orden", foreign_keys=[id_orden])
    autor = relationship("Usuario", foreign_keys=[id_usuario_autor])
    colaborador = relationship("Usuario", foreign_keys=[id_usuario_colaborador])


class ColaboracionCambio(Base):
    __tablename__ = "colaboracion_cambios"

    id_cambio = Column(BigInteger, primary_key=True, index=True)
    id_orden = Column(BigInteger, ForeignKey("ordenes.id_orden", ondelete="CASCADE"), nullable=False)
    id_parametro = Column(BigInteger, ForeignKey("parametros.id_parametro"), nullable=False)
    id_usuario = Column(BigInteger, ForeignKey("laboratorio.usuarios.id_usuario"), nullable=False)
    rol = Column(String(12), nullable=False)
    valor_anterior = Column(Text, nullable=True)
    valor_nuevo = Column(Text, nullable=True)
    folio = Column(String(20), ForeignKey("folios.folio"), nullable=True)
    creado_en = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    orden = relationship("Orden", foreign_keys=[id_orden])
    parametro = relationship("Parametro", foreign_keys=[id_parametro])
    usuario = relationship("Usuario", foreign_keys=[id_usuario])
