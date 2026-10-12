from sqlalchemy import Column, BigInteger, SmallInteger, String, Boolean, DateTime, Text, LargeBinary, ForeignKey, func
from sqlalchemy.orm import relationship
from app.core.database import Base  # O la base declarativa que uses en tu proyecto

class Rol(Base):
    __tablename__ = "roles"
    __table_args__ = {"schema": "laboratorio"}

    id_rol = Column(SmallInteger, primary_key=True, index=True)
    nombre = Column(String(30), unique=True, nullable=False)
    descripcion = Column(Text)

class Usuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = {"schema": "laboratorio"}

    id_usuario = Column(BigInteger, primary_key=True, index=True)
    id_rol = Column(SmallInteger, ForeignKey("laboratorio.roles.id_rol"), nullable=False)
    usuario = Column(String, unique=True, nullable=False)
    ci = Column(String(30), unique=True, nullable=False)
    nombres = Column(String(100), nullable=False)
    apellido_paterno = Column(String(100), nullable=False)
    apellido_materno = Column(String(100))
    correo = Column(String, unique=True)
    matricula_profesional = Column(String(50))
    firma_imagen = Column(LargeBinary)
    hash_password = Column(String(255), nullable=False)
    debe_cambiar_password = Column(Boolean, nullable=False, default=True)
    intentos_fallidos = Column(SmallInteger, nullable=False, default=0)
    bloqueado_hasta = Column(DateTime(timezone=True))
    ultimo_login = Column(DateTime(timezone=True))
    activo = Column(Boolean, nullable=False, default=True)
    creado_en = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    actualizado_en = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    rol = relationship("Rol")
