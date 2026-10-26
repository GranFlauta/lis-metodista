/**
 * Plantillas analíticas y generadores para estudios del catálogo clínico.
 * Permite instanciar formularios completos de captura cuando se añaden estudios
 * en memoria a una orden existente.
 * Alineado con definitions.py y docs/UX_GUIDE.md.
 */

import {
  EstudioCaptura,
  ParametroCaptura,
  SeccionCaptura,
  ValidacionEstudio,
} from "../../api/resultados";

const NEG_POS = ["Negativo", "Positivo"];
const REACTIVO = ["No reactivo", "Reactivo"];
const SEMICUANT = ["Negativo", "Trazas", "+", "++", "+++", "++++"];

/**
 * Genera la estructura de EstudioCaptura para cualquier estudio del catálogo
 * según su código analítico y el sexo del paciente (para rangos de referencia).
 */
export function generarEstudioCapturaPlantilla(
  codigo: string,
  nombre: string,
  sexoPaciente: string = "M"
): EstudioCaptura {
  const esM = sexoPaciente === "M";

  switch (codigo) {
    case "HEMOGRAMA":
      return {
        codigo: "HEMOGRAMA",
        nombre: nombre || "Hemograma Completo",
        grupos_seleccionados: null,
        validaciones: [],
        secciones: [
          {
            grupo: null,
            parametros: [
              {
                codigo: "GLOBULOS_BLANCOS",
                nombre: "Glóbulos Blancos",
                tipo_campo: "NUMERICO",
                unidad: "mm3",
                decimales: 0,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Sangre total EDTA",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "5.000 - 10.000", inferior: "5000", superior: "10000" },
                bandera: null,
              },
              {
                codigo: "HEMATOCRITO",
                nombre: "Hematocrito",
                tipo_campo: "NUMERICO",
                unidad: "%",
                decimales: 1,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Sangre total EDTA",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: esM
                  ? { texto: "48 - 58 %", inferior: "48", superior: "58" }
                  : { texto: "44 - 54 %", inferior: "44", superior: "54" },
                bandera: null,
              },
              {
                codigo: "GLOBULOS_ROJOS",
                nombre: "Glóbulos Rojos (estimado)",
                tipo_campo: "CALCULADO",
                unidad: "mm3",
                decimales: 0,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Sangre total EDTA",
                valor: null,
                es_calculado: true,
                calculable: false,
                motivo_no_calculable: "Requiere Hematocrito",
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: esM
                  ? { texto: "5,4 - 6,3 x 10^6", inferior: "5400000", superior: "6300000" }
                  : { texto: "4,9 - 5,7 x 10^6", inferior: "4900000", superior: "5700000" },
                bandera: null,
              },
              {
                codigo: "HEMOGLOBINA",
                nombre: "Hemoglobina (estimada)",
                tipo_campo: "CALCULADO",
                unidad: "g/dL",
                decimales: 1,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Sangre total EDTA",
                valor: null,
                es_calculado: true,
                calculable: false,
                motivo_no_calculable: "Requiere Hematocrito",
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: esM
                  ? { texto: "16 - 18 g/dl", inferior: "16", superior: "18" }
                  : { texto: "14 - 16 g/dl", inferior: "14", superior: "16" },
                bandera: null,
              },
              {
                codigo: "VES",
                nombre: "V.E.S.",
                tipo_campo: "NUMERICO",
                unidad: "mm/hra",
                decimales: 0,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Sangre citratada",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: esM
                  ? { texto: "2 - 7", inferior: "2", superior: "7" }
                  : { texto: "3 - 10", inferior: "3", superior: "10" },
                bandera: null,
              },
              {
                codigo: "PLAQUETAS",
                nombre: "Plaquetas",
                tipo_campo: "NUMERICO",
                unidad: "xmm3",
                decimales: 0,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Sangre total EDTA",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "150.000 - 400.000", inferior: "150000", superior: "400000" },
                bandera: null,
              },
            ],
          },
          {
            grupo: "DIFERENCIAL",
            parametros: [
              {
                codigo: "SEGMENTADOS_PCT",
                nombre: "Segmentados",
                tipo_campo: "NUMERICO",
                unidad: "%",
                decimales: 0,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: null,
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "55 - 70 %", inferior: "55", superior: "70" },
                bandera: null,
              },
              {
                codigo: "SEGMENTADOS_ABS",
                nombre: "Segmentados (abs.)",
                tipo_campo: "CALCULADO",
                unidad: "mm3",
                decimales: 0,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: null,
                valor: null,
                es_calculado: true,
                calculable: false,
                motivo_no_calculable: "Requiere Glóbulos Blancos y %",
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: null,
                bandera: null,
              },
              {
                codigo: "LINFOCITOS_PCT",
                nombre: "Linfocitos",
                tipo_campo: "NUMERICO",
                unidad: "%",
                decimales: 0,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: null,
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "25 - 40 %", inferior: "25", superior: "40" },
                bandera: null,
              },
              {
                codigo: "LINFOCITOS_ABS",
                nombre: "Linfocitos (abs.)",
                tipo_campo: "CALCULADO",
                unidad: "mm3",
                decimales: 0,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: null,
                valor: null,
                es_calculado: true,
                calculable: false,
                motivo_no_calculable: "Requiere Glóbulos Blancos y %",
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: null,
                bandera: null,
              },
              {
                codigo: "EOSINOFILOS_PCT",
                nombre: "Eosinófilos",
                tipo_campo: "NUMERICO",
                unidad: "%",
                decimales: 0,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: null,
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "0 - 4 %", inferior: "0", superior: "4" },
                bandera: null,
              },
              {
                codigo: "EOSINOFILOS_ABS",
                nombre: "Eosinófilos (abs.)",
                tipo_campo: "CALCULADO",
                unidad: "mm3",
                decimales: 0,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: null,
                valor: null,
                es_calculado: true,
                calculable: false,
                motivo_no_calculable: "Requiere Glóbulos Blancos y %",
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: null,
                bandera: null,
              },
              {
                codigo: "MONOCITOS_PCT",
                nombre: "Monocitos",
                tipo_campo: "NUMERICO",
                unidad: "%",
                decimales: 0,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: null,
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "2 - 8 %", inferior: "2", superior: "8" },
                bandera: null,
              },
              {
                codigo: "MONOCITOS_ABS",
                nombre: "Monocitos (abs.)",
                tipo_campo: "CALCULADO",
                unidad: "mm3",
                decimales: 0,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: null,
                valor: null,
                es_calculado: true,
                calculable: false,
                motivo_no_calculable: "Requiere Glóbulos Blancos y %",
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: null,
                bandera: null,
              },
              {
                codigo: "CAYADOS_PCT",
                nombre: "Cayados",
                tipo_campo: "NUMERICO",
                unidad: "%",
                decimales: 0,
                opciones: null,
                obligatorio: false,
                requiere_confirmacion: false,
                metodo: null,
                muestra: null,
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "0 - 1 %", inferior: "0", superior: "1" },
                bandera: null,
              },
              {
                codigo: "CAYADOS_ABS",
                nombre: "Cayados (abs.)",
                tipo_campo: "CALCULADO",
                unidad: "mm3",
                decimales: 0,
                opciones: null,
                obligatorio: false,
                requiere_confirmacion: false,
                metodo: null,
                muestra: null,
                valor: null,
                es_calculado: true,
                calculable: false,
                motivo_no_calculable: "Requiere Glóbulos Blancos y %",
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: null,
                bandera: null,
              },
            ],
          },
        ],
      };

    case "COAGULOGRAMA":
      return {
        codigo: "COAGULOGRAMA",
        nombre: nombre || "Coagulograma y Grupo Sanguíneo",
        grupos_seleccionados: null,
        validaciones: [],
        secciones: [
          {
            grupo: "COAGULACION",
            parametros: [
              {
                codigo: "T_COAGULACION",
                nombre: "T. coagulación",
                tipo_campo: "NUMERICO",
                unidad: "min",
                decimales: 1,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Sangre total",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "(5-10 min.)", inferior: "5", superior: "10" },
                bandera: null,
              },
              {
                codigo: "T_SANGRIA",
                nombre: "T. sangría",
                tipo_campo: "NUMERICO",
                unidad: "min",
                decimales: 1,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Sangre capilar",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "(2-5 min.)", inferior: "2", superior: "5" },
                bandera: null,
              },
              {
                codigo: "T_PROTROMBINA",
                nombre: "T. Protrombina",
                tipo_campo: "NUMERICO",
                unidad: "seg",
                decimales: 1,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Plasma citratado",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "(11-13 seg.)", inferior: "11", superior: "13" },
                bandera: null,
              },
              {
                codigo: "ACTIVIDAD",
                nombre: "Actividad",
                tipo_campo: "NUMERICO",
                unidad: "%",
                decimales: 0,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Plasma citratado",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "(80-100 %)", inferior: "80", superior: "100" },
                bandera: null,
              },
              {
                codigo: "INR",
                nombre: "INR",
                tipo_campo: "NUMERICO",
                unidad: null,
                decimales: 2,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Plasma citratado",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "0.8 - 1.2", inferior: "0.8", superior: "1.2" },
                bandera: null,
              },
              {
                codigo: "TPTA",
                nombre: "TPTA",
                tipo_campo: "NUMERICO",
                unidad: "seg",
                decimales: 1,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Plasma citratado",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "(25-33,8 seg.)", inferior: "25", superior: "33.8" },
                bandera: null,
              },
            ],
          },
          {
            grupo: "GRUPO_SANGUINEO",
            parametros: [
              {
                codigo: "GRUPO_SANGUINEO",
                nombre: "Grupo",
                tipo_campo: "SELECCION",
                unidad: null,
                decimales: null,
                opciones: ["A", "B", "AB", "O"],
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: "Aglutinación directa",
                muestra: "Sangre total",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: null,
                bandera: null,
              },
              {
                codigo: "FACTOR_RH",
                nombre: "Factor RH",
                tipo_campo: "SELECCION",
                unidad: null,
                decimales: null,
                opciones: ["Positivo (+)", "Negativo (-)"],
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: "Aglutinación directa",
                muestra: "Sangre total",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: null,
                bandera: null,
              },
            ],
          },
        ],
      };

    case "QUIMICA_SANGUINEA":
      return {
        codigo: "QUIMICA_SANGUINEA",
        nombre: nombre || "Química Sanguínea",
        grupos_seleccionados: null,
        validaciones: [],
        secciones: [
          {
            grupo: null,
            parametros: [
              {
                codigo: "GLICEMIA",
                nombre: "Glicemia",
                tipo_campo: "NUMERICO",
                unidad: "mg/dl",
                decimales: 1,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Suero",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "VR: 70-110", inferior: "70", superior: "110" },
                bandera: null,
              },
              {
                codigo: "CREATININA",
                nombre: "Creatinina",
                tipo_campo: "NUMERICO",
                unidad: "mg/dl",
                decimales: 2,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Suero",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "VR: 0,7-1,4", inferior: "0.7", superior: "1.4" },
                bandera: null,
              },
              {
                codigo: "UREA",
                nombre: "Urea",
                tipo_campo: "NUMERICO",
                unidad: "mg/dl",
                decimales: 1,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Suero",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "VR: 17-42", inferior: "17", superior: "42" },
                bandera: null,
              },
              {
                codigo: "NUS",
                nombre: "NUS",
                tipo_campo: "NUMERICO",
                unidad: "mg/dl",
                decimales: 1,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Suero",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "VR: 7,0-18", inferior: "7.0", superior: "18" },
                bandera: null,
              },
              {
                codigo: "ACIDO_URICO",
                nombre: "Ácido úrico",
                tipo_campo: "NUMERICO",
                unidad: "mg/dl",
                decimales: 1,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Suero",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "VR: 2,5-7,0", inferior: "2.5", superior: "7.0" },
                bandera: null,
              },
              {
                codigo: "HBA1C",
                nombre: "HbA1c",
                tipo_campo: "NUMERICO",
                unidad: "%",
                decimales: 1,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Sangre total EDTA",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "VR: 6,0-8,3", inferior: "6.0", superior: "8.3" },
                bandera: null,
              },
            ],
          },
        ],
      };

    case "ELECTROLITOS":
      return {
        codigo: "ELECTROLITOS",
        nombre: nombre || "Electrolitos",
        grupos_seleccionados: null,
        validaciones: [],
        secciones: [
          {
            grupo: null,
            parametros: [
              {
                codigo: "SODIO",
                nombre: "Sodio",
                tipo_campo: "NUMERICO",
                unidad: "mEq/L",
                decimales: 1,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Suero",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "VR: 135-155", inferior: "135", superior: "155" },
                bandera: null,
              },
              {
                codigo: "POTASIO",
                nombre: "Potasio",
                tipo_campo: "NUMERICO",
                unidad: "mEq/L",
                decimales: 1,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Suero",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "VR: 3,5-5,3", inferior: "3.5", superior: "5.3" },
                bandera: null,
              },
              {
                codigo: "CLORO",
                nombre: "Cloro",
                tipo_campo: "NUMERICO",
                unidad: "mEq/L",
                decimales: 1,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Suero",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "VR: 98-106", inferior: "98", superior: "106" },
                bandera: null,
              },
              {
                codigo: "CALCIO",
                nombre: "Calcio",
                tipo_campo: "NUMERICO",
                unidad: "mg/dl",
                decimales: 1,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Suero",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "VR: 8,5-10,5", inferior: "8.5", superior: "10.5" },
                bandera: null,
              },
              {
                codigo: "MAGNESIO",
                nombre: "Magnesio",
                tipo_campo: "NUMERICO",
                unidad: "mg/dl",
                decimales: 1,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Suero",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "VR: 1,7-2,5", inferior: "1.7", superior: "2.5" },
                bandera: null,
              },
              {
                codigo: "FOSFORO",
                nombre: "Fósforo",
                tipo_campo: "NUMERICO",
                unidad: "mg/dl",
                decimales: 1,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Suero",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "VR: 2,5-5,0", inferior: "2.5", superior: "5.0" },
                bandera: null,
              },
            ],
          },
        ],
      };

    case "PERFIL_LIPIDICO":
      return {
        codigo: "PERFIL_LIPIDICO",
        nombre: nombre || "Perfil Lipídico",
        grupos_seleccionados: null,
        validaciones: [],
        secciones: [
          {
            grupo: null,
            parametros: [
              {
                codigo: "COLESTEROL",
                nombre: "Colesterol",
                tipo_campo: "NUMERICO",
                unidad: "mg/dl",
                decimales: 1,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Suero",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "VR: Menor a 200", inferior: null, superior: "200" },
                bandera: null,
              },
              {
                codigo: "TRIGLICERIDOS",
                nombre: "Triglicéridos",
                tipo_campo: "NUMERICO",
                unidad: "mg/dl",
                decimales: 1,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Suero",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "VR: 10-150", inferior: "10", superior: "150" },
                bandera: null,
              },
              {
                codigo: "HDL",
                nombre: "HDL-COL",
                tipo_campo: "NUMERICO",
                unidad: "mg/dl",
                decimales: 1,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Suero",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "VR: 33-75", inferior: "33", superior: "75" },
                bandera: null,
              },
              {
                codigo: "VLDL",
                nombre: "VLDL-COL",
                tipo_campo: "CALCULADO",
                unidad: "mg/dl",
                decimales: 2,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Suero",
                valor: null,
                es_calculado: true,
                calculable: false,
                motivo_no_calculable: "Requiere Triglicéridos",
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "VR: 5-40", inferior: "5", superior: "40" },
                bandera: null,
              },
              {
                codigo: "LDL",
                nombre: "LDL-COL",
                tipo_campo: "CALCULADO",
                unidad: "mg/dl",
                decimales: 2,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Suero",
                valor: null,
                es_calculado: true,
                calculable: false,
                motivo_no_calculable: "Requiere Colesterol, HDL y Triglicéridos",
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "VR: 10-160", inferior: "10", superior: "160" },
                bandera: null,
              },
            ],
          },
        ],
      };

    case "HEPATOGRAMA":
      return {
        codigo: "HEPATOGRAMA",
        nombre: nombre || "Hepatograma / Perfil Hepático",
        grupos_seleccionados: null,
        validaciones: [],
        secciones: [
          {
            grupo: null,
            parametros: [
              {
                codigo: "BILIRRUBINA_TOTAL",
                nombre: "Bilirrubina Total",
                tipo_campo: "NUMERICO",
                unidad: "mg/dl",
                decimales: 2,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Suero",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "VR: Hasta 1,1", inferior: null, superior: "1.1" },
                bandera: null,
              },
              {
                codigo: "BILIRRUBINA_DIRECTA",
                nombre: "Bilirrubina Directa",
                tipo_campo: "NUMERICO",
                unidad: "mg/dl",
                decimales: 2,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Suero",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "VR: Hasta 0,3", inferior: null, superior: "0.3" },
                bandera: null,
              },
              {
                codigo: "BILIRRUBINA_INDIRECTA",
                nombre: "Bilirrubina Indirecta",
                tipo_campo: "CALCULADO",
                unidad: "mg/dl",
                decimales: 2,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Suero",
                valor: null,
                es_calculado: true,
                calculable: false,
                motivo_no_calculable: "Requiere B. Total y Directa",
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "VR: Hasta 0,8", inferior: null, superior: "0.8" },
                bandera: null,
              },
              {
                codigo: "GOT_AST",
                nombre: "GOT / AST",
                tipo_campo: "NUMERICO",
                unidad: "UI/L",
                decimales: 0,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Suero",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "VR: Hasta 37", inferior: null, superior: "37" },
                bandera: null,
              },
              {
                codigo: "GPT_ALT",
                nombre: "GPT / ALT",
                tipo_campo: "NUMERICO",
                unidad: "UI/L",
                decimales: 0,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Suero",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "VR: Hasta 45", inferior: null, superior: "45" },
                bandera: null,
              },
              {
                codigo: "FOSFATASA_ALCALINA",
                nombre: "F. Alcalina",
                tipo_campo: "NUMERICO",
                unidad: "UI/L",
                decimales: 0,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Suero",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "VR: 98-279", inferior: "98", superior: "279" },
                bandera: null,
              },
              {
                codigo: "GGT",
                nombre: "GGT",
                tipo_campo: "NUMERICO",
                unidad: "UI/L",
                decimales: 0,
                opciones: null,
                obligatorio: false,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Suero",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "VR: Hasta 45", inferior: null, superior: "45" },
                bandera: null,
              },
            ],
          },
        ],
      };

    case "PROTEINOGRAMA":
      return {
        codigo: "PROTEINOGRAMA",
        nombre: nombre || "Proteinograma",
        grupos_seleccionados: null,
        validaciones: [],
        secciones: [
          {
            grupo: null,
            parametros: [
              {
                codigo: "PROTEINAS_TOTALES",
                nombre: "Proteínas Totales",
                tipo_campo: "NUMERICO",
                unidad: "g/dl",
                decimales: 2,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Suero",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "VR: 6,2-8,5", inferior: "6.2", superior: "8.5" },
                bandera: null,
              },
              {
                codigo: "ALBUMINA",
                nombre: "Albúmina",
                tipo_campo: "NUMERICO",
                unidad: "g/dl",
                decimales: 2,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Suero",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "VR: 3,5-5,3", inferior: "3.5", superior: "5.3" },
                bandera: null,
              },
              {
                codigo: "GLOBULINA",
                nombre: "Globulina",
                tipo_campo: "CALCULADO",
                unidad: "g/dl",
                decimales: 2,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Suero",
                valor: null,
                es_calculado: true,
                calculable: false,
                motivo_no_calculable: "Requiere P. Totales y Albúmina",
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "VR: 2,0-3,5", inferior: "2.0", superior: "3.5" },
                bandera: null,
              },
              {
                codigo: "RELACION_AG",
                nombre: "Relación A/G",
                tipo_campo: "CALCULADO",
                unidad: null,
                decimales: 2,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Suero",
                valor: null,
                es_calculado: true,
                calculable: false,
                motivo_no_calculable: "Requiere Albúmina y Globulina",
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "VR: 1,2-2,2", inferior: "1.2", superior: "2.2" },
                bandera: null,
              },
            ],
          },
        ],
      };

    case "EGO":
      return {
        codigo: "EGO",
        nombre: nombre || "Examen General de Orina",
        grupos_seleccionados: null,
        validaciones: [],
        secciones: [
          {
            grupo: "FISICO",
            parametros: [
              {
                codigo: "CANTIDAD",
                nombre: "Cantidad",
                tipo_campo: "TEXTO",
                unidad: "ml",
                decimales: null,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Orina",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: null,
                bandera: null,
              },
              {
                codigo: "COLOR",
                nombre: "Color",
                tipo_campo: "TEXTO",
                unidad: null,
                decimales: null,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Orina",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: null,
                bandera: null,
              },
              {
                codigo: "ASPECTO",
                nombre: "Aspecto",
                tipo_campo: "TEXTO",
                unidad: null,
                decimales: null,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Orina",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: null,
                bandera: null,
              },
              {
                codigo: "ESPUMA",
                nombre: "Espuma",
                tipo_campo: "TEXTO",
                unidad: null,
                decimales: null,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Orina",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: null,
                bandera: null,
              },
              {
                codigo: "DENSIDAD",
                nombre: "Densidad",
                tipo_campo: "NUMERICO",
                unidad: null,
                decimales: 0,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Orina",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "1015 - 1025", inferior: "1015", superior: "1025" },
                bandera: null,
              },
              {
                codigo: "PH",
                nombre: "pH",
                tipo_campo: "NUMERICO",
                unidad: null,
                decimales: 1,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Orina",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "5,0 - 7,0", inferior: "5.0", superior: "7.0" },
                bandera: null,
              },
              {
                codigo: "SEDIMENTO",
                nombre: "Sedimento",
                tipo_campo: "TEXTO",
                unidad: null,
                decimales: null,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Orina",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: null,
                bandera: null,
              },
            ],
          },
          {
            grupo: "QUIMICO",
            parametros: [
              {
                codigo: "PROTEINAS",
                nombre: "Proteínas",
                tipo_campo: "SELECCION",
                unidad: null,
                decimales: null,
                opciones: SEMICUANT,
                obligatorio: true,
                requiere_confirmacion: true,
                metodo: "Tira reactiva",
                muestra: "Orina",
                valor: "Negativo",
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: false,
                es_defecto: true,
                valor_defecto: "Negativo",
                referencia: { texto: "Negativo", inferior: null, superior: null },
                bandera: null,
              },
              {
                codigo: "GLUCOSA",
                nombre: "Glucosa",
                tipo_campo: "SELECCION",
                unidad: null,
                decimales: null,
                opciones: SEMICUANT,
                obligatorio: true,
                requiere_confirmacion: true,
                metodo: "Tira reactiva",
                muestra: "Orina",
                valor: "Negativo",
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: false,
                es_defecto: true,
                valor_defecto: "Negativo",
                referencia: { texto: "Negativo", inferior: null, superior: null },
                bandera: null,
              },
              {
                codigo: "CETONAS",
                nombre: "Cetonas",
                tipo_campo: "SELECCION",
                unidad: null,
                decimales: null,
                opciones: SEMICUANT,
                obligatorio: true,
                requiere_confirmacion: true,
                metodo: "Tira reactiva",
                muestra: "Orina",
                valor: "Negativo",
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: false,
                es_defecto: true,
                valor_defecto: "Negativo",
                referencia: { texto: "Negativo", inferior: null, superior: null },
                bandera: null,
              },
              {
                codigo: "ESTERASA_LEUCOCITARIA",
                nombre: "Esterasa leucocitaria",
                tipo_campo: "SELECCION",
                unidad: null,
                decimales: null,
                opciones: SEMICUANT,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: "Tira reactiva",
                muestra: "Orina",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "Negativo", inferior: null, superior: null },
                bandera: null,
              },
              {
                codigo: "NITRITOS",
                nombre: "Nitritos",
                tipo_campo: "SELECCION",
                unidad: null,
                decimales: null,
                opciones: NEG_POS,
                obligatorio: true,
                requiere_confirmacion: true,
                metodo: "Tira reactiva",
                muestra: "Orina",
                valor: "Negativo",
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: false,
                es_defecto: true,
                valor_defecto: "Negativo",
                referencia: { texto: "Negativo", inferior: null, superior: null },
                bandera: null,
              },
              {
                codigo: "PIGMENTOS_BILIARES",
                nombre: "Pigmentos biliares (bilirrubina)",
                tipo_campo: "SELECCION",
                unidad: null,
                decimales: null,
                opciones: SEMICUANT,
                obligatorio: true,
                requiere_confirmacion: true,
                metodo: "Tira reactiva",
                muestra: "Orina",
                valor: "Negativo",
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: false,
                es_defecto: true,
                valor_defecto: "Negativo",
                referencia: { texto: "Negativo", inferior: null, superior: null },
                bandera: null,
              },
              {
                codigo: "UROBILINOGENO",
                nombre: "Urobilinógeno",
                tipo_campo: "SELECCION",
                unidad: null,
                decimales: null,
                opciones: ["Normal", "Aumentado"],
                obligatorio: true,
                requiere_confirmacion: true,
                metodo: "Tira reactiva",
                muestra: "Orina",
                valor: "Normal",
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: false,
                es_defecto: true,
                valor_defecto: "Normal",
                referencia: { texto: "Normal", inferior: null, superior: null },
                bandera: null,
              },
              {
                codigo: "SANGRE",
                nombre: "Sangre",
                tipo_campo: "SELECCION",
                unidad: null,
                decimales: null,
                opciones: SEMICUANT,
                obligatorio: true,
                requiere_confirmacion: true,
                metodo: "Tira reactiva",
                muestra: "Orina",
                valor: "Negativo",
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: false,
                es_defecto: true,
                valor_defecto: "Negativo",
                referencia: { texto: "Negativo", inferior: null, superior: null },
                bandera: null,
              },
            ],
          },
          {
            grupo: "MICROSCOPICO",
            parametros: [
              {
                codigo: "HEMATIES",
                nombre: "Hematíes",
                tipo_campo: "RECUENTO",
                unidad: "p/c",
                decimales: null,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: "Microscopía",
                muestra: "Orina",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "0 - 2 p/c", inferior: "0", superior: "2" },
                bandera: null,
              },
              {
                codigo: "LEUCOCITOS",
                nombre: "Leucocitos",
                tipo_campo: "RECUENTO",
                unidad: "p/c",
                decimales: null,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: "Microscopía",
                muestra: "Orina",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "0 - 4 p/c", inferior: "0", superior: "4" },
                bandera: null,
              },
              {
                codigo: "CELULAS_EPITELIALES",
                nombre: "C. epiteliales",
                tipo_campo: "RECUENTO",
                unidad: "p/c",
                decimales: null,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: "Microscopía",
                muestra: "Orina",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "Escasas", inferior: null, superior: null },
                bandera: null,
              },
              {
                codigo: "CRISTALES",
                nombre: "Cristales",
                tipo_campo: "TEXTO",
                unidad: null,
                decimales: null,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: true,
                metodo: "Microscopía",
                muestra: "Orina",
                valor: "No contiene",
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: false,
                es_defecto: true,
                valor_defecto: "No contiene",
                referencia: { texto: "No contiene", inferior: null, superior: null },
                bandera: null,
              },
              {
                codigo: "BACTERIAS",
                nombre: "Bacterias",
                tipo_campo: "TEXTO",
                unidad: null,
                decimales: null,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: true,
                metodo: "Microscopía",
                muestra: "Orina",
                valor: "Escasa cantidad",
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: false,
                es_defecto: true,
                valor_defecto: "Escasa cantidad",
                referencia: { texto: "Escasa cantidad", inferior: null, superior: null },
                bandera: null,
              },
              {
                codigo: "CILINDROS",
                nombre: "Cilindros",
                tipo_campo: "TEXTO",
                unidad: null,
                decimales: null,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: true,
                metodo: "Microscopía",
                muestra: "Orina",
                valor: "No contiene",
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: false,
                es_defecto: true,
                valor_defecto: "No contiene",
                referencia: { texto: "No contiene", inferior: null, superior: null },
                bandera: null,
              },
              {
                codigo: "OTROS",
                nombre: "Otros",
                tipo_campo: "TEXTO",
                unidad: null,
                decimales: null,
                opciones: null,
                obligatorio: false,
                requiere_confirmacion: false,
                metodo: "Microscopía",
                muestra: "Orina",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: null,
                bandera: null,
              },
            ],
          },
        ],
      };

    case "INMUNOSEROLOGIA":
      return {
        codigo: "INMUNOSEROLOGIA",
        nombre: nombre || "Inmunoserología",
        grupos_seleccionados: null,
        validaciones: [],
        secciones: [
          {
            grupo: "VIH",
            parametros: [
              {
                codigo: "VIH",
                nombre: "Serología para VIH",
                tipo_campo: "SELECCION",
                unidad: null,
                decimales: null,
                opciones: REACTIVO,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: "Inmunocromatográfico",
                muestra: "Suero",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "No reactivo", inferior: null, superior: null },
                bandera: null,
              },
            ],
          },
          {
            grupo: "HEPATITIS_B",
            parametros: [
              {
                codigo: "HEPATITIS_B",
                nombre: "Hepatitis B (Ag. superficie)",
                tipo_campo: "SELECCION",
                unidad: null,
                decimales: null,
                opciones: REACTIVO,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: "Inmunocromatográfico",
                muestra: "Suero",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "No reactivo", inferior: null, superior: null },
                bandera: null,
              },
            ],
          },
          {
            grupo: "PCR_SEMICUANT",
            parametros: [
              {
                codigo: "PCR_DILUCION",
                nombre: "Proteína C Reactiva (semicuantitativa)",
                tipo_campo: "TEXTO",
                unidad: "dilución",
                decimales: null,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: "Aglutinación látex",
                muestra: "Suero",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "Negativo / Menor a 6 mg/L", inferior: null, superior: null },
                bandera: null,
              },
            ],
          },
          {
            grupo: "FACTOR_REUMATOIDEO",
            parametros: [
              {
                codigo: "FR_DILUCION",
                nombre: "Factor reumatoideo",
                tipo_campo: "TEXTO",
                unidad: "dilución",
                decimales: null,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: "Aglutinación látex",
                muestra: "Suero",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "Menor a 8 UI/ml", inferior: null, superior: null },
                bandera: null,
              },
            ],
          },
          {
            grupo: "VDRL",
            parametros: [
              {
                codigo: "VDRL_DILUCION",
                nombre: "V.D.R.L.",
                tipo_campo: "TEXTO",
                unidad: "dilución",
                decimales: null,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: "Floculación",
                muestra: "Suero",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: { texto: "No reactivo", inferior: null, superior: null },
                bandera: null,
              },
            ],
          },
        ],
      };

    default:
      // Plantilla genérica para cualquier estudio adicional del catálogo
      return {
        codigo,
        nombre: nombre || codigo,
        grupos_seleccionados: null,
        validaciones: [],
        secciones: [
          {
            grupo: null,
            parametros: [
              {
                codigo: `${codigo}_RESULTADO`,
                nombre: "Resultado General",
                tipo_campo: "TEXTO",
                unidad: null,
                decimales: null,
                opciones: null,
                obligatorio: true,
                requiere_confirmacion: false,
                metodo: null,
                muestra: "Muestra clínica",
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: null,
                bandera: null,
              },
              {
                codigo: `${codigo}_OBS`,
                nombre: "Observaciones",
                tipo_campo: "TEXTO",
                unidad: null,
                decimales: null,
                opciones: null,
                obligatorio: false,
                requiere_confirmacion: false,
                metodo: null,
                muestra: null,
                valor: null,
                es_calculado: false,
                calculable: true,
                motivo_no_calculable: null,
                confirmado: true,
                es_defecto: false,
                valor_defecto: null,
                referencia: null,
                bandera: null,
              },
            ],
          },
        ],
      };
  }
}

/**
 * Evalúa banderas (ALTO, BAJO, NORMAL) para un valor numérico y rango de referencia.
 */
export function evaluarBanderaLocal(
  valorStr: string | null | undefined,
  ref: { inferior: string | null; superior: string | null } | null | undefined
): "BAJO" | "NORMAL" | "ALTO" | null {
  if (!valorStr || !ref) return null;
  const num = parseFloat(valorStr.replace(",", "."));
  if (isNaN(num)) return null;

  const inf = ref.inferior !== null ? parseFloat(ref.inferior) : null;
  const sup = ref.superior !== null ? parseFloat(ref.superior) : null;

  if (inf !== null && num < inf) return "BAJO";
  if (sup !== null && num > sup) return "ALTO";
  if (inf !== null || sup !== null) return "NORMAL";
  return null;
}

/**
 * Ejecuta cálculos locales para fórmulas clínicas analíticas instantáneas
 * actualizando valores calculados y banderas en tiempo real.
 */
export function calcularEstudioLocalmente(
  estudio: EstudioCaptura,
  valores: Record<string, string>
): EstudioCaptura {
  const nuevoEstudio: EstudioCaptura = JSON.parse(JSON.stringify(estudio));
  const validaciones: ValidacionEstudio[] = [];

  // 1. HEMOGRAMA
  if (estudio.codigo === "HEMOGRAMA") {
    const gb = parseFloat(valores["GLOBULOS_BLANCOS"]?.replace(",", ".") || "");
    const hto = parseFloat(valores["HEMATOCRITO"]?.replace(",", ".") || "");

    nuevoEstudio.secciones.forEach((sec) => {
      sec.parametros.forEach((p) => {
        if (p.codigo === "GLOBULOS_ROJOS") {
          if (!isNaN(hto)) {
            const gr = Math.round(107000 * hto);
            p.valor = String(gr);
            p.calculable = true;
            p.motivo_no_calculable = null;
            p.bandera = evaluarBanderaLocal(p.valor, p.referencia);
          } else {
            p.valor = null;
            p.calculable = false;
            p.motivo_no_calculable = "Requiere Hematocrito";
            p.bandera = null;
          }
        } else if (p.codigo === "HEMOGLOBINA") {
          if (!isNaN(hto)) {
            const hb = (0.32 * hto).toFixed(1);
            p.valor = hb;
            p.calculable = true;
            p.motivo_no_calculable = null;
            p.bandera = evaluarBanderaLocal(p.valor, p.referencia);
          } else {
            p.valor = null;
            p.calculable = false;
            p.motivo_no_calculable = "Requiere Hematocrito";
            p.bandera = null;
          }
        } else if (p.codigo.endsWith("_ABS")) {
          const prefix = p.codigo.replace(/_ABS$/, "");
          const pctVal = parseFloat(valores[`${prefix}_PCT`]?.replace(",", ".") || "");
          if (!isNaN(gb) && !isNaN(pctVal)) {
            const abs = Math.round((pctVal / 100) * gb);
            p.valor = String(abs);
            p.calculable = true;
            p.motivo_no_calculable = null;
          } else {
            p.valor = null;
            p.calculable = false;
            p.motivo_no_calculable = "Requiere GB y %";
          }
        } else if (!p.es_calculado) {
          const v = valores[p.codigo];
          if (v !== undefined && v.trim() !== "") {
            p.bandera = evaluarBanderaLocal(v, p.referencia);
          }
        }
      });
    });

    // Validación sumatoria diferencial
    const seg = parseFloat(valores["SEGMENTADOS_PCT"]?.replace(",", ".") || "0") || 0;
    const lin = parseFloat(valores["LINFOCITOS_PCT"]?.replace(",", ".") || "0") || 0;
    const eos = parseFloat(valores["EOSINOFILOS_PCT"]?.replace(",", ".") || "0") || 0;
    const mon = parseFloat(valores["MONOCITOS_PCT"]?.replace(",", ".") || "0") || 0;
    const cay = parseFloat(valores["CAYADOS_PCT"]?.replace(",", ".") || "0") || 0;
    const suma = seg + lin + eos + mon + cay;
    if (suma > 0 && Math.abs(suma - 100) > 1) {
      validaciones.push({
        severidad: "ADVERTENCIA",
        mensaje: `El diferencial no suma 100 % (suma actual: ${suma} %)`,
        parametros: ["SEGMENTADOS_PCT", "LINFOCITOS_PCT", "EOSINOFILOS_PCT", "MONOCITOS_PCT", "CAYADOS_PCT"],
      });
    }
  }

  // 2. PERFIL LIPIDICO
  else if (estudio.codigo === "PERFIL_LIPIDICO") {
    const col = parseFloat(valores["COLESTEROL"]?.replace(",", ".") || "");
    const tg = parseFloat(valores["TRIGLICERIDOS"]?.replace(",", ".") || "");
    const hdl = parseFloat(valores["HDL"]?.replace(",", ".") || "");

    nuevoEstudio.secciones.forEach((sec) => {
      sec.parametros.forEach((p) => {
        if (p.codigo === "VLDL") {
          if (!isNaN(tg)) {
            p.valor = (tg / 5).toFixed(2);
            p.calculable = true;
            p.motivo_no_calculable = null;
            p.bandera = evaluarBanderaLocal(p.valor, p.referencia);
          } else {
            p.valor = null;
            p.calculable = false;
            p.motivo_no_calculable = "Requiere Triglicéridos";
          }
        } else if (p.codigo === "LDL") {
          if (!isNaN(col) && !isNaN(hdl) && !isNaN(tg)) {
            if (tg > 400) {
              p.valor = null;
              p.calculable = false;
              p.motivo_no_calculable = "No calculable con Triglicéridos > 400 mg/dl";
            } else {
              const ldl = col - hdl - tg / 5;
              p.valor = ldl.toFixed(2);
              p.calculable = true;
              p.motivo_no_calculable = null;
              p.bandera = evaluarBanderaLocal(p.valor, p.referencia);
            }
          } else {
            p.valor = null;
            p.calculable = false;
            p.motivo_no_calculable = "Requiere Colesterol, HDL y Triglicéridos";
          }
        } else if (!p.es_calculado) {
          const v = valores[p.codigo];
          if (v !== undefined && v.trim() !== "") {
            p.bandera = evaluarBanderaLocal(v, p.referencia);
          }
        }
      });
    });
  }

  // 3. HEPATOGRAMA
  else if (estudio.codigo === "HEPATOGRAMA") {
    const bt = parseFloat(valores["BILIRRUBINA_TOTAL"]?.replace(",", ".") || "");
    const bd = parseFloat(valores["BILIRRUBINA_DIRECTA"]?.replace(",", ".") || "");

    nuevoEstudio.secciones.forEach((sec) => {
      sec.parametros.forEach((p) => {
        if (p.codigo === "BILIRRUBINA_INDIRECTA") {
          if (!isNaN(bt) && !isNaN(bd)) {
            if (bd <= bt) {
              p.valor = (bt - bd).toFixed(2);
              p.calculable = true;
              p.motivo_no_calculable = null;
              p.bandera = evaluarBanderaLocal(p.valor, p.referencia);
            } else {
              p.valor = null;
              p.calculable = false;
              p.motivo_no_calculable = "Directa supera a Total";
            }
          } else {
            p.valor = null;
            p.calculable = false;
            p.motivo_no_calculable = "Requiere B. Total y Directa";
          }
        } else if (!p.es_calculado) {
          const v = valores[p.codigo];
          if (v !== undefined && v.trim() !== "") {
            p.bandera = evaluarBanderaLocal(v, p.referencia);
          }
        }
      });
    });

    if (!isNaN(bt) && !isNaN(bd) && bd > bt) {
      validaciones.push({
        severidad: "ERROR",
        mensaje: "La bilirrubina directa no puede superar a la total",
        parametros: ["BILIRRUBINA_DIRECTA", "BILIRRUBINA_TOTAL"],
      });
    }
  }

  // 4. PROTEINOGRAMA
  else if (estudio.codigo === "PROTEINOGRAMA") {
    const pt = parseFloat(valores["PROTEINAS_TOTALES"]?.replace(",", ".") || "");
    const alb = parseFloat(valores["ALBUMINA"]?.replace(",", ".") || "");

    nuevoEstudio.secciones.forEach((sec) => {
      sec.parametros.forEach((p) => {
        if (p.codigo === "GLOBULINA") {
          if (!isNaN(pt) && !isNaN(alb)) {
            if (alb <= pt) {
              p.valor = (pt - alb).toFixed(2);
              p.calculable = true;
              p.motivo_no_calculable = null;
              p.bandera = evaluarBanderaLocal(p.valor, p.referencia);
            } else {
              p.valor = null;
              p.calculable = false;
              p.motivo_no_calculable = "Albúmina supera a P. Totales";
            }
          } else {
            p.valor = null;
            p.calculable = false;
            p.motivo_no_calculable = "Requiere P. Totales y Albúmina";
          }
        } else if (p.codigo === "RELACION_AG") {
          if (!isNaN(pt) && !isNaN(alb)) {
            const glob = pt - alb;
            if (glob > 0) {
              p.valor = (alb / glob).toFixed(2);
              p.calculable = true;
              p.motivo_no_calculable = null;
              p.bandera = evaluarBanderaLocal(p.valor, p.referencia);
            } else {
              p.valor = null;
              p.calculable = false;
              p.motivo_no_calculable = "Globulina menor o igual a 0";
            }
          } else {
            p.valor = null;
            p.calculable = false;
            p.motivo_no_calculable = "Requiere Albúmina y Globulina";
          }
        } else if (!p.es_calculado) {
          const v = valores[p.codigo];
          if (v !== undefined && v.trim() !== "") {
            p.bandera = evaluarBanderaLocal(v, p.referencia);
          }
        }
      });
    });

    if (!isNaN(pt) && !isNaN(alb) && alb > pt) {
      validaciones.push({
        severidad: "ERROR",
        mensaje: "La albúmina no puede superar a las proteínas totales",
        parametros: ["ALBUMINA", "PROTEINAS_TOTALES"],
      });
    }
  }

  // 5. Otros estudios
  else {
    nuevoEstudio.secciones.forEach((sec) => {
      sec.parametros.forEach((p) => {
        if (!p.es_calculado) {
          const v = valores[p.codigo];
          if (v !== undefined && v.trim() !== "") {
            p.bandera = evaluarBanderaLocal(v, p.referencia);
          }
        }
      });
    });
  }

  nuevoEstudio.validaciones = validaciones;
  return nuevoEstudio;
}
