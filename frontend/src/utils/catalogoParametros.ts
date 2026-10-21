/**
 * Generador de plantillas analíticas de captura para estudios del catálogo clínico (LIS).
 * Fiel a backend/app/catalog/definitions.py y formato Excel 2026.
 */
import { EstudioCaptura, SeccionCaptura, ParametroCaptura } from "../api/resultados";

function param(
  codigo: string,
  nombre: string,
  tipo_campo: "NUMERICO" | "SELECCION" | "TEXTO" | "RECUENTO" | "FECHA" | "CALCULADO",
  unidad: string | null = null,
  decimales: number | null = null,
  opciones: string[] | null = null,
  es_calculado = false,
  obligatorio = true,
  defecto: string | null = null,
  confirmar = false,
  textoRef: string | null = null
): ParametroCaptura {
  return {
    codigo,
    nombre,
    tipo_campo,
    unidad,
    decimales,
    opciones,
    obligatorio,
    requiere_confirmacion: confirmar,
    metodo: null,
    muestra: null,
    valor: null,
    es_calculado,
    calculable: !es_calculado,
    motivo_no_calculable: es_calculado ? "Faltan entradas" : null,
    confirmado: false,
    es_defecto: !!defecto,
    valor_defecto: defecto,
    referencia: textoRef ? { texto: textoRef, inferior: null, superior: null } : null,
    bandera: null,
  };
}

export function construirEstudioCapturaPlantilla(codigo: string, nombre: string): EstudioCaptura {
  const secciones: SeccionCaptura[] = [];

  switch (codigo.toUpperCase()) {
    case "HEMOGRAMA":
      secciones.push({
        grupo: null,
        parametros: [
          param("GLOBULOS_BLANCOS", "Glóbulos Blancos", "NUMERICO", "mm3", 0, null, false, true, null, false, "5.000 - 10.000"),
          param("HEMATOCRITO", "Hematocrito", "NUMERICO", "%", 1, null, false, true, null, false, "44 - 58 %"),
          param("GLOBULOS_ROJOS", "Glóbulos Rojos (estimado)", "CALCULADO", "mm3", 0, null, true, true, null, false, "4,9 - 6,3 x 10^6"),
          param("HEMOGLOBINA", "Hemoglobina (estimada)", "CALCULADO", "g/dL", 1, null, true, true, null, false, "14 - 18 g/dl"),
          param("VES", "V.E.S.", "NUMERICO", "mm/hra", 0, null, false, true, null, false, "2 - 10"),
          param("PLAQUETAS", "Plaquetas", "NUMERICO", "xmm3", 0, null, false, true, null, false, "150.000 - 400.000"),
        ],
      });
      secciones.push({
        grupo: "DIFERENCIAL",
        parametros: [
          param("SEGMENTADOS_PCT", "Segmentados", "NUMERICO", "%", 0, null, false, true, null, false, "55 - 70 %"),
          param("SEGMENTADOS_ABS", "Segmentados (abs.)", "CALCULADO", "mm3", 0, null, true),
          param("LINFOCITOS_PCT", "Linfocitos", "NUMERICO", "%", 0, null, false, true, null, false, "25 - 40 %"),
          param("LINFOCITOS_ABS", "Linfocitos (abs.)", "CALCULADO", "mm3", 0, null, true),
          param("EOSINOFILOS_PCT", "Eosinófilos", "NUMERICO", "%", 0, null, false, true, null, false, "0 - 4 %"),
          param("EOSINOFILOS_ABS", "Eosinófilos (abs.)", "CALCULADO", "mm3", 0, null, true),
          param("MONOCITOS_PCT", "Monocitos", "NUMERICO", "%", 0, null, false, true, null, false, "2 - 8 %"),
          param("MONOCITOS_ABS", "Monocitos (abs.)", "CALCULADO", "mm3", 0, null, true),
          param("CAYADOS_PCT", "Cayados", "NUMERICO", "%", 0, null, false, false, null, false, "0 - 1 %"),
          param("CAYADOS_ABS", "Cayados (abs.)", "CALCULADO", "mm3", 0, null, true, false),
        ],
      });
      break;

    case "COAGULOGRAMA":
      secciones.push({
        grupo: "COAGULACION",
        parametros: [
          param("T_COAGULACION", "T. coagulación", "NUMERICO", "min", 1, null, false, true, null, false, "(5-10 min.)"),
          param("T_SANGRIA", "T. sangría", "NUMERICO", "min", 1, null, false, true, null, false, "(2-5 min.)"),
          param("T_PROTROMBINA", "T. Protrombina", "NUMERICO", "seg", 1, null, false, true, null, false, "(11-13 seg.)"),
          param("ACTIVIDAD", "Actividad", "NUMERICO", "%", 0, null, false, true, null, false, "(80-100 %)"),
          param("INR", "INR", "NUMERICO", null, 2, null, false, true),
          param("TPTA", "TPTA", "NUMERICO", "seg", 1, null, false, true, null, false, "(25-33,8 seg.)"),
        ],
      });
      secciones.push({
        grupo: "GRUPO_SANGUINEO",
        parametros: [
          param("GRUPO_SANGUINEO", "Grupo", "SELECCION", null, null, ["A", "B", "AB", "O"]),
          param("FACTOR_RH", "Factor RH", "SELECCION", null, null, ["Positivo (+)", "Negativo (-)"]),
        ],
      });
      break;

    case "QUIMICA_SANGUINEA":
    case "QUIMICA":
      secciones.push({
        grupo: null,
        parametros: [
          param("GLICEMIA", "Glicemia", "NUMERICO", "mg/dl", 1, null, false, true, null, false, "VR: 70-110"),
          param("CREATININA", "Creatinina", "NUMERICO", "mg/dl", 2, null, false, true, null, false, "VR: 0,7-1,4"),
          param("UREA", "Urea", "NUMERICO", "mg/dl", 1, null, false, true, null, false, "VR: 17-42"),
          param("NUS", "NUS", "NUMERICO", "mg/dl", 1, null, false, true, null, false, "VR: 7,0-18"),
          param("ACIDO_URICO", "Ácido úrico", "NUMERICO", "mg/dl", 1, null, false, true, null, false, "VR: 2,5-7,0"),
          param("HBA1C", "HbA1c", "NUMERICO", "%", 1, null, false, true, null, false, "VR: 6,0-8,3"),
        ],
      });
      break;

    case "ELECTROLITOS":
      secciones.push({
        grupo: null,
        parametros: [
          param("SODIO", "Sodio", "NUMERICO", "mEq/L", 1, null, false, true, null, false, "VR: 135-155"),
          param("POTASIO", "Potasio", "NUMERICO", "mEq/L", 1, null, false, true, null, false, "VR: 3,5-5,3"),
          param("CLORO", "Cloro", "NUMERICO", "mEq/L", 1, null, false, true, null, false, "VR: 98-106"),
          param("CALCIO", "Calcio", "NUMERICO", "mg/dl", 1, null, false, true, null, false, "VR: 8,5-10,5"),
          param("MAGNESIO", "Magnesio", "NUMERICO", "mg/dl", 1, null, false, true, null, false, "VR: 1,7-2,5"),
          param("FOSFORO", "Fósforo", "NUMERICO", "mg/dl", 1, null, false, true, null, false, "VR: 2,5-5,0"),
        ],
      });
      break;

    case "PERFIL_LIPIDICO":
      secciones.push({
        grupo: null,
        parametros: [
          param("COLESTEROL", "Colesterol", "NUMERICO", "mg/dl", 1, null, false, true, null, false, "VR: Menor a 200"),
          param("TRIGLICERIDOS", "Triglicéridos", "NUMERICO", "mg/dl", 1, null, false, true, null, false, "VR: 10-150"),
          param("HDL", "HDL-COL", "NUMERICO", "mg/dl", 1, null, false, true, null, false, "VR: 33-75"),
          param("VLDL", "VLDL-COL", "CALCULADO", "mg/dl", 2, null, true, true, null, false, "VR: 5-40"),
          param("LDL", "LDL-COL", "CALCULADO", "mg/dl", 2, null, true, true, null, false, "VR: 10-160"),
        ],
      });
      break;

    case "HEPATOGRAMA":
      secciones.push({
        grupo: null,
        parametros: [
          param("BILIRRUBINA_TOTAL", "Bilirrubina Total", "NUMERICO", "mg/dl", 2, null, false, true, null, false, "VR: Hasta 1,1"),
          param("BILIRRUBINA_DIRECTA", "Bilirrubina Directa", "NUMERICO", "mg/dl", 2, null, false, true, null, false, "VR: Hasta 0,3"),
          param("BILIRRUBINA_INDIRECTA", "Bilirrubina Indirecta", "CALCULADO", "mg/dl", 2, null, true, true, null, false, "VR: Hasta 0,8"),
          param("GOT_AST", "GOT / AST", "NUMERICO", "UI/L", 0, null, false, true, null, false, "VR: Hasta 37"),
          param("GPT_ALT", "GPT / ALT", "NUMERICO", "UI/L", 0, null, false, true, null, false, "VR: Hasta 45"),
          param("FOSFATASA_ALCALINA", "F. Alcalina", "NUMERICO", "UI/L", 0, null, false, true, null, false, "VR: 98-279"),
          param("GGT", "GGT", "NUMERICO", "UI/L", 0, null, false, false, null, false, "VR: Hasta 45"),
        ],
      });
      break;

    case "PROTEINOGRAMA":
      secciones.push({
        grupo: null,
        parametros: [
          param("PROTEINAS_TOTALES", "Proteínas Totales", "NUMERICO", "g/dl", 2, null, false, true, null, false, "VR: 6,2-8,5"),
          param("ALBUMINA", "Albúmina", "NUMERICO", "g/dl", 2, null, false, true, null, false, "VR: 3,5-5,3"),
          param("GLOBULINA", "Globulina", "CALCULADO", "g/dl", 2, null, true, true, null, false, "VR: 2,0-3,5"),
          param("RELACION_AG", "Relación A/G", "CALCULADO", null, 2, null, true, true, null, false, "VR: 1,2-2,2"),
        ],
      });
      break;

    case "EGO":
      secciones.push({
        grupo: "FISICO",
        parametros: [
          param("CANTIDAD", "Cantidad", "TEXTO", "ml"),
          param("COLOR", "Color", "TEXTO"),
          param("ASPECTO", "Aspecto", "TEXTO"),
          param("ESPUMA", "Espuma", "TEXTO"),
          param("DENSIDAD", "Densidad", "NUMERICO", null, 0),
          param("PH", "pH", "NUMERICO", null, 1),
          param("SEDIMENTO", "Sedimento", "TEXTO"),
        ],
      });
      secciones.push({
        grupo: "QUIMICO",
        parametros: [
          param("PROTEINAS", "Proteínas", "SELECCION", null, null, ["Negativo", "Trazas", "+", "++", "+++", "++++"], false, true, "Negativo", true),
          param("GLUCOSA", "Glucosa", "SELECCION", null, null, ["Negativo", "Trazas", "+", "++", "+++", "++++"], false, true, "Negativo", true),
          param("CETONAS", "Cetonas", "SELECCION", null, null, ["Negativo", "Trazas", "+", "++", "+++", "++++"], false, true, "Negativo", true),
          param("ESTERASA_LEUCOCITARIA", "Esterasa leucocitaria", "SELECCION", null, null, ["Negativo", "Trazas", "+", "++", "+++", "++++"]),
          param("NITRITOS", "Nitritos", "SELECCION", null, null, ["Negativo", "Positivo"], false, true, "Negativo", true),
          param("PIGMENTOS_BILIARES", "Pigmentos biliares", "SELECCION", null, null, ["Negativo", "Trazas", "+", "++", "+++", "++++"], false, true, "Negativo", true),
          param("UROBILINOGENO", "Urobilinógeno", "SELECCION", null, null, ["Normal", "Aumentado"], false, true, "Normal", true),
          param("SANGRE", "Sangre", "SELECCION", null, null, ["Negativo", "Trazas", "+", "++", "+++", "++++"], false, true, "Negativo", true),
        ],
      });
      secciones.push({
        grupo: "MICROSCOPICO",
        parametros: [
          param("HEMATIES", "Hematíes", "RECUENTO", "p/c"),
          param("LEUCOCITOS", "Leucocitos", "RECUENTO", "p/c"),
          param("CELULAS_EPITELIALES", "Células epiteliales", "TEXTO"),
          param("BACTERIAS", "Bacterias", "TEXTO"),
          param("CRISTALES", "Cristales", "TEXTO"),
          param("CILINDROS", "Cilindros", "TEXTO"),
        ],
      });
      break;

    case "INMUNOSEROLOGIA":
      secciones.push({
        grupo: "SEROLOGIA",
        parametros: [
          param("VIH", "VIH 1/2 Ac.", "SELECCION", null, null, ["No reactivo", "Reactivo"], false, true, "No reactivo"),
          param("HBSAG", "HBsAg (Hepatitis B)", "SELECCION", null, null, ["No reactivo", "Reactivo"], false, true, "No reactivo"),
          param("VDRL", "VDRL / Sífilis", "SELECCION", null, null, ["No reactivo", "Reactivo"], false, true, "No reactivo"),
          param("CHAGAS", "Chagas HAI", "SELECCION", null, null, ["No reactivo", "Reactivo"], false, true, "No reactivo"),
          param("TOXOPLASMOSIS", "Toxoplasmosis IgG/IgM", "SELECCION", null, null, ["No reactivo", "Reactivo"], false, true, "No reactivo"),
        ],
      });
      break;

    default:
      secciones.push({
        grupo: null,
        parametros: [
          param(`${codigo}_RESULTADO`, "Resultado", "TEXTO"),
          param(`${codigo}_OBSERVACIONES`, "Observaciones", "TEXTO", null, null, null, false, false),
        ],
      });
      break;
  }

  return {
    codigo,
    nombre,
    grupos_seleccionados: null,
    secciones,
    validaciones: [],
  };
}
