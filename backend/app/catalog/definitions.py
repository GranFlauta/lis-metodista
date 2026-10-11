"""
Catálogo v1: 9 estudios + 2 perfiles, derivado de `1. FORMATO CENTRAL 2026.xlsx`.

Fuente única de verdad del catálogo. De aquí se genera el seed SQL
(`scripts/generar_seed_sql.py`) y se validan las fórmulas en los tests.

Convenciones
  * Las fórmulas usan el código del parámetro en minúsculas.
  * Los porcentajes se capturan en 0-100 (NO como fracción 0.57 como hacía el
    Excel). El absoluto es `pct / 100 * globulos_blancos`.
  * Un parámetro con `confirmar=True` puede traer valor por defecto, pero NO se
    puede publicar hasta que el bioquímico lo confirme explícitamente.
  * `validar=True` en un rango: el Excel tiene valores contradictorios entre
    hojas; se eligió el de las plantillas de perfil y requiere validación del
    bioquímico responsable antes de producción.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

NUMERICO = "NUMERICO"
TEXTO = "TEXTO_LIBRE"
SELECCION = "SELECCION"
RECUENTO = "RECUENTO_MICROSCOPICO"
CALCULADO = "CALCULADO"
FECHA = "FECHA"

NEG_POS = ["Negativo", "Positivo"]
REACTIVO = ["No reactivo", "Reactivo"]
SEMICUANT = ["Negativo", "Trazas", "+", "++", "+++", "++++"]


@dataclass(frozen=True)
class Rango:
    sexo: Optional[str] = None           # 'M' | 'F' | None (ambos)
    inferior: Optional[float] = None
    superior: Optional[float] = None
    inferior_incl: bool = True
    superior_incl: bool = True
    texto: Optional[str] = None          # lo que se imprime en el informe
    validar: bool = False


@dataclass(frozen=True)
class Param:
    codigo: str
    nombre: str
    tipo: str
    unidad: Optional[str] = None
    grupo: Optional[str] = None
    formula: Optional[str] = None
    decimales: int = 2
    obligatorio: bool = True
    opciones: Optional[list] = None
    defecto: Optional[str] = None
    confirmar: bool = False
    metodo: Optional[str] = None
    muestra: Optional[str] = None
    rangos: tuple = ()


@dataclass(frozen=True)
class Estudio:
    codigo: str
    nombre: str
    categoria: str
    parametros: tuple
    seleccion_parcial: bool = False      # True: se piden por grupo (Inmunoserología)
    reglas: tuple = ()


@dataclass(frozen=True)
class Perfil:
    codigo: str
    nombre: str
    estudios: tuple                      # ((codigo_estudio, [grupos] | None), ...)


def hasta(valor, texto=None, validar=False):
    return Rango(superior=valor, texto=texto or f"Hasta {valor}", validar=validar)


def entre(lo, hi, texto=None, sexo=None, validar=False):
    return Rango(sexo=sexo, inferior=lo, superior=hi, texto=texto or f"{lo} - {hi}", validar=validar)


def menor_a(valor, texto=None):
    return Rango(superior=valor, superior_incl=False, texto=texto or f"Menor a {valor}")


INMUNO = dict(metodo="Inmunocromatográfico", muestra="Suero")


# ---------------------------------------------------------------- HEMOGRAMA
HEMOGRAMA = Estudio(
    "HEMOGRAMA", "Hemograma Completo", "Hematología",
    parametros=(
        Param("GLOBULOS_BLANCOS", "Glóbulos Blancos", NUMERICO, "mm3", decimales=0,
              rangos=(entre(5000, 10000, "5.000 - 10.000"),)),
        Param("HEMATOCRITO", "Hematocrito", NUMERICO, "%", decimales=1,
              rangos=(entre(48, 58, "48 - 58 %", "M"), entre(44, 54, "44 - 54 %", "F"))),
        Param("GLOBULOS_ROJOS", "Glóbulos Rojos (estimado)", CALCULADO, "mm3", decimales=0,
              formula="107000 * hematocrito",
              rangos=(entre(5_400_000, 6_300_000, "5,4 - 6,3 x 10^6", "M"),
                      entre(4_900_000, 5_700_000, "4,9 - 5,7 x 10^6", "F"))),
        Param("HEMOGLOBINA", "Hemoglobina (estimada)", CALCULADO, "g/dL", decimales=1,
              formula="0.32 * hematocrito",
              rangos=(entre(16, 18, "16 - 18 g/dl", "M"), entre(14, 16, "14 - 16 g/dl", "F"))),
        Param("VES", "V.E.S.", NUMERICO, "mm/hra", decimales=0,
              rangos=(entre(2, 7, "2 - 7", "M"), entre(3, 10, "3 - 10", "F"))),
        Param("PLAQUETAS", "Plaquetas", NUMERICO, "xmm3", decimales=0,
              rangos=(entre(150000, 400000, "150.000 - 400.000"),)),
        # --- fórmula diferencial: entrada en %, salida absoluta
        Param("SEGMENTADOS_PCT", "Segmentados", NUMERICO, "%", grupo="DIFERENCIAL", decimales=0,
              rangos=(entre(55, 70),)),
        Param("LINFOCITOS_PCT", "Linfocitos", NUMERICO, "%", grupo="DIFERENCIAL", decimales=0,
              rangos=(entre(25, 40),)),
        Param("EOSINOFILOS_PCT", "Eosinófilos", NUMERICO, "%", grupo="DIFERENCIAL", decimales=0,
              rangos=(entre(0, 4),)),
        Param("MONOCITOS_PCT", "Monocitos", NUMERICO, "%", grupo="DIFERENCIAL", decimales=0,
              rangos=(entre(2, 8),)),
        Param("CAYADOS_PCT", "Cayados", NUMERICO, "%", grupo="DIFERENCIAL", decimales=0,
              obligatorio=False),
        Param("SEGMENTADOS_ABS", "Segmentados (abs.)", CALCULADO, "mm3", grupo="DIFERENCIAL", decimales=0,
              formula="segmentados_pct / 100 * globulos_blancos"),
        Param("LINFOCITOS_ABS", "Linfocitos (abs.)", CALCULADO, "mm3", grupo="DIFERENCIAL", decimales=0,
              formula="linfocitos_pct / 100 * globulos_blancos"),
        Param("EOSINOFILOS_ABS", "Eosinófilos (abs.)", CALCULADO, "mm3", grupo="DIFERENCIAL", decimales=0,
              formula="eosinofilos_pct / 100 * globulos_blancos"),
        Param("MONOCITOS_ABS", "Monocitos (abs.)", CALCULADO, "mm3", grupo="DIFERENCIAL", decimales=0,
              formula="monocitos_pct / 100 * globulos_blancos"),
        Param("CAYADOS_ABS", "Cayados (abs.)", CALCULADO, "mm3", grupo="DIFERENCIAL", decimales=0,
              obligatorio=False, formula="cayados_pct / 100 * globulos_blancos"),
    ),
    reglas=(
        {"tipo": "SUMA_IGUAL", "severidad": "ADVERTENCIA", "valor": 100, "tolerancia": 1,
         "parametros": ["SEGMENTADOS_PCT", "LINFOCITOS_PCT", "EOSINOFILOS_PCT",
                        "MONOCITOS_PCT", "CAYADOS_PCT"],
         "mensaje": "El diferencial no suma 100 %"},
    ),
)

# ------------------------------------------------------------- COAGULOGRAMA
COAGULOGRAMA = Estudio(
    "COAGULOGRAMA", "Coagulograma y Grupo Sanguíneo", "Hematología",
    parametros=(
        Param("T_COAGULACION", "T. coagulación", NUMERICO, "min", grupo="COAGULACION", decimales=1,
              rangos=(entre(5, 10, "(5-10 min.)"),)),
        Param("T_SANGRIA", "T. sangría", NUMERICO, "min", grupo="COAGULACION", decimales=1,
              rangos=(entre(2, 5, "(2-5 min.)"),)),
        Param("T_PROTROMBINA", "T. Protrombina", NUMERICO, "seg", grupo="COAGULACION", decimales=1,
              rangos=(entre(11, 13, "(11-13 seg.)"),)),
        Param("ACTIVIDAD", "Actividad", NUMERICO, "%", grupo="COAGULACION", decimales=0,
              rangos=(entre(80, 100, "(80-100 %)"),)),
        Param("INR", "INR", NUMERICO, None, grupo="COAGULACION", decimales=2),
        Param("TPTA", "TPTA", NUMERICO, "seg", grupo="COAGULACION", decimales=1,
              rangos=(entre(25, 33.8, "(25-33,8 seg.)"),)),
        Param("GRUPO_SANGUINEO", "Grupo", SELECCION, grupo="GRUPO_SANGUINEO",
              opciones=["A", "B", "AB", "O"]),
        Param("FACTOR_RH", "Factor RH", SELECCION, grupo="GRUPO_SANGUINEO",
              opciones=["Positivo (+)", "Negativo (-)"]),
    ),
)

# ---------------------------------------------------------- QUÍMICA SANGUÍNEA
QUIMICA = Estudio(
    "QUIMICA_SANGUINEA", "Química Sanguínea", "Bioquímica",
    parametros=(
        Param("GLICEMIA", "Glicemia", NUMERICO, "mg/dl", decimales=1, rangos=(entre(70, 110, "VR: 70-110"),)),
        Param("CREATININA", "Creatinina", NUMERICO, "mg/dl", decimales=2, rangos=(entre(0.7, 1.4, "VR: 0,7-1,4"),)),
        Param("UREA", "Urea", NUMERICO, "mg/dl", decimales=1, rangos=(entre(17, 42, "VR: 17-42"),)),
        Param("NUS", "NUS", NUMERICO, "mg/dl", decimales=1, rangos=(entre(7, 18, "VR: 7,0-18"),)),
        Param("ACIDO_URICO", "Ácido úrico", NUMERICO, "mg/dl", decimales=1,
              rangos=(entre(2.5, 7.0, "VR: 2,5-7,0", validar=True),)),   # VN.xlsx dice 1,5-7,0
        Param("HBA1C", "HbA1c", NUMERICO, "%", decimales=1,
              rangos=(entre(6.0, 8.3, "VR: 6,0-8,3", validar=True),)),   # no es rango de normalidad estándar
    ),
)

# --------------------------------------------------------------- ELECTROLITOS
ELECTROLITOS = Estudio(
    "ELECTROLITOS", "Electrolitos", "Bioquímica",
    parametros=(
        Param("SODIO", "Sodio", NUMERICO, "mEq/L", decimales=1, rangos=(entre(135, 155, "VR: 135-155"),)),
        Param("POTASIO", "Potasio", NUMERICO, "mEq/L", decimales=1, rangos=(entre(3.5, 5.3, "VR: 3,5-5,3"),)),
        Param("CLORO", "Cloro", NUMERICO, "mEq/L", decimales=1, rangos=(entre(98, 106, "VR: 98-106"),)),
        Param("CALCIO", "Calcio", NUMERICO, "mg/dl", decimales=1, rangos=(entre(8.5, 10.5, "VR: 8,5-10,5"),)),
        Param("MAGNESIO", "Magnesio", NUMERICO, "mg/dl", decimales=1, rangos=(entre(1.7, 2.5, "VR: 1,7-2,5"),)),
        Param("FOSFORO", "Fósforo", NUMERICO, "mg/dl", decimales=1,
              rangos=(entre(2.5, 5.0, "VR: 2,5-5,0", validar=True),)),   # HC-QMC dice 2,5-5,6
    ),
)

# -------------------------------------------------------------- PERFIL LIPÍDICO
LIPIDICO = Estudio(
    "PERFIL_LIPIDICO", "Perfil Lipídico", "Bioquímica",
    parametros=(
        Param("COLESTEROL", "Colesterol", NUMERICO, "mg/dl", decimales=1, rangos=(menor_a(200, "VR: Menor a 200"),)),
        Param("TRIGLICERIDOS", "Triglicéridos", NUMERICO, "mg/dl", decimales=1, rangos=(entre(10, 150, "VR: 10-150"),)),
        Param("HDL", "HDL-COL", NUMERICO, "mg/dl", decimales=1, rangos=(entre(33, 75, "VR: 33-75"),)),
        Param("VLDL", "VLDL-COL", CALCULADO, "mg/dl", decimales=2, formula="trigliceridos / 5",
              rangos=(entre(5, 40, "VR: 5-40"),)),
        # Friedewald: no válido con triglicéridos > 400 mg/dl
        Param("LDL", "LDL-COL", CALCULADO, "mg/dl", decimales=2,
              formula="colesterol - hdl - trigliceridos / 5 if trigliceridos <= 400 else no_calculable()",
              rangos=(entre(10, 160, "VR: 10-160"),)),
    ),
)

# ----------------------------------------------------------------- HEPATOGRAMA
HEPATOGRAMA = Estudio(
    "HEPATOGRAMA", "Hepatograma / Perfil Hepático", "Bioquímica",
    parametros=(
        Param("BILIRRUBINA_TOTAL", "Bilirrubina Total", NUMERICO, "mg/dl", decimales=2, rangos=(hasta(1.1, "VR: Hasta 1,1"),)),
        Param("BILIRRUBINA_DIRECTA", "Bilirrubina Directa", NUMERICO, "mg/dl", decimales=2, rangos=(hasta(0.3, "VR: Hasta 0,3"),)),
        Param("BILIRRUBINA_INDIRECTA", "Bilirrubina Indirecta", CALCULADO, "mg/dl", decimales=2,
              formula="bilirrubina_total - bilirrubina_directa if bilirrubina_directa <= bilirrubina_total else no_calculable()",
              rangos=(hasta(0.8, "VR: Hasta 0,8"),)),
        Param("GOT_AST", "GOT / AST", NUMERICO, "UI/L", decimales=0,
              rangos=(hasta(37, "VR: Hasta 37", validar=True),)),   # HC-QMC dice 40, VN dice 39
        Param("GPT_ALT", "GPT / ALT", NUMERICO, "UI/L", decimales=0,
              rangos=(hasta(45, "VR: Hasta 45", validar=True),)),   # HC-QMC dice 40, VN dice 39
        Param("FOSFATASA_ALCALINA", "F. Alcalina", NUMERICO, "UI/L", decimales=0,
              rangos=(entre(98, 279, "VR: 98-279", validar=True),)),  # VN dice 25-90
        # Opcional: solo aparece en la plantilla HC-QMC-SERO-PROT del Excel.
        # Si no tiene valor, NO se imprime.
        Param("GGT", "GGT", NUMERICO, "UI/L", decimales=0, obligatorio=False, rangos=(hasta(45, "VR: Hasta 45"),)),
    ),
    reglas=(
        {"tipo": "MENOR_IGUAL", "severidad": "ERROR", "parametros": ["BILIRRUBINA_DIRECTA", "BILIRRUBINA_TOTAL"],
         "mensaje": "La bilirrubina directa no puede superar a la total"},
    ),
)

# --------------------------------------------------------------- PROTEINOGRAMA
PROTEINOGRAMA = Estudio(
    "PROTEINOGRAMA", "Proteinograma", "Bioquímica",
    parametros=(
        Param("PROTEINAS_TOTALES", "Proteínas Totales", NUMERICO, "g/dl", decimales=2, rangos=(entre(6.2, 8.5, "VR: 6,2-8,5"),)),
        Param("ALBUMINA", "Albúmina", NUMERICO, "g/dl", decimales=2, rangos=(entre(3.5, 5.3, "VR: 3,5-5,3"),)),
        Param("GLOBULINA", "Globulina", CALCULADO, "g/dl", decimales=2,
              formula="proteinas_totales - albumina if albumina <= proteinas_totales else no_calculable()",
              rangos=(entre(2.0, 3.5, "VR: 2,0-3,5"),)),
        Param("RELACION_AG", "Relación A/G", CALCULADO, None, decimales=2,
              formula="albumina / (proteinas_totales - albumina) if albumina < proteinas_totales else no_calculable()",
              rangos=(entre(1.2, 2.2, "VR: 1,2-2,2"),)),
    ),
    reglas=(
        {"tipo": "MENOR_IGUAL", "severidad": "ERROR", "parametros": ["ALBUMINA", "PROTEINAS_TOTALES"],
         "mensaje": "La albúmina no puede superar a las proteínas totales"},
    ),
)

# ------------------------------------------------------------------------ EGO
EGO = Estudio(
    "EGO", "Examen General de Orina", "Uroanálisis",
    parametros=(
        # Análisis físico
        Param("CANTIDAD", "Cantidad", TEXTO, "ml", grupo="FISICO"),
        Param("COLOR", "Color", TEXTO, grupo="FISICO"),
        Param("ASPECTO", "Aspecto", TEXTO, grupo="FISICO"),
        Param("ESPUMA", "Espuma", TEXTO, grupo="FISICO"),
        Param("DENSIDAD", "Densidad", NUMERICO, grupo="FISICO", decimales=0),
        Param("PH", "pH", NUMERICO, grupo="FISICO", decimales=1),
        Param("SEDIMENTO", "Sedimento", TEXTO, grupo="FISICO"),
        # Análisis químico (los "Negativo/Normal" del Excel son valores por defecto a confirmar)
        Param("PROTEINAS", "Proteínas", SELECCION, grupo="QUIMICO", opciones=SEMICUANT, defecto="Negativo", confirmar=True),
        Param("GLUCOSA", "Glucosa", SELECCION, grupo="QUIMICO", opciones=SEMICUANT, defecto="Negativo", confirmar=True),
        Param("CETONAS", "Cetonas", SELECCION, grupo="QUIMICO", opciones=SEMICUANT, defecto="Negativo", confirmar=True),
        Param("ESTERASA_LEUCOCITARIA", "Esterasa leucocitaria", SELECCION, grupo="QUIMICO", opciones=SEMICUANT),
        Param("NITRITOS", "Nitritos", SELECCION, grupo="QUIMICO", opciones=NEG_POS, defecto="Negativo", confirmar=True),
        Param("PIGMENTOS_BILIARES", "Pigmentos biliares (bilirrubina)", SELECCION, grupo="QUIMICO",
              opciones=SEMICUANT, defecto="Negativo", confirmar=True),
        Param("UROBILINOGENO", "Urobilinógeno", SELECCION, grupo="QUIMICO",
              opciones=["Normal", "Aumentado"], defecto="Normal", confirmar=True),
        Param("SANGRE", "Sangre", SELECCION, grupo="QUIMICO", opciones=SEMICUANT, defecto="Negativo", confirmar=True),
        # Análisis microscópico
        Param("HEMATIES", "Hematíes", RECUENTO, "p/c", grupo="MICROSCOPICO"),
        Param("LEUCOCITOS", "Leucocitos", RECUENTO, "p/c", grupo="MICROSCOPICO"),
        Param("CELULAS_EPITELIALES", "C. epiteliales", RECUENTO, "p/c", grupo="MICROSCOPICO"),
        Param("CRISTALES", "Cristales", TEXTO, grupo="MICROSCOPICO", defecto="No contiene", confirmar=True),
        Param("BACTERIAS", "Bacterias", TEXTO, grupo="MICROSCOPICO", defecto="Escasa cantidad", confirmar=True),
        Param("CILINDROS", "Cilindros", TEXTO, grupo="MICROSCOPICO", defecto="No contiene", confirmar=True),
        Param("OTROS", "Otros", TEXTO, grupo="MICROSCOPICO", obligatorio=False),
    ),
)

# --------------------------------------------------------------- INMUNOSEROLOGÍA
# Un estudio, pero se piden POR GRUPO (VIH solo, PCR solo, etc.).
INMUNOSEROLOGIA = Estudio(
    "INMUNOSEROLOGIA", "Inmunoserología", "Inmunología",
    seleccion_parcial=True,
    parametros=(
        Param("VIH", "Serología para VIH", SELECCION, grupo="VIH", opciones=REACTIVO, **INMUNO),
        Param("HEPATITIS_A", "Hepatitis A (Ag. superficie)", SELECCION, grupo="HEPATITIS_A", opciones=REACTIVO, **INMUNO),
        Param("HEPATITIS_B", "Hepatitis B (Ag. superficie)", SELECCION, grupo="HEPATITIS_B", opciones=REACTIVO, **INMUNO),
        Param("HEPATITIS_C", "Hepatitis C (Ag. superficie)", SELECCION, grupo="HEPATITIS_C", opciones=REACTIVO, **INMUNO),
        Param("HCG", "Gonadotropina coriónica humana (HCG)", SELECCION, grupo="HCG", opciones=NEG_POS, **INMUNO),
        Param("HCG_FUM", "FUM", FECHA, grupo="HCG", obligatorio=False),
        Param("SARS_COV2_AG", "Antígeno SARS-CoV-2", SELECCION, grupo="SARS_COV2", opciones=NEG_POS,
              metodo="Inmunocromatográfico cualitativo de antígeno nasal", muestra="Hisopeado nasofaríngeo"),
        Param("H_PYLORI_SUERO", "Helicobacter pylori (suero)", SELECCION, grupo="H_PYLORI_SUERO", opciones=NEG_POS, **INMUNO),
        Param("H_PYLORI_HECES", "Helicobacter pylori (heces)", SELECCION, grupo="H_PYLORI_HECES",
              opciones=REACTIVO, metodo="Inmunocromatográfico", muestra="Heces"),
        Param("SANGRE_OCULTA_HECES", "Sangre oculta en heces", SELECCION, grupo="SANGRE_OCULTA",
              opciones=REACTIVO, metodo="Inmunocromatográfico", muestra="Heces"),
        # Semicuantitativas: se registra la dilución (p. ej. 1/24)
        Param("PCR_DILUCION", "Proteína C Reactiva (semicuantitativa)", TEXTO, "dilución", grupo="PCR_SEMICUANT"),
        Param("FR_DILUCION", "Factor reumatoideo", TEXTO, "dilución", grupo="FACTOR_REUMATOIDEO"),
        Param("ASTO_DILUCION", "A.S.T.O.", TEXTO, "dilución", grupo="ASTO"),
        Param("VDRL_DILUCION", "V.D.R.L.", TEXTO, "dilución", grupo="VDRL"),
        # Cuantitativa (el Excel decía "ml/L": es mg/L)
        Param("PCR_CUANTITATIVA", "Proteína C Reactiva (cuantitativa)", NUMERICO, "mg/L", grupo="PCR_TURBIDIMETRICA",
              decimales=1, metodo="Turbidimétrico (cuantitativo)", muestra="Suero",
              rangos=(menor_a(5, "VR: menor a 5"),)),
        # Reacción de Widal
        Param("WIDAL_TIFOIDEA_H", "Tifoidea H", TEXTO, "dilución", grupo="WIDAL"),
        Param("WIDAL_TIFOIDEA_O", "Tifoidea O", TEXTO, "dilución", grupo="WIDAL"),
        Param("WIDAL_PARATIFI_A", "Paratifi A", TEXTO, "dilución", grupo="WIDAL"),
        Param("WIDAL_PARATIFI_B", "Paratifi B", TEXTO, "dilución", grupo="WIDAL"),
    ),
)

ESTUDIOS = (HEMOGRAMA, COAGULOGRAMA, QUIMICA, ELECTROLITOS, LIPIDICO,
            HEPATOGRAMA, PROTEINOGRAMA, EGO, INMUNOSEROLOGIA)

# ------------------------------------------------------------------- PERFILES
PERFILES = (
    Perfil("HC-QMC-SEROL-EGO", "Perfil HC-QMC-SEROL-EGO", (
        ("HEMOGRAMA", None), ("COAGULOGRAMA", None), ("QUIMICA_SANGUINEA", None),
        ("ELECTROLITOS", None), ("HEPATOGRAMA", None), ("PERFIL_LIPIDICO", None),
        ("INMUNOSEROLOGIA", ["VIH", "PCR_SEMICUANT"]), ("EGO", None),
    )),
    Perfil("HC-QMC-SERO-PROT", "Perfil HC-QMC-SERO-PROT", (
        ("HEMOGRAMA", None), ("COAGULOGRAMA", None), ("QUIMICA_SANGUINEA", None),
        ("ELECTROLITOS", None), ("HEPATOGRAMA", None), ("PROTEINOGRAMA", None),
        ("INMUNOSEROLOGIA", ["VIH"]),
    )),
)

ESTUDIOS_POR_CODIGO = {e.codigo: e for e in ESTUDIOS}
