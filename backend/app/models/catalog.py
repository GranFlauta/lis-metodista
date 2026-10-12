"""
Modelos ORM para el catálogo (estudios, versiones, parámetros, rangos, perfiles).
Alineados estrictamente con db/init/001_schema.sql.
"""
from sqlalchemy import (
    Boolean,
    Column,
    BigInteger,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    DateTime,
    ForeignKey,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class Estudio(Base):
    __tablename__ = "estudios"

    id_estudio = Column(BigInteger, primary_key=True, index=True)
    codigo = Column(String(60), unique=True, nullable=False)
    nombre = Column(String(150), nullable=False)
    categoria = Column(String(80), nullable=False)
    seleccion_parcial = Column(Boolean, nullable=False, default=False)
    activo = Column(Boolean, nullable=False, default=True)

    versiones = relationship("EstudioVersion", back_populates="estudio")


class EstudioVersion(Base):
    __tablename__ = "estudio_versiones"

    id_estudio_version = Column(BigInteger, primary_key=True, index=True)
    id_estudio = Column(BigInteger, ForeignKey("estudios.id_estudio"), nullable=False)
    numero_version = Column(Integer, nullable=False, default=1)
    configuracion_json = Column(JSONB, nullable=False, default=dict)
    activa = Column(Boolean, nullable=False, default=True)
    creado_en = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    estudio = relationship("Estudio", back_populates="versiones")
    parametros = relationship("Parametro", back_populates="estudio_version", order_by="Parametro.orden_visualizacion")


class Parametro(Base):
    __tablename__ = "parametros"

    id_parametro = Column(BigInteger, primary_key=True, index=True)
    id_estudio_version = Column(BigInteger, ForeignKey("estudio_versiones.id_estudio_version"), nullable=False)
    codigo = Column(String(80), nullable=False)
    nombre = Column(String(150), nullable=False)
    grupo = Column(String(60))
    tipo_campo = Column(String(30), nullable=False)
    unidad_medida = Column(String(30))
    decimales = Column(SmallInteger, nullable=False, default=2)
    formula_expresion = Column(Text)
    opciones = Column(JSONB)
    valor_defecto = Column(Text)
    requiere_confirmacion = Column(Boolean, nullable=False, default=False)
    metodo = Column(String(120))
    muestra = Column(String(80))
    obligatorio = Column(Boolean, nullable=False, default=True)
    orden_visualizacion = Column(Integer, nullable=False, default=1)

    estudio_version = relationship("EstudioVersion", back_populates="parametros")
    rangos_referencia = relationship("RangoReferencia", back_populates="parametro", cascade="all, delete-orphan")


class RangoReferencia(Base):
    __tablename__ = "rangos_referencia"

    id_rango_referencia = Column(BigInteger, primary_key=True, index=True)
    id_parametro = Column(BigInteger, ForeignKey("parametros.id_parametro", ondelete="CASCADE"), nullable=False)
    sexo = Column(String(1))
    edad_min_meses = Column(Integer)
    edad_max_meses = Column(Integer)
    limite_inferior = Column(Numeric(18, 4))
    inferior_inclusivo = Column(Boolean, nullable=False, default=True)
    limite_superior = Column(Numeric(18, 4))
    superior_inclusivo = Column(Boolean, nullable=False, default=True)
    referencia_texto = Column(Text)
    requiere_validacion = Column(Boolean, nullable=False, default=False)

    parametro = relationship("Parametro", back_populates="rangos_referencia")


class Perfil(Base):
    __tablename__ = "perfiles"

    id_perfil = Column(BigInteger, primary_key=True, index=True)
    codigo = Column(String(50), unique=True, nullable=False)
    nombre = Column(String(150), nullable=False)
    descripcion = Column(Text)
    activo = Column(Boolean, nullable=False, default=True)

    estudios_asociados = relationship(
        "PerfilEstudio",
        back_populates="perfil",
        order_by="PerfilEstudio.orden_visualizacion",
        cascade="all, delete-orphan",
    )


class PerfilEstudio(Base):
    __tablename__ = "perfil_estudios"

    id_perfil = Column(BigInteger, ForeignKey("perfiles.id_perfil", ondelete="CASCADE"), primary_key=True)
    id_estudio = Column(BigInteger, ForeignKey("estudios.id_estudio"), primary_key=True)
    grupos = Column(ARRAY(Text))
    orden_visualizacion = Column(Integer, nullable=False, default=1)

    perfil = relationship("Perfil", back_populates="estudios_asociados")
    estudio = relationship("Estudio")
