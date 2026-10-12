# PROMPT — FASE 1.5: Cierre y verificación de la Fase 1 (puerta obligatoria antes de la Fase 2)

**Cómo usarlo:** pégalo en la IA/programador **antes** de iniciar la Fase 2. No se escribe ninguna funcionalidad nueva: solo se corrige y se demuestra lo ya hecho.

=== INICIO DEL PROMPT ===

# 1. ROL Y REGLAS

Eres un ingeniero senior en un **sistema clínico**. Esta fase es de **verificación y corrección**, no de funcionalidades nuevas.

* Todo lo que afirmes debe ir acompañado de **la salida real** del comando que lo prueba. Sin salida pegada, el punto cuenta como **no hecho**.
* No inventes. Si algo no existe o no lo puedes comprobar, dilo.
* No toques `db/init/*.sql` ni `backend/app/catalog/**`.
* Un commit por tarea, mensaje en español, imperativo.
* Reglas de `AGENTS.md` siguen vigentes.

# 2. HALLAZGOS QUE MOTIVAN ESTA FASE (hechos observados en lo que se me entregó)

| # | Hallazgo | Por qué importa |
|---|---|---|
| H1 | La salida de tests enviada es un **error de arranque** (`Start directory is not importable`): se ejecutó desde la carpeta equivocada y además se escribió literalmente `con TEST_DATABASE_URL`. **No hay evidencia de ningún test ejecutado.** | El informe afirma "52 tests pasando" sin prueba |
| H2 | La clase base de los tests de integración **omite (`SkipTest`) todos los tests si PostgreSQL no responde**, y captura `except Exception`. | Un `OK` puede esconder que los 27 tests de integración **nunca corrieron** |
| H3 | Esa misma clase usa `Base.metadata.create_all(...)` para crear tablas desde los modelos ORM. | Si la BD está vacía, crea tablas **sin** los `CHECK`, índices parciales ni triggers de `001_schema.sql`; los tests pasarían sin probar el esquema real |
| H4 | El `api/auth.py` pegado en la entrega **no coincide con el informe ni con los tests**: contiene 4 endpoints (sin `/me` ni `/cambiar-password`), usa `HTTPException` con `detail` en vez de `{codigo, mensaje}`, llama a `datetime.now(...)` 5 veces, define modelos con `try/except ImportError` y `sys.modules`, usa cookie `Path="/"`, **no** exige `X-LIS-Client`, responde mensajes **distintos** para usuario inexistente / inactivo / clave errónea (enumeración de usuarios) y no verifica contra el hash ficticio. Sin embargo el `grep datetime.now` enviado dice que solo existe en `clock.py`. | O se pegó un archivo viejo, o el repositorio no está refactorizado. **Una de las dos afirmaciones es falsa** |
| H5 | `docker-compose.yml` publica `5432:5432` (PostgreSQL en **todas** las interfaces) con el comentario "La BD NO se publica al exterior". | Base de datos clínica expuesta a la red local |
| H6 | El `pip freeze` enviado muestra `fastapi==0.136.1`, `psycopg2-binary`, **sin SQLAlchemy ni psycopg 3**, mientras `requirements.txt` fija `fastapi==0.143.0`, `psycopg==3.3.6`, `SQLAlchemy==2.1.4`. El entorno del `freeze` no es el del proyecto. | La evidencia viene de otro entorno; además Python local es 3.14 y el `Dockerfile` usa `python:3.12-slim` |
| H7 | `httpx` (necesario para `TestClient`) no aparece en `requirements.txt` ni se muestra un `requirements-dev.txt`. | Los tests podrían no ser reproducibles en otra máquina |
| H8 | `DUMMY_ARGON2_HASH` es una cadena **escrita a mano**; `verify_password` captura `Exception` y devuelve `False`. Si ese hash no es válido, la verificación "ficticia" falla **al instante** y el login de usuario inexistente se vuelve más rápido que el de uno real. | Anula la protección contra enumeración por tiempo |
| H9 | `generate_temporary_password` devuelve el último candidato **aunque incumpla la política** tras 20 intentos. | Podría emitirse una temporal inválida |
| H10 | El comando de la entrega usó `<commit-de-Fase-0>` literal. Del `git log` se deduce: Fase 0 = `d9bf297`, Fase 1 = `cdc2db0`. | La verificación "no se tocó esquema/catálogo" no se hizo |
| Resuelto | `CLAVES_PROHIBIDAS` tiene las **21** entradas correctas. | — |

# 3. TAREAS (cada una con su evidencia obligatoria)

## G1 — Evidencia real de los tests (H1, H2, H3, H7)
1. Crea `scripts/crear_bd_test.sh` (compatible con Podman **y** Docker mediante una variable `CONTAINER_CLI`, valor por defecto `docker`) que: recrea la BD `lis_test` y aplica `db/init/001_schema.sql` **y** `db/init/002_seed_catalogo.sql`. Documenta su uso en `README.md`.
2. En la clase base de tests de integración:
   * Elimina `Base.metadata.create_all`.
   * Si la BD de pruebas no responde → el test **falla** con un mensaje claro (no `SkipTest`). Captura solo `sqlalchemy.exc.OperationalError`, no `Exception`.
   * En `setUpClass`, verifica que existan en el esquema `laboratorio` las tablas `usuarios`, `sesiones`, `log_seguridad`, `informes`, `folios` y el trigger `trg_proteger_informe`; si no, falla indicando que se debe ejecutar `scripts/crear_bd_test.sh`.
3. Crea `backend/requirements-dev.txt` con `httpx` (versión fijada, verificada con `pip show httpx`).
4. Ejecuta **desde `backend/`**, con el entorno virtual del proyecto y `TEST_DATABASE_URL` realmente definida:
   `cd backend && python -m unittest discover -s tests -v`
   **Evidencia:** la salida completa, con `Ran N tests`, `OK`, y **ninguna** línea `skipped`. Si algún test falla, corrige el **código**, no el test (salvo que el test contradiga el prompt de Fase 1; entonces repórtalo).
5. Pega además: `python --version` y `pip freeze` **del entorno virtual** usado en el punto 4.

## G2 — Resolver la contradicción de `auth.py` (H4)
1. Pega **íntegros** los archivos reales: `git show HEAD:backend/app/api/auth.py` y `git show HEAD:backend/app/api/deps.py`.
2. Verifica que cumplan el prompt de Fase 1 §6.2. Si el archivo real es el descrito en H4, **reescríbelo** según §6.2 de `PROMPT_FASE_1.md` (los tests existentes son la especificación ejecutable).
3. **Evidencia (todos deben salir como se indica):**
   * `grep -rn "datetime.now\|utcnow" backend/app --include=*.py` → solo `core/clock.py`
   * `grep -rn "HTTPException" backend/app --include=*.py` → sin resultados (se usan las clases de `core/errors.py`)
   * `grep -rn "sys.modules\|except (ImportError" backend/app --include=*.py` → sin resultados
   * `grep -n "path=" backend/app/api/auth.py` → `/api/auth`
   * `grep -rn "X-LIS-Client" backend/app --include=*.py` → presente en `refresh` y `logout`
   * `grep -n "@router" backend/app/api/auth.py` → los 6 endpoints: `login`, `refresh`, `heartbeat`, `logout`, `me`, `cambiar-password`
4. IP del cliente: no parsear `X-Forwarded-For` a mano; usar `request.client.host` y dejar que uvicorn (`--proxy-headers`) lo resuelva (el backend solo es accesible desde la red interna de Compose, ver G3).

## G3 — Superficie de red (H5)
1. Quita `5432:5432` de `docker-compose.yml`. Para desarrollo local crea `docker-compose.override.yml` con `127.0.0.1:5432:5432` (solo loopback) y documenta que **no** se usa en producción.
2. Comprueba el comportamiento de `http://lis.local:8080` (Caddy redirige a HTTPS sin el puerto 8443). Si el redireccionamiento queda roto, elimina el mapeo `8080:80`. **Evidencia:** `curl -i` del resultado.
3. **Evidencia:** `podman compose config` (o `docker compose config`) mostrando que `db` no publica puertos en el compose base; `podman compose ps`.

## G4 — Consistencia de entornos (H6)
1. Alinea la versión de Python del `Dockerfile` con la del entorno de desarrollo (misma versión menor). Si `python:<versión>-slim` no existe, usa en **ambos** la misma versión disponible.
2. Compara `venv/bin/pip freeze` con `requirements.txt`; deben coincidir en `fastapi`, `SQLAlchemy`, `psycopg`, `pwdlib`, `PyJWT`, `pydantic`. Corrige la discrepancia.
3. Comprueba que no hay `psycopg2` instalado en el entorno del proyecto y que la URL usa `postgresql+psycopg://`.
4. **Evidencia:** build del backend (`podman compose build backend`) y `podman compose run --rm backend python -c "import app.main; print('ok')"`.

## G5 — Seguridad de contraseñas (H8, H9)
1. Reemplaza `DUMMY_ARGON2_HASH` escrito a mano por un hash **generado al importar el módulo** con el mismo hasher: `password_hash.hash(secrets.token_urlsafe(16))`.
2. Verifica con `python -c "import pwdlib.exceptions as e; print(dir(e))"` qué excepciones lanza `pwdlib` ante un hash inválido y **acota** el `except Exception` de `verify_password` a esas (más las de `argon2` si aplican). Un error inesperado no debe convertirse silenciosamente en `False`.
3. `generate_temporary_password`: si tras los intentos ninguna candidata cumple la política, **lanza excepción** (no devuelve una inválida).
4. Tests nuevos: (a) verificar contra `DUMMY_ARGON2_HASH` con `argon2.PasswordHasher().verify(...)` lanza `VerifyMismatchError` (no `InvalidHash`); (b) con usuario inexistente, el login **sí invoca** la verificación ficticia (contador sobre `password_hash.verify`); (c) `len(CLAVES_PROHIBIDAS) == 21`; (d) mensajes y código idénticos para usuario inexistente, inactivo y clave errónea.

## G6 — Git y límites de la Fase 1 (H10)
**Evidencia:**
* `git diff --stat d9bf297 HEAD -- db/init backend/app/catalog` → vacío (si no lo está, explica cada cambio).
* `git status` limpio y `git log --oneline`.
* Al terminar todo: `git tag fase-1-cerrada`.

## G7 — Frontend (verificación mínima)
**Evidencia:** `cd frontend && npm run build` (salida final) y `npm ls --depth=0` (solo debe haberse añadido `react-router-dom` a las dependencias previstas).

## G8 — Documentación de desviaciones
Añade a `docs/SUPUESTOS.md` (continuando la numeración) una entrada por cada una, con su impacto: `pwdlib` en lugar de `argon2-cffi`; Podman/Fedora y puertos; modelos con `Column`/`declarative_base` y sin `schema=` explícito (depende de `search_path` por `connect_args`); versión de Python; extensiones a la política de claves (partes del usuario ≥ 3 caracteres, dígitos del CI ≥ 4); cualquier decisión tomada en G1–G7. Actualiza `README.md` con los comandos reales de test (desde `backend/`, `scripts/crear_bd_test.sh`).

# 4. PROHIBIDO EN ESTA FASE
Añadir endpoints, pantallas o tablas; modificar el esquema o el catálogo; cambiar tests para que pasen; omitir una evidencia; usar `except Exception`/`pass`; marcar un punto como hecho sin pegar su salida.

# 5. INFORME FINAL (formato obligatorio)

```
## Evidencias por tarea
G1 … G8 (cada una con la salida real pegada)
## Contradicciones resueltas
(H4: ¿el auth.py pegado era el real? ¿qué se corrigió?)
## No hecho / parcial
## Supuestos nuevos
## Estado final
(tests: Ran N, OK, skipped=0; tag fase-1-cerrada creado: sí/no)
```

**Regla de parada:** la Fase 2 **no se inicia** hasta que G1–G8 estén completas con evidencia y se haya revisado este informe.

=== FIN DEL PROMPT ===