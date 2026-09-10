import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
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
  const sql = (await Promise.all((await readdir("migrations")).filter(f => f.endsWith(".sql")).sort().map(f => readFile("migrations/"+f,"utf8")))).join("\n");
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
    for (const s of ((await Promise.all((await readdir("migrations")).filter(f => f.endsWith(".sql")).sort().map(f => readFile("migrations/"+f,"utf8")))).join("\n"))
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

async function browser(owner = 'a') {
  const session = crypto.randomUUID();
  await db.prepare("INSERT INTO sessions VALUES(?,?,?)").bind(await sha(session), owner, Math.floor(Date.now()/1000)+600).run();
  return (path, body) => mf.dispatchFetch('http://localhost:7490'+path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: { Cookie:'atlas_session='+session, Origin:'http://localhost:7490', 'Content-Type':'application/json' },
    ...(body === undefined ? {} : {body:JSON.stringify(body)})
  });
}
async function revised(original, description) {
  const { parse } = await import('lossless-json');
  const { canonical } = await import('../src/publication.js');
  const a = structuredClone(original), bundle = parse(a.inquiry_json);
  bundle.content.description = description;
  bundle.id = await sha(canonical(bundle.content));
  a.inquiry_json = canonical(bundle);
  return a;
}

test('editions preserve geography and immutable downloads; stars and independent follows persist across devices', async () => {
  const publisher = await browser('a'), viewer = await browser('b'), secondDevice = await browser('b');
  const first = JSON.parse(await readFile('test/fixtures/3.json','utf8'));
  const published = await (await publisher('/api/publications',{artifact:first,reviewed:true})).json();
  const one = await (await req('/api/publications/'+published.id)).json();
  assert.equal(one.edition,1);
  const endpoint = `/api/threadwalks/${one.threadwalk_id}/subscription`;
  assert.equal((await viewer(endpoint,{starred:true,following:false})).status,200);
  let library = await (await secondDevice('/api/library')).json();
  assert.equal(library.publications[0].id,one.id);
  assert.equal(library.subscriptions[0].following,0);
  assert.equal((await viewer(endpoint,{starred:true,following:true})).status,200);
  assert.equal((await (await viewer('/api/library')).json()).updates.length,0);
  const nextArtifact = await revised(first,'Synthetic second edition');
  assert.equal((await publisher('/api/publications',{artifact:nextArtifact,reviewed:true})).status,409);
  const reply = await publisher('/api/publications',{artifact:nextArtifact,reviewed:true,previous_id:one.id});
  assert.equal(reply.status,201,await reply.clone().text());
  const two = await (await req('/api/publications/'+(await reply.json()).id)).json();
  assert.equal(two.edition,2); assert.equal(two.previous_id,one.id);
  assert.equal(two.threadwalk_id,one.threadwalk_id);
  assert.deepEqual([two.x,two.z,two.sequence],[one.x,one.z,one.sequence]);
  const world = await (await req('/api/world')).json();
  assert.deepEqual(world.publications.filter(p=>p.threadwalk_id===one.threadwalk_id).map(p=>p.id),[two.id]);
  assert.equal(await (await req(`/api/publications/${one.id}/bundle`)).text(),first.inquiry_json);
  library = await (await secondDevice('/api/library')).json();
  assert.equal(library.publications[0].id,two.id); assert.equal(library.updates.length,1);
  const through = library.updates[0].seq;
  const thirdArtifact = await revised(first,'Synthetic third edition');
  assert.equal((await publisher('/api/publications',{artifact:thirdArtifact,reviewed:true,previous_id:two.id})).status,201);
  assert.equal((await viewer(`/api/threadwalks/${one.threadwalk_id}/seen`,{through})).status,200);
  library = await (await secondDevice('/api/library')).json();
  assert.equal(library.updates.length,1); assert.ok(library.updates[0].seq>through);
  assert.equal((await viewer(endpoint,{starred:false,following:true})).status,200);
  library = await (await secondDevice('/api/library')).json();
  assert.equal(library.subscriptions[0].starred,0); assert.equal(library.subscriptions[0].following,1);
  const history = await (await req(`/api/threadwalks/${one.threadwalk_id}`)).json();
  assert.deepEqual(history.publications.map(p=>p.edition),[3,2,1]);
  assert.equal((await publisher(`/api/publications/${history.publications[0].id}/withdraw`,{})).status,200);
  assert.ok(!(await (await req('/api/world')).json()).publications.some(p=>p.threadwalk_id===one.threadwalk_id));
  assert.equal((await req(`/api/publications/${two.id}/bundle`)).status,200);
  assert.equal((await (await secondDevice('/api/library')).json()).publications[0].withdrawn,true);
});

test('simultaneous editions choose one successor and one update; stale predecessor leaves no object', async () => {
  const publisher = await browser('a');
  const first = JSON.parse(await readFile('test/fixtures/4.json','utf8'));
  const {id} = await (await publisher('/api/publications',{artifact:first,reviewed:true})).json();
  const before = (await bucket.list()).objects.length;
  const responses = await Promise.all(['left','right'].map(async name => {
    const artifact = await revised(first,'Synthetic concurrent '+name);
    const r = await publisher('/api/publications',{artifact,reviewed:true,previous_id:id});
    return {status:r.status,data:await r.json()};
  }));
  assert.deepEqual(responses.map(r=>r.status).sort(),[201,409]);
  const history = await (await req('/api/threadwalks/'+id)).json();
  assert.equal(history.publications.length,2);
  assert.equal((await bucket.list()).objects.length,before+1);
  assert.equal((await db.prepare('SELECT count(*) AS n FROM updates WHERE threadwalk_id=?').bind(id).first()).n,2);
});

test('pairing is browser-owned, expiring and one-use; revocation removes access across sessions and devices', async () => {
  const account = await browser('a');
  assert.equal((await req('/api/pairings',{name:'No browser'})).status,403);
  const start = await account('/api/pairings',{name:'Synthetic laptop'});
  assert.equal(start.status,201);
  const pairing = await start.json();
  assert.ok(!(await db.prepare('SELECT * FROM pairings').all()).results.some(p=>Object.values(p).includes(pairing.code)));
  const exchange = code => req('/api/pairings/exchange',{code},null,{Origin:'http://localhost:7490'});
  const attempts = await Promise.all([exchange(pairing.code),exchange(pairing.code)]);
  assert.deepEqual(attempts.map(r=>r.status).sort(),[201,403]);
  const credential = await attempts.find(r=>r.status===201).json();
  const deviceGet = path => mf.dispatchFetch('http://localhost:7490'+path,{headers:{Authorization:'Bearer '+credential.token}});
  assert.equal((await (await deviceGet('/api/me')).json()).owner.id,'a');
  assert.equal((await req('/api/instances/a/revoke',{},credential.token)).status,403);
  assert.equal((await req('/api/pairings',{name:'Nested'},credential.token)).status,403);
  const expired = await (await account('/api/pairings',{name:'Expired'})).json();
  await db.prepare('UPDATE pairings SET expires_at=1').run();
  assert.equal((await exchange(expired.code)).status,403);
  const pending = await (await account('/api/pairings',{name:'Pending'})).json();
  const otherSession = await browser('a');
  assert.equal((await account('/api/account/revoke',{})).status,200);
  assert.equal((await otherSession('/api/mine')).status,401);
  assert.equal((await deviceGet('/api/mine')).status,401);
  assert.equal((await exchange(pending.code)).status,403);
  assert.ok((await db.prepare('SELECT count(*) AS n FROM publications').first()).n>0);
  assert.ok((await db.prepare('SELECT count(*) AS n FROM subscriptions').first()).n>0);
});

test('pairing exchange racing account revocation cannot leave a live credential', async () => {
  const account = await browser('a');
  const {code} = await (await account('/api/pairings',{name:'Synthetic concurrent pairing'})).json();
  await Promise.all([
    req('/api/pairings/exchange',{code},null,{Origin:'http://localhost:7490'}),
    account('/api/account/revoke',{}),
  ]);
  assert.equal((await db.prepare('SELECT count(*) AS n FROM instances WHERE owner_id=? AND revoked_at IS NULL').bind('a').first()).n,0);
  assert.equal((await db.prepare('SELECT count(*) AS n FROM pairings WHERE owner_id=?').bind('a').first()).n,0);
});

test('migration joins existing editions while preserving the first placement and every snapshot', async () => {
  const legacy = new Miniflare({modules:true,script:'export default {fetch(){return new Response("ok")}}',compatibilityDate:'2026-05-15',d1Databases:['DB']});
  try {
    const ldb = await legacy.getD1Database('DB');
    const apply = async file => {
      for (const s of (await readFile(file,'utf8')).split(';').map(s=>s.trim()).filter(Boolean)) await ldb.prepare(s).run();
    };
    await apply('migrations/0001_publications.sql');
    await ldb.prepare("INSERT INTO owners VALUES('legacy','Synthetic legacy','synthetic',1)").run();
    for (const [id,session] of [['old','same'],['other','different'],['new','same']]) {
      await ldb.prepare(`INSERT INTO publications(id,owner_id,inquiry_id,origin_id,session_id,title,author,description,graph_count,thought_count,object_key,created_at)
        VALUES(?,'legacy',?,'synthetic-origin',?,'Synthetic title','Synthetic author','Synthetic description',1,1,?,1)`).bind(id,id,session,id).run();
    }
    await apply('migrations/0002_editions_and_connections.sql');
    assert.deepEqual((await ldb.prepare('SELECT id,seq,threadwalk_id,previous_id,object_key FROM publications ORDER BY seq').all()).results,[
      {id:'old',seq:1,threadwalk_id:'old',previous_id:null,object_key:'old'},
      {id:'other',seq:2,threadwalk_id:'other',previous_id:null,object_key:'other'},
      {id:'new',seq:3,threadwalk_id:'old',previous_id:'old',object_key:'new'},
    ]);
    assert.equal((await ldb.prepare('SELECT count(*) AS n FROM updates').first()).n,3);
  } finally { await legacy.dispose(); }
});
