import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import ts from "typescript";

const fuente = readFileSync(new URL("../src/utils/formatoNumerico.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(fuente, { compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2020 } });
const { formatearEntradaNumerica, procesarEdicionNumerica, posicionEntradaNumerica, formatearResultadoClinico } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);

test("2.2 y 2,2 conservan el decimal mientras se teclea", () => {
  for (const decimal of [".", ","]) {
    let valor = "";
    for (const caracter of `2${decimal}2`) {
      const edicion = procesarEdicionNumerica(valor, formatearEntradaNumerica(valor) + caracter);
      assert.ok(edicion);
      valor = edicion.valor;
    }
    assert.equal(valor, "2.2");
    assert.equal(formatearEntradaNumerica(valor), "2,2");
  }
});

test("la agrupación de miles y millones nunca entra en el valor canónico", () => {
  let valor = "";
  for (const caracter of "1234567890") {
    valor = procesarEdicionNumerica(valor, formatearEntradaNumerica(valor) + caracter).valor;
  }
  assert.equal(valor, "1234567890");
  assert.equal(formatearEntradaNumerica(valor), "1.234.567.890");
  valor = procesarEdicionNumerica(valor, formatearEntradaNumerica(valor) + ".").valor;
  valor = procesarEdicionNumerica(valor, formatearEntradaNumerica(valor) + "2").valor;
  assert.equal(valor, "1234567890.2");
  assert.equal(formatearEntradaNumerica(valor), "1.234.567.890,2");
});

test("conserva ceros, precisión decimal y un campo realmente vacío", () => {
  assert.equal(formatearEntradaNumerica(""), "");
  assert.equal(formatearEntradaNumerica("0"), "0");
  assert.equal(formatearEntradaNumerica("0.00"), "0,00");
  assert.equal(formatearEntradaNumerica("2."), "2,");
  assert.equal(formatearEntradaNumerica("12345678901234.123456"), "12.345.678.901.234,123456");
  assert.equal(procesarEdicionNumerica("2.2", "", ",", "deleteContentBackward").valor, "");
  assert.equal(formatearResultadoClinico("12345678901234.123456"), "12.345.678.901.234,123456");
});

test("permite editar en el centro y mantiene la posición lógica del cursor", () => {
  const edicion = procesarEdicionNumerica("1234.5", "1.2934,5");
  assert.deepEqual(edicion, { valor: "12934.5", posicion: 3 });
  assert.equal(posicionEntradaNumerica(edicion.valor, edicion.posicion), 4);
  assert.deepEqual(procesarEdicionNumerica("1234", "1234", ",", "deleteContentBackward"), { valor: "234", posicion: 0 });
});

test("editar dígitos repetidos conserva el cursor en el punto de inserción", () => {
  assert.deepEqual(procesarEdicionNumerica("111", "1111", ",", "insertText", 1), { valor: "1111", posicion: 1 });
  assert.deepEqual(procesarEdicionNumerica("1111", "12.111", ",", "insertText", 2), { valor: "12111", posicion: 2 });
  assert.deepEqual(procesarEdicionNumerica("1111", "1.11", ",", "deleteContentBackward", 3), { valor: "111", posicion: 2 });
});

test("pega números con ambos formatos de agrupación sin aritmética binaria", () => {
  for (const texto of ["1.234.567,89", "1,234,567.89", "1234567.89", "1234567,89"]) {
    assert.equal(procesarEdicionNumerica("", texto, ",", "insertFromPaste").valor, "1234567.89");
  }
  assert.equal(procesarEdicionNumerica("", "1.234.567", ",", "insertFromPaste").valor, "1234567");
  assert.equal(procesarEdicionNumerica("", "2.200", ",", "insertFromPaste").valor, "2.200");
});

test("respeta la configuración con punto decimal", () => {
  assert.equal(formatearEntradaNumerica("1234567.22", "."), "1,234,567.22");
  assert.equal(procesarEdicionNumerica("1234", "1,234,", ".").valor, "1234.");
});

test("rechaza texto inválido y conserva el signo para que el backend lo valide", () => {
  assert.equal(procesarEdicionNumerica("2.2", "2,2."), null);
  assert.equal(procesarEdicionNumerica("", "abc"), null);
  assert.equal(procesarEdicionNumerica("", "-2.2").valor, "-2.2");
});
