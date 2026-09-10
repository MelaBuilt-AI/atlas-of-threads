import { Miniflare } from "miniflare";
import { readFile } from "node:fs/promises";
import { sha } from "../src/publication.js";
const mf = new Miniflare({
  modules: true,
  scriptPath: "dist/worker.js",
  compatibilityDate: "2026-05-15",
  host: "127.0.0.1",
  port: 7490,
  assets: {
    directory: "dist/public",
    binding: "ASSETS",
    routerConfig: {
      has_user_worker: true,
      invoke_user_worker_ahead_of_assets: true,
    },
  },
  d1Databases: ["DB"],
  r2Buckets: ["INQUIRIES"],
  bindings: {
    SITE_ORIGIN: "http://127.0.0.1:7490",
    GITHUB_CLIENT_ID: "",
    MAX_PUBLICATIONS_PER_OWNER: "20",
  },
});
const db = await mf.getD1Database("DB");
for (const statement of (
  await readFile("migrations/0001_publications.sql", "utf8")
)
  .split(";")
  .map((x) => x.trim())
  .filter(Boolean))
  await db.prepare(statement).run();
const key = crypto.randomUUID();
await db
  .prepare("INSERT INTO owners(id,login,kind,created_at) VALUES(?,?,?,?)")
  .bind("synthetic-publisher", "Synthetic publisher", "synthetic", 1)
  .run();
await db
  .prepare("INSERT INTO instances VALUES(?,?,?,?,?,NULL)")
  .bind(
    "local-fixtures",
    "synthetic-publisher",
    "Local synthetic fixture seed",
    await sha(key),
    1,
  )
  .run();
for (let i = 1; i <= 6; i++) {
  const artifact = JSON.parse(
    await readFile(`test/fixtures/${i}.json`, "utf8"),
  );
  const r = await mf.dispatchFetch("http://127.0.0.1:7490/api/publications", {
    method: "POST",
    headers: {
      Authorization: "Bearer " + key,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ artifact, reviewed: true }),
  });
  if (!r.ok) throw Error(await r.text());
}
await db.prepare("UPDATE instances SET revoked_at=1").run();
console.log("Synthetic Atlas preview ready at http://127.0.0.1:7490/");
process.on("SIGINT", async () => {
  await mf.dispose();
  process.exit();
});
