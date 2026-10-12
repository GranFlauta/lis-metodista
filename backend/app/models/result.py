"""
Modelos ORM para Resultados en borrador y configuración del laboratorio.
Alineados estrictamente con db/init/001_schema.sql.
"""
from sqlalchemy import (
    Boolean,
    Column,
    BigInteger,
    Numeric,
    String,
    Text,
    DateTime,
    ForeignKey,
    func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class ResultadoBorrador(Base):
    __tablename__ = "resultados_borrador"

    id_resultado = Column(BigInteger, primary_key=True, index=True)
    id_orden_estudio = Column(BigInteger, ForeignKey("orden_estudios.id_orden_estudio", ondelete="CASCADE"), nullable=False, index=True)
    id_edicion = Column(BigInteger, nullable=True)  # NULL = borrador de la orden
    id_parametro = Column(BigInteger, ForeignKey("parametros.id_parametro"), nullable=False, index=True)
    valor_numerico = Column(Numeric(20, 6), nullable=True)
    valor_texto = Column(Text, nullable=True)
    es_calculado = Column(Boolean, nullable=False, default=False)
    calculable = Column(Boolean, nullable=False, default=True)
    confirmado = Column(Boolean, nullable=False, default=True)
    actualizado_por = Column(BigInteger, ForeignKey("laboratorio.usuarios.id_usuario"), nullable=False)
    actualizado_en = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    orden_estudio = relationship("OrdenEstudio", back_populates="resultados")
    parametro = relationship("Parametro")
    usuario_actualizador = relationship("Usuario", foreign_keys=[actualizado_por])


class LaboratorioConfig(Base):
    __tablename__ = "laboratorio_config"

    clave = Column(String(60), primary_key=True)
    valor = Column(Text, nullable=False)
    actualizado_en = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
