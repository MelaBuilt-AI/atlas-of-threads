import { readFile, writeFile, mkdir, cp, readdir, rm } from "node:fs/promises";
import { build } from "esbuild";
import Ajv from "ajv/dist/2020.js";
import standalone from "ajv/dist/standalone/index.js";
const ajv = new Ajv({ code: { source: true, esm: false }, strict: false });
const root = "../src/thought_archaeology/schemas/v1/";
for (const file of await readdir(root))
  if (file.endsWith(".schema.json"))
    ajv.addSchema(JSON.parse(await readFile(root + file, "utf8")), file);
await mkdir("dist", { recursive: true });
await writeFile(
  "dist/validate.cjs",
  standalone(ajv, ajv.getSchema("portable-inquiry.schema.json")),
);
await build({
  entryPoints: ["dist/validate.cjs"],
  bundle: true,
  format: "esm",
  outfile: "dist/validate.js",
  target: "es2022",
});
await build({
  entryPoints: ["src/worker.js"],
  bundle: true,
  format: "esm",
  outfile: "dist/worker.js",
  target: "es2022",
});
// Rebuild only generated public output, so removed artwork cannot remain deployed.
await rm("dist/public", { recursive: true, force: true });
await mkdir("dist/public/player", { recursive: true });
await cp("../viz/dist", "dist/public/player", { recursive: true });
await cp("web", "dist/public", { recursive: true });
const sourceHTML = await readFile("../viz/dist/index.html", "utf8");
let world = await readFile("web/index.html", "utf8");
const audioStart = sourceHTML.indexOf('      <div id="music-controls">');
const audioEnd = sourceHTML.indexOf("</section>", audioStart);
// Reuse the existing album/effect controls, including their complete input set.
const audioMarkup = sourceHTML.slice(audioStart, audioEnd);
world = world.replace("<!-- AUDIO_CONTROLS -->", audioMarkup);
await writeFile("dist/public/index.html", world);
let shell = await readFile("../viz/dist/index.html", "utf8");
shell = shell.replace("<head>", '<head><base href="/player/" />');
shell = shell.replace(
  /  <script src="\.\/(?:portable|return-paths|agent-connect|sound|music)\.js"><\/script>\n/g,
  "",
);
shell = shell.replace(
  '<script src="./three.min.js">',
  '<link rel="stylesheet" href="/player.css" /><script src="/player.js"></script><script src="./three.min.js">',
);
shell = shell.replace(
  "Inhabit a private Personal Atlas built with the Thought Archaeology Framework.",
  "Explore a published, read-only Atlas Threadwalk.",
);
await writeFile("dist/public/player/index.html", shell);
for (const name of ["LICENSE", "THIRD_PARTY_NOTICES.md"])
  await cp("../" + name, "dist/public/" + name);
await writeFile(
  "dist/public/_headers",
  "/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: same-origin\n/player/*\n  Cache-Control: public, max-age=3600\n",
);
console.log("Worker, shared Atlas player, and world assets built.");
