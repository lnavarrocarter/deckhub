// Extrae los textos de interfaz (español) del panel web con el analizador de TypeScript.
// Uso: node out/extract.cjs <html> <salida.json>
const fs = require("fs");
const ts = require("typescript");
const src = fs.readFileSync(process.argv[2], "utf8");
const keys = new Set();
const SPANISH = /[a-záéíóúñü]{2,}/i;

function add(s) {
  s = s.replace(/\s+/g, " ").trim();
  if (!s || !SPANISH.test(s)) return;
  if (/^[\w.\-/#:{}]+$/.test(s) && !/[áéíóúñ]/.test(s) && !/^[A-ZÁÉÍÓÚÑ¿¡][a-záéíóúñ]+$/.test(s)) return; // identificadores
  if (/^(\/api|https?:|#|\.|data:)/.test(s)) return;
  if (/[;{}=]\s*$/.test(s) && /\(|\)/.test(s)) return; // código
  keys.add(s);
}
function addText(t) {
  for (const frag of t.split(/<[^>]*>/)) for (const line of frag.split("\n")) add(line);
}

// HTML (fuera de <script>/<style>): textos y atributos visibles.
const html = src.replace(/<script>[\s\S]*?<\/script>|<style>[\s\S]*?<\/style>/g, "");
for (const m of html.matchAll(/(?:placeholder|title|label|alt)="([^"]+)"/g)) add(m[1]);
addText(html.replace(/<[^>]*>/g, "\n"));

// JS
for (const [, code] of src.matchAll(/<script>([\s\S]*?)<\/script>/g)) {
  const sf = ts.createSourceFile("x.js", code, ts.ScriptTarget.Latest, true, ts.ScriptKind.JS);
  const visit = (n) => {
    if (ts.isStringLiteral(n) || ts.isNoSubstitutionTemplateLiteral(n)) {
      // Atributos o selectores no son texto de interfaz.
      const parent = n.parent;
      const isPropName = parent && ts.isPropertyAssignment(parent) && parent.name === n;
      if (!isPropName) addText(n.text);
    } else if (ts.isTemplateExpression(n)) {
      let t = n.head.text;
      for (const span of n.templateSpans) t += "{}" + span.literal.text;
      addText(t);
    }
    ts.forEachChild(n, visit);
  };
  visit(sf);
}
fs.writeFileSync(process.argv[3], JSON.stringify([...keys], null, 0));
console.log(keys.size);
