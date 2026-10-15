// The supplied layouts are copied verbatim except for the header brand block.
const fs = require("node:fs"),
  path = require("node:path");
const source = path.resolve(__dirname, "../docs/ui"),
  target = path.join(__dirname, "assets/screens");
fs.mkdirSync(target, { recursive: true });
const logo = fs
  .readFileSync(path.join(__dirname, "assets/logo.svg"), "utf8")
  .replace("<svg ", '<svg x="24" y="7" width="90" height="34" ');
const files = fs
  .readdirSync(source)
  .filter(
    (name) =>
      name.endsWith(".svg") &&
      !name.startsWith("00_") &&
      !name.startsWith("01_"),
  );
for (const file of files) {
  const original = fs.readFileSync(path.join(source, file), "utf8");
  const start = original.indexOf('  <path d="M30 13'),
    end = original.indexOf('  <line x1="123"', start);
  if (start < 0 || end < 0)
    throw new Error("Header brand block missing: " + file);
  const result = original.slice(0, start) + logo + "\n" + original.slice(end);
  if (result.slice(result.indexOf('  <line x1="123"')) !== original.slice(end))
    throw new Error("Unexpected layout change");
  fs.writeFileSync(path.join(target, file), result.replace(/font-family="[^"]*"/g, 'font-family="Pretendard, sans-serif"'));
}
console.log(
  `Generated ${files.length} original-layout screens; header logo and Pretendard font applied.`,
);
