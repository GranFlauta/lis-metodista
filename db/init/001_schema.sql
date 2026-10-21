-- =============================================================================
-- LIS Laboratorio Clínico - Esquema v1 (PostgreSQL 14+)
-- Reemplaza el DDL del documento original. Ver docs/DECISIONES.md para el porqué.
--
-- Principios
--   1. orden  = trabajo (borrador, privado).   informe = documento oficial.
--   2. El folio vive en `folios` (nunca se reutiliza) y la versión es del INFORME,
--      no del estudio:  UNIQUE(folio, numero_version) + CHECK(numero_version <= 3).
--   3. Los borradores se borran físicamente (ON DELETE CASCADE). Todo lo que
--      tiene folio es inmutable y se audita en `informe_eventos` (append-only).
--   4. Vacío = NULL, nunca 0.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;

CREATE SCHEMA IF NOT EXISTS laboratorio;
SET search_path TO laboratorio, public;

-- Mantiene actualizado_en
CREATE OR REPLACE FUNCTION set_actualizado_en() RETURNS trigger AS $$
BEGIN
    NEW.actualizado_en := NOW();
    RETURN NEW;
END $$ LANGUAGE plpgsql;

-- -----------------------------------------------------------------------------
-- 1. USUARIOS, ROLES, SESIONES, SEGURIDAD
-- -----------------------------------------------------------------------------
CREATE TABLE roles (
    id_rol      SMALLSERIAL PRIMARY KEY,
    nombre      VARCHAR(30) NOT NULL UNIQUE,
    descripcion TEXT
);
INSERT INTO roles (nombre, descripcion) VALUES
    ('ADMIN',      'Gestiona usuarios y consulta; NO edita trabajos de bioquímicos'),
    ('BIOQUIMICO', 'Calcula, publica y firma informes');

CREATE TABLE usuarios (
    id_usuario            BIGSERIAL PRIMARY KEY,
    id_rol                SMALLINT     NOT NULL REFERENCES roles(id_rol),
    usuario               CITEXT       NOT NULL UNIQUE,             -- login
    ci                    VARCHAR(30)  NOT NULL UNIQUE,
    nombres               VARCHAR(100) NOT NULL,
    apellido_paterno      VARCHAR(100) NOT NULL,
    apellido_materno      VARCHAR(100),
    correo                CITEXT UNIQUE,
    matricula_profesional VARCHAR(50),                              -- sale en el informe junto al nombre
    firma_imagen          BYTEA,                                    -- PNG de la firma (opcional)
    hash_password         VARCHAR(255) NOT NULL,                    -- Argon2id (nunca texto/encriptado reversible)
    debe_cambiar_password BOOLEAN      NOT NULL DEFAULT TRUE,       -- TRUE al crear y al resetear el admin
    intentos_fallidos     SMALLINT     NOT NULL DEFAULT 0,
    bloqueado_hasta       TIMESTAMPTZ,
    ultimo_login          TIMESTAMPTZ,
    activo                BOOLEAN      NOT NULL DEFAULT TRUE,       -- baja LÓGICA: nunca DELETE de usuarios
    creado_en             TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    actualizado_en        TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE TRIGGER trg_usuarios_upd BEFORE UPDATE ON usuarios
    FOR EACH ROW EXECUTE FUNCTION set_actualizado_en();

-- Sesiones con latido: si no hay latido en N segundos la sesión expira
-- (cubre "cerró la pestaña" y "apagó la PC", que el navegador no puede notificar).
CREATE TABLE sesiones (
    id_sesion     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    id_usuario    BIGINT      NOT NULL REFERENCES usuarios(id_usuario),
    refresh_hash  CHAR(64)    NOT NULL,
    ip            INET,
    user_agent    TEXT,
    creada_en     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ultimo_latido TIMESTAMPTZ NOT NULL DEFAULT NOW(),                -- la pestaña sigue abierta
    ultima_actividad TIMESTAMPTZ NOT NULL DEFAULT NOW(),             -- el USUARIO hizo algo (no cuenta el latido)
    expira_en     TIMESTAMPTZ NOT NULL,                              -- tope absoluto
    revocada_en   TIMESTAMPTZ
);
CREATE INDEX ix_sesiones_usuario ON sesiones(id_usuario) WHERE revocada_en IS NULL;

-- Eventos de seguridad (NO llevan folio). Distinto de informe_eventos.
CREATE TABLE log_seguridad (
    id_log      BIGSERIAL PRIMARY KEY,
    id_usuario  BIGINT REFERENCES usuarios(id_usuario),              -- quien actúa
    id_objetivo BIGINT REFERENCES usuarios(id_usuario),              -- sobre quién
    accion      VARCHAR(40) NOT NULL CHECK (accion IN (
        'LOGIN_OK','LOGIN_FALLIDO','LOGOUT','SESION_EXPIRADA','CAMBIO_PASSWORD',
        'RESET_PASSWORD_ADMIN','USUARIO_CREADO','USUARIO_EDITADO','USUARIO_DESACTIVADO',
        'ADMIN_VE_PRIVADO')),                                         -- admin mirando pendientes/colaborativos ajenos
    ip          INET,
    detalle     JSONB,
    creado_en   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- 2. CATÁLOGO (estudios, parámetros, rangos, perfiles)
-- -----------------------------------------------------------------------------
CREATE TABLE estudios (
    id_estudio        BIGSERIAL PRIMARY KEY,
    codigo            VARCHAR(60)  NOT NULL UNIQUE,
    nombre            VARCHAR(150) NOT NULL,
    categoria         VARCHAR(80)  NOT NULL,
    seleccion_parcial BOOLEAN      NOT NULL DEFAULT FALSE,           -- TRUE: se piden por grupo (Inmunoserología)
    activo            BOOLEAN      NOT NULL DEFAULT TRUE
);

CREATE TABLE estudio_versiones (            -- cambia una fórmula/rango => nueva versión, las viejas no se tocan
    id_estudio_version BIGSERIAL PRIMARY KEY,
    id_estudio         BIGINT  NOT NULL REFERENCES estudios(id_estudio),
    numero_version     INTEGER NOT NULL DEFAULT 1 CHECK (numero_version >= 1),
    configuracion_json JSONB   NOT NULL DEFAULT '{}'::jsonb,         -- {"reglas":[...]} validaciones cruzadas
    activa             BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (id_estudio, numero_version)
);
-- Solo una versión activa por estudio
CREATE UNIQUE INDEX uq_estudio_version_activa ON estudio_versiones(id_estudio) WHERE activa;

CREATE TABLE parametros (
    id_parametro        BIGSERIAL PRIMARY KEY,
    id_estudio_version  BIGINT NOT NULL REFERENCES estudio_versiones(id_estudio_version),
    codigo              VARCHAR(80)  NOT NULL,
    nombre              VARCHAR(150) NOT NULL,
    grupo               VARCHAR(60),                                  -- sección/prueba dentro del estudio
    tipo_campo          VARCHAR(30)  NOT NULL CHECK (tipo_campo IN
                        ('NUMERICO','TEXTO_LIBRE','SELECCION','RECUENTO_MICROSCOPICO','CALCULADO','FECHA')),
    unidad_medida       VARCHAR(30),
    decimales           SMALLINT     NOT NULL DEFAULT 2 CHECK (decimales BETWEEN 0 AND 6),
    formula_expresion   TEXT,                                         -- se evalúa con el motor seguro (sin eval)
    opciones            JSONB,                                        -- para SELECCION
    valor_defecto       TEXT,
    requiere_confirmacion BOOLEAN    NOT NULL DEFAULT FALSE,          -- default que el bioquímico debe confirmar
    metodo              VARCHAR(120),
    muestra             VARCHAR(80),
    obligatorio         BOOLEAN      NOT NULL DEFAULT TRUE,
    orden_visualizacion INTEGER      NOT NULL DEFAULT 1,
    UNIQUE (id_estudio_version, codigo),
    CHECK ((tipo_campo = 'CALCULADO') = (formula_expresion IS NOT NULL)),
    CHECK (tipo_campo <> 'SELECCION' OR opciones IS NOT NULL),
    CHECK (NOT requiere_confirmacion OR valor_defecto IS NOT NULL)
);

CREATE TABLE rangos_referencia (
    id_rango_referencia BIGSERIAL PRIMARY KEY,
    id_parametro        BIGINT NOT NULL REFERENCES parametros(id_parametro) ON DELETE CASCADE,
    sexo                CHAR(1) CHECK (sexo IN ('M','F')),            -- NULL = ambos
    edad_min_meses      INTEGER,                                      -- NULL = sin límite (rangos pediátricos futuros)
    edad_max_meses      INTEGER,
    limite_inferior     NUMERIC(18,4),
    inferior_inclusivo  BOOLEAN NOT NULL DEFAULT TRUE,
    limite_superior     NUMERIC(18,4),
    superior_inclusivo  BOOLEAN NOT NULL DEFAULT TRUE,
    referencia_texto    TEXT,                                         -- lo que se imprime ("Menor a 200")
    requiere_validacion BOOLEAN NOT NULL DEFAULT FALSE,               -- valor en conflicto en el Excel
    CHECK (limite_inferior IS NULL OR limite_superior IS NULL OR limite_inferior <= limite_superior)
);
CREATE INDEX ix_rangos_parametro ON rangos_referencia(id_parametro);

-- Perfil = atajo de pedido (preselecciona estudios). NO es la plantilla de impresión.
CREATE TABLE perfiles (
    id_perfil   BIGSERIAL PRIMARY KEY,
    codigo      VARCHAR(50)  NOT NULL UNIQUE,
    nombre      VARCHAR(150) NOT NULL,
    descripcion TEXT,
    activo      BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE TABLE perfil_estudios (
    id_perfil           BIGINT NOT NULL REFERENCES perfiles(id_perfil) ON DELETE CASCADE,
    id_estudio          BIGINT NOT NULL REFERENCES estudios(id_estudio),
    grupos              TEXT[],                                       -- NULL = todo el estudio; si no, solo esos grupos
    orden_visualizacion INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (id_perfil, id_estudio)
);

-- -----------------------------------------------------------------------------
-- 3. PACIENTES Y ÓRDENES (trabajo = borrador privado)
-- -----------------------------------------------------------------------------
CREATE TABLE pacientes (
    id_paciente      BIGSERIAL PRIMARY KEY,
    ci               VARCHAR(30),                                     -- NULL si no tiene (RN, extranjero, urgencia)
    ci_complemento   VARCHAR(5),
    sin_ci           BOOLEAN      NOT NULL DEFAULT FALSE,
    nombres          VARCHAR(100) NOT NULL,
    apellido_paterno VARCHAR(100) NOT NULL,
    apellido_materno VARCHAR(100),
    fecha_nacimiento DATE,                                            -- opcional: la edad se guarda en la orden
    sexo             CHAR(1)      NOT NULL CHECK (sexo IN ('M','F')),
    telefono         VARCHAR(30),
    creado_por       BIGINT       NOT NULL REFERENCES usuarios(id_usuario),
    creado_en        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    actualizado_en   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CHECK ((ci IS NOT NULL) <> sin_ci)                                -- o tiene CI, o está marcado sin CI
);
CREATE UNIQUE INDEX uq_paciente_ci ON pacientes(ci, COALESCE(ci_complemento, '')) WHERE ci IS NOT NULL;
CREATE INDEX ix_pacientes_nombre ON pacientes (apellido_paterno, apellido_materno, nombres);
CREATE TRIGGER trg_pacientes_upd BEFORE UPDATE ON pacientes
    FOR EACH ROW EXECUTE FUNCTION set_actualizado_en();

CREATE TABLE ordenes (
    id_orden               BIGSERIAL PRIMARY KEY,
    id_paciente            BIGINT NOT NULL REFERENCES pacientes(id_paciente),
    numero_orden_paciente  INTEGER NOT NULL CHECK (numero_orden_paciente >= 1),  -- Orden N° 1, 2, 3 del paciente
    id_usuario_autor       BIGINT NOT NULL REFERENCES usuarios(id_usuario),
    id_perfil              BIGINT REFERENCES perfiles(id_perfil),
    origen_solicitud       VARCHAR(100),                              -- Neurología, Enfermería...
    medico_solicitante     VARCHAR(150),
    pieza                  VARCHAR(100),
    edad_anios             SMALLINT CHECK (edad_anios BETWEEN 0 AND 130),    -- edad AL MOMENTO de la orden
    edad_meses             SMALLINT CHECK (edad_meses BETWEEN 0 AND 11),
    fecha_solicitud        DATE NOT NULL DEFAULT CURRENT_DATE,
    fecha_hora_toma_muestra TIMESTAMPTZ,
    -- Trabajo. La publicación vive en `informes`; aquí solo el avance del borrador.
    estado_trabajo         VARCHAR(20) NOT NULL DEFAULT 'INCOMPLETO'
                           CHECK (estado_trabajo IN ('INCOMPLETO','COMPLETO','PUBLICADA')),
    -- Bloqueo por concurrencia: NO pisa estado_trabajo, así se conserva el avance real.
    bloqueada              BOOLEAN NOT NULL DEFAULT FALSE,
    bloqueada_por_informe  BIGINT,                                    -- FK abajo (informes se crea después)
    bloqueada_en           TIMESTAMPTZ,
    fila_version           INTEGER NOT NULL DEFAULT 1,                -- bloqueo optimista (409 si cambió)
    creado_en              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actualizado_en         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (id_paciente, numero_orden_paciente),
    CHECK (NOT bloqueada OR (bloqueada_por_informe IS NOT NULL AND bloqueada_en IS NOT NULL))
);
CREATE INDEX ix_ordenes_autor_estado ON ordenes(id_usuario_autor, estado_trabajo);
CREATE INDEX ix_ordenes_paciente ON ordenes(id_paciente);
CREATE TRIGGER trg_ordenes_upd BEFORE UPDATE ON ordenes
    FOR EACH ROW EXECUTE FUNCTION set_actualizado_en();

-- Una orden NO puede existir sin estudios: se valida al crearla (servicio, misma transacción)
-- y con este constraint trigger al hacer COMMIT.
CREATE TABLE orden_estudios (
    id_orden_estudio   BIGSERIAL PRIMARY KEY,
    id_orden           BIGINT NOT NULL REFERENCES ordenes(id_orden) ON DELETE CASCADE,
    id_estudio         BIGINT NOT NULL REFERENCES estudios(id_estudio),
    id_estudio_version BIGINT NOT NULL REFERENCES estudio_versiones(id_estudio_version),  -- versión del catálogo congelada
    UNIQUE (id_orden, id_estudio)
);
CREATE TABLE orden_estudio_grupos (            -- solo estudios con seleccion_parcial (Inmunoserología)
    id_orden_estudio BIGINT NOT NULL REFERENCES orden_estudios(id_orden_estudio) ON DELETE CASCADE,
    grupo            VARCHAR(60) NOT NULL,
    PRIMARY KEY (id_orden_estudio, grupo)
);

CREATE OR REPLACE FUNCTION validar_orden_con_estudios() RETURNS trigger AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM ordenes o WHERE o.id_orden = NEW.id_orden)
       AND NOT EXISTS (SELECT 1 FROM orden_estudios oe WHERE oe.id_orden = NEW.id_orden) THEN
        RAISE EXCEPTION 'La orden % no tiene estudios asignados', NEW.id_orden;
    END IF;
    RETURN NULL;
END $$ LANGUAGE plpgsql;
CREATE CONSTRAINT TRIGGER trg_orden_requiere_estudios
    AFTER INSERT ON ordenes DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION validar_orden_con_estudios();

-- -----------------------------------------------------------------------------
-- 4. FOLIOS, INFORMES (documento oficial), VERSIONES
-- -----------------------------------------------------------------------------
-- Contador SIN huecos por año: se incrementa dentro de la transacción de publicación
-- (si la transacción falla, el incremento también se revierte). Un folio nunca se reutiliza.
CREATE TABLE contadores_folio (
    anio   SMALLINT PRIMARY KEY,
    ultimo INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE folios (
    folio      VARCHAR(20) PRIMARY KEY,                               -- 'AAAA-NNNNNN'  p.ej. 2026-000123
    anio       SMALLINT    NOT NULL,
    correlativo INTEGER    NOT NULL,
    creado_en  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (anio, correlativo)
);

CREATE OR REPLACE FUNCTION siguiente_folio() RETURNS VARCHAR AS $$
DECLARE
    v_anio SMALLINT := EXTRACT(YEAR FROM NOW())::SMALLINT;
    v_n    INTEGER;
    v_folio VARCHAR(20);
BEGIN
    INSERT INTO contadores_folio(anio, ultimo) VALUES (v_anio, 1)
    ON CONFLICT (anio) DO UPDATE SET ultimo = contadores_folio.ultimo + 1
    RETURNING ultimo INTO v_n;                                         -- bloquea la fila: serializa la publicación
    v_folio := v_anio::TEXT || '-' || LPAD(v_n::TEXT, 6, '0');
    INSERT INTO folios(folio, anio, correlativo) VALUES (v_folio, v_anio, v_n);
    RETURN v_folio;
END $$ LANGUAGE plpgsql;

CREATE TABLE informes (
    id_informe        BIGSERIAL PRIMARY KEY,
    folio             VARCHAR(20) NOT NULL REFERENCES folios(folio),
    numero_version    SMALLINT    NOT NULL CHECK (numero_version BETWEEN 1 AND 3),   -- CANDADO: máx. V3
    id_orden          BIGINT      NOT NULL REFERENCES ordenes(id_orden),
    estado            VARCHAR(12) NOT NULL DEFAULT 'VIGENTE'
                      CHECK (estado IN ('VIGENTE','DESPLAZADO','PAPELERA','RECICLAJE')),
    -- Responsabilidad legal: el informe impreso lleva SIEMPRE al autor original (A),
    -- aunque lo haya publicado el colaborador (B).
    id_usuario_firmante  BIGINT NOT NULL REFERENCES usuarios(id_usuario),
    id_usuario_publicador BIGINT NOT NULL REFERENCES usuarios(id_usuario),
    es_urgencia       BOOLEAN NOT NULL DEFAULT FALSE,
    justificativo     TEXT,                                           -- obligatorio en V2/V3 y en urgencia
    snapshot_json     JSONB   NOT NULL,                               -- valores, rangos, unidades, fórmulas, aportes colaborativos
    snapshot_sha256   CHAR(64) NOT NULL,
    publicado_en      TIMESTAMPTZ NOT NULL DEFAULT NOW(),             -- = fecha/hora de entrega del informe
    reemplaza_a_folio VARCHAR(20) REFERENCES folios(folio),           -- informe nuevo creado tras mandar otro a papelera
    UNIQUE (folio, numero_version),
    CHECK (numero_version = 1 OR justificativo IS NOT NULL),
    CHECK (NOT es_urgencia OR justificativo IS NOT NULL)
);
-- Un folio tiene como máximo UNA versión que no esté desplazada
CREATE UNIQUE INDEX uq_informe_version_actual ON informes(folio) WHERE estado <> 'DESPLAZADO';
CREATE INDEX ix_informes_orden  ON informes(id_orden);
CREATE INDEX ix_informes_estado ON informes(estado, publicado_en DESC);
CREATE INDEX ix_informes_firmante ON informes(id_usuario_firmante);

ALTER TABLE ordenes ADD CONSTRAINT fk_orden_bloqueada_por
    FOREIGN KEY (bloqueada_por_informe) REFERENCES informes(id_informe);

-- Inmutabilidad: del informe solo puede cambiar `estado` (vigente/desplazado/papelera/reciclaje).
CREATE OR REPLACE FUNCTION proteger_informe() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Los informes oficiales no se eliminan (folio %)', OLD.folio;
    END IF;
    IF NEW.folio IS DISTINCT FROM OLD.folio
       OR NEW.numero_version IS DISTINCT FROM OLD.numero_version
       OR NEW.id_orden IS DISTINCT FROM OLD.id_orden
       OR NEW.snapshot_json IS DISTINCT FROM OLD.snapshot_json
       OR NEW.snapshot_sha256 IS DISTINCT FROM OLD.snapshot_sha256
       OR NEW.id_usuario_firmante IS DISTINCT FROM OLD.id_usuario_firmante
       OR NEW.id_usuario_publicador IS DISTINCT FROM OLD.id_usuario_publicador
       OR NEW.justificativo IS DISTINCT FROM OLD.justificativo
       OR NEW.publicado_en IS DISTINCT FROM OLD.publicado_en THEN
        RAISE EXCEPTION 'El contenido de un informe oficial es inmutable (folio %)', OLD.folio;
    END IF;
    RETURN NEW;
END $$ LANGUAGE plpgsql;
CREATE TRIGGER trg_proteger_informe BEFORE UPDATE OR DELETE ON informes
    FOR EACH ROW EXECUTE FUNCTION proteger_informe();

CREATE OR REPLACE FUNCTION proteger_folio() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'Los folios no se modifican ni se eliminan';
END $$ LANGUAGE plpgsql;
CREATE TRIGGER trg_proteger_folio BEFORE UPDATE OR DELETE ON folios
    FOR EACH ROW EXECUTE FUNCTION proteger_folio();

-- -----------------------------------------------------------------------------
-- 5. RESULTADOS EN BORRADOR (pendientes y ediciones de versión)
-- -----------------------------------------------------------------------------
-- Edición de un informe oficial (V1->V2, V2->V3): se trabaja sobre una COPIA.
-- Mientras no se publica, el informe vigente sigue siendo el visible.
CREATE TABLE ediciones_informe (
    id_edicion       BIGSERIAL PRIMARY KEY,
    id_informe_base  BIGINT NOT NULL REFERENCES informes(id_informe),
    id_usuario       BIGINT NOT NULL REFERENCES usuarios(id_usuario),
    justificativo    TEXT   NOT NULL,
    creada_en        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- Una sola edición abierta por informe
CREATE UNIQUE INDEX uq_edicion_abierta ON ediciones_informe(id_informe_base);

CREATE TABLE resultados_borrador (
    id_resultado     BIGSERIAL PRIMARY KEY,
    id_orden_estudio BIGINT NOT NULL REFERENCES orden_estudios(id_orden_estudio) ON DELETE CASCADE,
    id_edicion       BIGINT REFERENCES ediciones_informe(id_edicion) ON DELETE CASCADE, -- NULL = borrador de la orden
    id_parametro     BIGINT NOT NULL REFERENCES parametros(id_parametro),
    valor_numerico   NUMERIC(20,6),
    valor_texto      TEXT,
    es_calculado     BOOLEAN NOT NULL DEFAULT FALSE,
    calculable       BOOLEAN NOT NULL DEFAULT TRUE,                   -- FALSE = "No calculable" (no se guarda 0)
    confirmado       BOOLEAN NOT NULL DEFAULT TRUE,                   -- FALSE = valor por defecto sin confirmar (bloquea publicar)
    actualizado_por  BIGINT NOT NULL REFERENCES usuarios(id_usuario),
    actualizado_en   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (valor_numerico IS NULL OR valor_texto IS NULL)
);
CREATE UNIQUE INDEX uq_resultado_orden   ON resultados_borrador(id_orden_estudio, id_parametro) WHERE id_edicion IS NULL;
CREATE UNIQUE INDEX uq_resultado_edicion ON resultados_borrador(id_orden_estudio, id_parametro, id_edicion) WHERE id_edicion IS NOT NULL;

-- -----------------------------------------------------------------------------
-- 6. DELEGACIÓN / COLABORACIÓN (máx. 2 usuarios por orden)
-- -----------------------------------------------------------------------------
CREATE TABLE delegaciones (
    id_delegacion          BIGSERIAL PRIMARY KEY,
    id_orden               BIGINT NOT NULL REFERENCES ordenes(id_orden) ON DELETE CASCADE,
    id_usuario_autor       BIGINT NOT NULL REFERENCES usuarios(id_usuario),
    id_usuario_colaborador BIGINT NOT NULL REFERENCES usuarios(id_usuario),
    estado                 VARCHAR(12) NOT NULL DEFAULT 'SOLICITADA'
                           CHECK (estado IN ('SOLICITADA','ACEPTADA','RECHAZADA','REVOCADA','FINALIZADA')),
    solicitada_en          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    respondida_en          TIMESTAMPTZ,
    finalizada_en          TIMESTAMPTZ,
    CHECK (id_usuario_autor <> id_usuario_colaborador)
);
-- Máximo UNA delegación viva por orden => máximo 2 personas
CREATE UNIQUE INDEX uq_delegacion_viva ON delegaciones(id_orden) WHERE estado IN ('SOLICITADA','ACEPTADA');

-- Historial append-only de cambios (de ahí salen los colores rojo/azul).
-- NO se borra al publicar: queda ligado al folio como evidencia de quién tipeó qué.
CREATE TABLE colaboracion_cambios (
    id_cambio       BIGSERIAL PRIMARY KEY,
    id_orden        BIGINT NOT NULL REFERENCES ordenes(id_orden) ON DELETE CASCADE,
    id_parametro    BIGINT NOT NULL REFERENCES parametros(id_parametro),
    id_usuario      BIGINT NOT NULL REFERENCES usuarios(id_usuario),
    rol             VARCHAR(12) NOT NULL CHECK (rol IN ('AUTOR','COLABORADOR')),
    valor_anterior  TEXT,
    valor_nuevo     TEXT,
    folio           VARCHAR(20) REFERENCES folios(folio),             -- se completa al publicar
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_colab_orden ON colaboracion_cambios(id_orden, id_parametro, creado_en);
CREATE INDEX ix_colab_folio ON colaboracion_cambios(folio) WHERE folio IS NOT NULL;

-- -----------------------------------------------------------------------------
-- 7. AUDITORÍA DE DOCUMENTOS OFICIALES (todo lo que tiene folio)
-- -----------------------------------------------------------------------------
-- Reemplaza papelera_ordenes + auditoria_actividad_log. Alimenta el reporte PDF.
CREATE TABLE informe_eventos (
    id_evento       BIGSERIAL PRIMARY KEY,
    folio           VARCHAR(20) NOT NULL REFERENCES folios(folio),    -- OBLIGATORIO
    numero_version  SMALLINT,
    id_usuario      BIGINT NOT NULL REFERENCES usuarios(id_usuario),
    accion          VARCHAR(20) NOT NULL CHECK (accion IN (
        'PUBLICACION','URGENCIA','EDICION_V2','EDICION_V3','PAPELERA','RESTAURACION','IMPRESION')),
    justificativo   TEXT,
    detalle         JSONB,
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (accion NOT IN ('URGENCIA','EDICION_V2','EDICION_V3','PAPELERA','RESTAURACION')
           OR justificativo IS NOT NULL)
);
CREATE INDEX ix_eventos_fecha ON informe_eventos(creado_en);
CREATE INDEX ix_eventos_folio ON informe_eventos(folio);

CREATE OR REPLACE FUNCTION proteger_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'La tabla % es append-only', TG_TABLE_NAME;
END $$ LANGUAGE plpgsql;
CREATE TRIGGER trg_eventos_append_only BEFORE UPDATE OR DELETE ON informe_eventos
    FOR EACH ROW EXECUTE FUNCTION proteger_append_only();

-- Descarte de borradores (sin contenido clínico): evita que "desaparezca sin rastro"
-- un borrador bloqueado por una urgencia. NO entra al reporte de actividad.
CREATE TABLE borradores_descartados (
    id_descarte   BIGSERIAL PRIMARY KEY,
    id_orden      BIGINT NOT NULL,                                     -- sin FK: la orden ya no existe
    id_paciente   BIGINT NOT NULL,
    id_usuario    BIGINT NOT NULL REFERENCES usuarios(id_usuario),
    estado_trabajo VARCHAR(20) NOT NULL,
    estaba_bloqueada BOOLEAN NOT NULL,
    folio_causa   VARCHAR(20) REFERENCES folios(folio),                -- folio de la urgencia que lo bloqueó
    descartado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- 8. CONFIGURACIÓN DEL LABORATORIO (encabezado/pie del informe)
-- -----------------------------------------------------------------------------
CREATE TABLE laboratorio_config (
    clave          VARCHAR(60) PRIMARY KEY,
    valor          TEXT NOT NULL,
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
INSERT INTO laboratorio_config (clave, valor) VALUES
    ('nombre_laboratorio', 'LABORATORIO CLINICO METODISTA'),
    ('ruc',                ''),            -- completar
    ('telefono',           ''),            -- completar
    ('horario_atencion',   ''),            -- completar
    ('separador_decimal',  ',');           -- DECISIÓN PENDIENTE: el Excel usa coma, la imagen de referencia usa punto

-- -----------------------------------------------------------------------------
-- Ajuste final: que toda conexión de la aplicación vea el esquema `laboratorio`
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    EXECUTE format('ALTER DATABASE %I SET search_path TO laboratorio, public', current_database());
END $$;
