import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { Miniflare } from "miniflare";
import { inspect, sha, position } from "../src/publication.js";
let mf, db, bucket;
const artifact = JSON.parse(
  await readFile(new URL("fixtures/1.json", import.meta.url), "utf8"),
);
const keyA = "synthetic-instance-a",
  keyB = "synthetic-instance-b";
const req = (path, body, key = keyA, headers = {}) =>
  mf.dispatchFetch("http://localhost:7490" + path, {
    ...(body === undefined
      ? {}
      : {
          method: "POST",
          body: JSON.stringify(body),
          headers: {
            "Content-Type": "application/json",
            ...(key ? { Authorization: "Bearer " + key } : {}),
            ...headers,
          },
        }),
  });
before(async () => {
  mf = new Miniflare({
    modules: true,
    scriptPath: "dist/worker.js",
    compatibilityDate: "2026-05-15",
    d1Databases: ["DB"],
    r2Buckets: ["INQUIRIES"],
    bindings: {
      SITE_ORIGIN: "http://localhost:7490",
      GITHUB_CLIENT_ID: "",
      MAX_PUBLICATIONS_PER_OWNER: "20",
    },
  });
  db = await mf.getD1Database("DB");
  bucket = await mf.getR2Bucket("INQUIRIES");
  const sql = await readFile("migrations/0001_publications.sql", "utf8");
  for (const s of sql
    .split(";")
    .map((x) => x.trim())
    .filter(Boolean))
    await db.prepare(s).run();
  for (const [id, key] of [
    ["a", keyA],
    ["b", keyB],
  ]) {
    await db
      .prepare("INSERT INTO owners(id,login,kind,created_at) VALUES(?,?,?,?)")
      .bind(id, "Synthetic " + id, "synthetic", 1)
      .run();
    await db
      .prepare("INSERT INTO instances VALUES(?,?,?,?,?,NULL)")
      .bind(id, id, id, await sha(key), 1)
      .run();
  }
});
after(async () => {
  await mf?.dispose();
});
test("Python canonical decimals survive browser JSON round trip", async () => {
  const parsed = await inspect(JSON.parse(JSON.stringify(artifact)));
  assert.equal(parsed.bundle.content.graphs[0].graph.nodes[0].confidence, 1);
  assert.equal(
    parsed.bundle.content.graphs[0].graph.nodes[1].confidence,
    0.00001,
  );
});
test("corrupted graph, source and private metadata rejected", async () => {
  const bad = structuredClone(artifact);
  const b = JSON.parse(bad.inquiry_json);
  b.content.graphs[0].graph.nodes[0].text = "tampered";
  bad.inquiry_json = JSON.stringify(b);
  await assert.rejects(() => inspect(bad), /checksum/);
  const badView = structuredClone(artifact);
  const p = JSON.parse(badView.player_json);
  Object.values(p.inhabit)[0].node.text = "different";
  badView.player_json = JSON.stringify(p);
  await assert.rejects(() => inspect(badView), /differs/);
});
test("anonymous, cross-origin and unreviewed writes rejected without storage", async () => {
  assert.equal(
    (
      await req("/api/publications", { artifact, reviewed: true }, null, {
        Origin: "http://localhost:7490",
      })
    ).status,
    401,
  );
  assert.equal(
    (
      await req("/api/publications", { artifact, reviewed: true }, keyA, {
        Origin: "https://elsewhere.example",
      })
    ).status,
    403,
  );
  assert.equal(
    (await req("/api/publications", { artifact, reviewed: false })).status,
    400,
  );
  assert.equal(
    (await db.prepare("SELECT count(*) AS n FROM publications").first()).n,
    0,
  );
  assert.equal((await bucket.list()).objects.length, 0);
});
test("publish, anonymous read, exact portable download, duplicate reuse and stable placement", async () => {
  const r = await req("/api/publications", { artifact, reviewed: true });
  assert.equal(r.status, 201, await r.clone().text());
  const { id } = await r.json();
  assert.equal(
    (await req("/api/publications", { artifact, reviewed: true })).status,
    200,
  );
  const world = await (await req("/api/world")).json();
  assert.equal(world.publications.length, 1);
  assert.equal(world.publications[0].sequence, 1);
  assert.equal(world.publications[0].owner.verified, false);
  assert.deepEqual(
    { x: world.publications[0].x, z: world.publications[0].z },
    position(1),
  );
  assert.equal(
    await (await req("/api/publications/" + id + "/bundle")).text(),
    artifact.inquiry_json,
  );
  assert.equal(
    await (await req("/api/publications/" + id + "/player")).text(),
    artifact.player_json,
  );
  assert.equal(
    (await db.prepare("SELECT count(*) AS n FROM publications").first()).n,
    1,
  );
});
test("ownership enforced; withdrawal removes bytes and retains a tombstone", async () => {
  const id = await sha("a:" + JSON.parse(artifact.inquiry_json).id);
  assert.equal(
    (await req(`/api/publications/${id}/withdraw`, {}, keyB)).status,
    403,
  );
  assert.equal((await req(`/api/publications/${id}/withdraw`, {})).status, 200);
  assert.equal((await req(`/api/publications/${id}/bundle`)).status, 410);
  assert.equal(
    (await req("/api/publications", { artifact, reviewed: true })).status,
    409,
  );
  assert.equal((await (await req("/api/world")).json()).publications.length, 0);
  assert.equal((await bucket.list()).objects.length, 0);
});
test("revocation rejects subsequent use of the instance token", async () => {
  assert.equal((await req("/api/instances/b/revoke", {}, keyB)).status, 200);
  assert.equal(
    (await req("/api/publications", { artifact, reviewed: true }, keyB)).status,
    401,
  );
});
test("unconfigured GitHub sign-in fails closed and bad session has no identity", async () => {
  assert.equal((await req("/auth/login")).status, 503);
  assert.deepEqual(
    await (
      await mf.dispatchFetch("http://localhost:7490/api/me", {
        headers: { Cookie: "atlas_session=forged" },
      })
    ).json(),
    { owner: null },
  );
});
test("GitHub callback verifies numeric owner, binds state to browser, and consumes it once", async () => {
  let requests = 0;
  const oauth = new Miniflare({
    modules: true,
    scriptPath: "dist/worker.js",
    compatibilityDate: "2026-05-15",
    d1Databases: ["DB"],
    r2Buckets: ["INQUIRIES"],
    bindings: {
      SITE_ORIGIN: "https://atlas.example",
      GITHUB_CLIENT_ID: "test-client",
      GITHUB_CLIENT_SECRET: "test-secret",
    },
    outboundService: async (request) => {
      requests++;
      const u = new URL(request.url);
      if (u.hostname === "github.com")
        return Response.json({ access_token: "synthetic-github-token" });
      if (u.hostname === "api.github.com")
        return Response.json({ id: 42, login: "synthetic-login" });
      return new Response("", { status: 404 });
    },
  });
  try {
    const odb = await oauth.getD1Database("DB");
    for (const s of (await readFile("migrations/0001_publications.sql", "utf8"))
      .split(";")
      .map((x) => x.trim())
      .filter(Boolean))
      await odb.prepare(s).run();
    const start = await oauth.dispatchFetch(
      "https://atlas.example/auth/login",
      { redirect: "manual" },
    );
    assert.equal(start.status, 302);
    const redirect = new URL(start.headers.get("Location")),
      state = redirect.searchParams.get("state");
    assert.equal(redirect.searchParams.get("code_challenge_method"), "S256");
    const callback =
      "https://atlas.example/auth/callback?state=" +
      state +
      "&code=synthetic-code";
    assert.equal(
      (await oauth.dispatchFetch(callback, { redirect: "manual" })).status,
      403,
    );
    assert.equal(requests, 0);
    const ok = await oauth.dispatchFetch(callback, {
      headers: { Cookie: "atlas_state=" + state },
      redirect: "manual",
    });
    assert.equal(ok.status, 302, await ok.clone().text());
    assert.match(ok.headers.get("set-cookie"), /HttpOnly/);
    assert.match(ok.headers.get("set-cookie"), /Secure/);
    assert.deepEqual(await odb.prepare("SELECT id,login FROM owners").first(), {
      id: "42",
      login: "synthetic-login",
    });
    assert.equal(
      (
        await oauth.dispatchFetch(callback, {
          headers: { Cookie: "atlas_state=" + state },
          redirect: "manual",
        })
      ).status,
      403,
    );
    assert.equal(requests, 2);
  } finally {
    await oauth.dispose();
  }
});

test("concurrent duplicate deliveries cannot replace the winning snapshot", async () => {
  const original = JSON.parse(await readFile("test/fixtures/2.json", "utf8"));
  const other = structuredClone(original),
    projection = JSON.parse(other.player_json);
  Object.values(projection.inhabit)[0].session_title =
    "Another reviewed display label";
  other.player_json = JSON.stringify(projection);
  const responses = await Promise.all(
    [original, other].map(async (artifact) => {
      const response = await req("/api/publications", {
        artifact,
        reviewed: true,
      });
      return { status: response.status, data: await response.json() };
    }),
  );
  for (const response of responses)
    assert.ok(response.status < 300, JSON.stringify(response.data));
  const { id } = responses[0].data;
  const saved = await (await req("/api/publications/" + id + "/player")).text();
  await req("/api/publications", { artifact: other, reviewed: true });
  assert.equal(
    await (await req("/api/publications/" + id + "/player")).text(),
    saved,
  );
  assert.equal((await bucket.list()).objects.length, 1);
});
