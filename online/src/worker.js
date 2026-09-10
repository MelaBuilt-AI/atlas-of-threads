import {expeditions,expeditionVisible,expeditionBindings} from './expeditions.js';
import { capsuleGet, capsulePost } from "./capsules.js";
import { inspect, sha, fail, MAX_BYTES, position } from "./publication.js";
const now = () => Math.floor(Date.now() / 1000);
const token = () => crypto.randomUUID() + crypto.randomUUID();
const json = (value, status = 200) =>
  Response.json(value, {
    status,
    headers: {
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
const cookie = (r, name) =>
  r.headers
    .get("Cookie")
    ?.split(";")
    .map((x) => x.trim())
    .find((x) => x.startsWith(name + "="))
    ?.slice(name.length + 1);
const cookieHeader = (env, name, value, age) =>
  `${name}=${value}; HttpOnly; SameSite=Lax; Path=/; Max-Age=${age}${env.SITE_ORIGIN.startsWith("https:") ? "; Secure" : ""}`;
async function body(request) {
  if (request.headers.get("Content-Type")?.split(";")[0] !== "application/json")
    fail("Use application/json", 415);
  if (Number(request.headers.get("Content-Length")) > MAX_BYTES)
    fail("Publication exceeds 8 MiB", 413);
  const reader = request.body?.getReader();
  let chunks = [],
    length = 0;
  if (!reader) fail("Missing request body");
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    length += value.length;
    if (length > MAX_BYTES) {
      await reader.cancel();
      fail("Publication exceeds 8 MiB", 413);
    }
    chunks.push(value);
  }
  const bytes = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.length;
  }
  try {
    return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
  } catch {
    fail("Invalid JSON");
  }
}
async function identity(r, env, required = true) {
  const bearer = r.headers.get("Authorization");
  let who;
  if (bearer?.startsWith("Bearer "))
    who = await env.DB.prepare(
      "SELECT o.id,o.login,i.id AS instance_id FROM instances i JOIN owners o ON o.id=i.owner_id WHERE i.token_hash=? AND i.revoked_at IS NULL",
    )
      .bind(await sha(bearer.slice(7)))
      .first();
  else if (cookie(r, "atlas_session"))
    who = await env.DB.prepare(
      "SELECT o.id,o.login FROM sessions s JOIN owners o ON o.id=s.owner_id WHERE s.hash=? AND s.expires_at>?",
    )
      .bind(await sha(cookie(r, "atlas_session")), now())
      .first();
  if (required && !who) fail("Sign in with GitHub to contribute", 401);
  return who;
}
function sameOrigin(r, env) {
  const origin = r.headers.get("Origin");
  if (origin && origin !== env.SITE_ORIGIN) fail("Use this Atlas window", 403);
  if (!r.headers.get("Authorization") && !origin)
    fail("Same-origin browser request required", 403);
}
async function auth(r, env, url) {
  if (!env.GITHUB_CLIENT_ID || !env.GITHUB_CLIENT_SECRET)
    fail("GitHub connection is not configured for this preview yet", 503);
  if (url.pathname === "/auth/login") {
    const state = token(),
      verifier = token();
    await env.DB.batch([
      env.DB.prepare("DELETE FROM auth_states WHERE expires_at<?").bind(now()),
      env.DB.prepare("INSERT INTO auth_states VALUES(?,?,?)").bind(
        await sha(state),
        verifier,
        now() + 600,
      ),
    ]);
    const challenge = btoa(
      String.fromCharCode(
        ...new Uint8Array(
          await crypto.subtle.digest(
            "SHA-256",
            new TextEncoder().encode(verifier),
          ),
        ),
      ),
    )
      .replaceAll("+", "-")
      .replaceAll("/", "_")
      .replaceAll("=", "");
    const target = new URL("https://github.com/login/oauth/authorize");
    target.search = new URLSearchParams({
      client_id: env.GITHUB_CLIENT_ID,
      redirect_uri: env.SITE_ORIGIN + "/auth/callback",
      state,
      code_challenge: challenge,
      code_challenge_method: "S256",
    });
    return new Response(null, {
      status: 302,
      headers: {
        Location: target.href,
        "Set-Cookie": cookieHeader(env, "atlas_state", state, 600),
        "Cache-Control": "no-store",
      },
    });
  }
  const state = url.searchParams.get("state");
  if (!state || state !== cookie(r, "atlas_state"))
    fail("Sign-in expired; start again", 403);
  const stored = await env.DB.prepare(
    "DELETE FROM auth_states WHERE hash=? AND expires_at>? RETURNING verifier",
  )
    .bind(await sha(state), now())
    .first();
  if (!stored) fail("Sign-in expired; start again", 403);
  const response = await fetch("https://github.com/login/oauth/access_token", {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({
      client_id: env.GITHUB_CLIENT_ID,
      client_secret: env.GITHUB_CLIENT_SECRET,
      code: url.searchParams.get("code"),
      redirect_uri: env.SITE_ORIGIN + "/auth/callback",
      code_verifier: stored.verifier,
    }),
  });
  const credentials = await response.json();
  if (!response.ok || !credentials.access_token)
    fail("GitHub sign-in was not completed", 403);
  const userResponse = await fetch("https://api.github.com/user", {
    headers: {
      Authorization: "Bearer " + credentials.access_token,
      "User-Agent": "Atlas-of-Threads",
      Accept: "application/vnd.github+json",
    },
  });
  const user = await userResponse.json();
  if (!userResponse.ok || !Number.isSafeInteger(user.id) || !user.login)
    fail("Could not verify GitHub owner", 403);
  const session = token();
  await env.DB.batch([
    env.DB.prepare(
      "INSERT INTO owners(id,login,created_at) VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET login=excluded.login",
    ).bind(String(user.id), user.login, now()),
    env.DB.prepare("DELETE FROM sessions WHERE expires_at<?").bind(now()),
    env.DB.prepare("INSERT INTO sessions VALUES(?,?,?)").bind(
      await sha(session),
      String(user.id),
      now() + 7 * 86400,
    ),
  ]);
  // GitHub access/refresh tokens are deliberately not retained; local service sessions are revocable.
  const headers = new Headers({ Location: "/", "Cache-Control": "no-store" });
  headers.append(
    "Set-Cookie",
    cookieHeader(env, "atlas_session", session, 7 * 86400),
  );
  headers.append("Set-Cookie", cookieHeader(env, "atlas_state", "", 0));
  return new Response(null, { status: 302, headers });
}
const rows = `SELECT p.*,o.login,o.kind,
  (SELECT min(first.seq) FROM publications first WHERE first.threadwalk_id=p.threadwalk_id) AS world_seq,
  (SELECT count(*) FROM publications prior WHERE prior.threadwalk_id=p.threadwalk_id AND prior.seq<=p.seq) AS edition
  FROM publications p JOIN owners o ON o.id=p.owner_id`;
const latestOnly = "p.seq=(SELECT max(last.seq) FROM publications last WHERE last.threadwalk_id=p.threadwalk_id)";
const publicRow = (row) => ({
  id: row.id,
  sequence: row.world_seq,
  threadwalk_id: row.threadwalk_id,
  previous_id: row.previous_id,
  edition: row.edition,
  inquiry_id: row.inquiry_id,
  title: row.title,
  author: row.author,
  description: row.description,
  owner: {
    id: row.owner_id,
    login: row.login,
    verified: row.kind === "github",
  },
  graph_count: row.graph_count,
  thought_count: row.thought_count,
  created_at: row.created_at,
  withdrawn: !!row.withdrawn_at,
  ...position(row.world_seq),
});
async function publication(env, id) {
  if (!/^[a-f0-9]{64}$/.test(id)) fail("Publication not found", 404);
  const row = await env.DB.prepare(
    rows + " WHERE p.id=?",
  )
    .bind(id)
    .first();
  if (!row) fail("Publication not found", 404);
  if (row.withdrawn_at) fail("This publication has been withdrawn", 410);
  return row;
}
async function registerInstance(env, ownerId, name, sessionHash) {
  const id = crypto.randomUUID(), key = token();
  const result = await env.DB.prepare(`INSERT INTO instances SELECT ?,?,?,?,?,NULL
    WHERE (SELECT count(*) FROM instances WHERE owner_id=? AND revoked_at IS NULL)<10
    AND EXISTS(SELECT 1 FROM sessions WHERE hash=? AND owner_id=? AND expires_at>?)`)
    .bind(id,ownerId,name,await sha(key),now(),ownerId,sessionHash,ownerId,now()).run();
  if (!result.meta.changes) fail("Revoke an unused device first", 429);
  return { id, service: env.SITE_ORIGIN, token: key, name };
}
export default {
  async fetch(r, env) {
    try {
      const u = new URL(r.url),
        path = u.pathname;
      if (path === "/auth/login" || path === "/auth/callback")
        return await auth(r, env, u);
      if (!path.startsWith("/api/")) return env.ASSETS.fetch(r);
      if (r.method === "GET") {
        if(path==="/api/expeditions"||path==="/api/expeditions/history")
          return json(await expeditions(env,u,await identity(r,env,false)));
        if (path.startsWith("/api/capsules") || path === "/api/blocks")
          return json(await capsuleGet(env, u, await identity(r, env)));
        if (path === "/api/health")
          return json({
            ok: true,
            mode: "online-preview",
            github_configured: !!(
              env.GITHUB_CLIENT_ID && env.GITHUB_CLIENT_SECRET
            ),
          });
        if (path === "/api/me")
          return json({ owner: await identity(r, env, false) });
        if (path === "/api/world") {
          const cursor = Math.max(
            0,
            Math.floor(Number(u.searchParams.get("after")) || 0),
          );
          const { results } = await env.DB.prepare(
            rows + ` WHERE p.withdrawn_at IS NULL AND ${latestOnly} AND world_seq>? ORDER BY world_seq LIMIT 100`,
          )
            .bind(cursor)
            .all();
          return json({
            publications: results.map(publicRow),
            next: results.length === 100 ? results.at(-1).world_seq : null,
          });
        }
        if (path === "/api/edition-head") {
          const who = await identity(r, env);
          const row = await env.DB.prepare(rows + " WHERE p.owner_id=? AND p.origin_id=? AND p.session_id=? ORDER BY p.seq DESC LIMIT 1")
            .bind(who.id,u.searchParams.get("origin") || "",u.searchParams.get("session") || "").first();
          return json({ publication: row ? publicRow(row) : null });
        }
        if (path === "/api/mine") {
          const who = await identity(r, env);
          const { results } = await env.DB.prepare(
            rows + " WHERE p.owner_id=? ORDER BY p.seq",
          )
            .bind(who.id)
            .all();
          return json({ publications: results.map(publicRow) });
        }
        if (path === "/api/library") {
          const who = await identity(r, env);
          const { results } = await env.DB.prepare(rows + ` JOIN subscriptions s ON s.threadwalk_id=p.threadwalk_id
            WHERE s.owner_id=? AND ${latestOnly} AND (s.starred=1 OR s.following=1) ORDER BY world_seq`).bind(who.id).all();
          const { results: subscriptions } = await env.DB.prepare("SELECT threadwalk_id,starred,following,seen_seq FROM subscriptions WHERE owner_id=?").bind(who.id).all();
          const { results: updates } = await env.DB.prepare(`SELECT u.*,e.delivery_id FROM updates u JOIN subscriptions s ON s.threadwalk_id=u.threadwalk_id
            JOIN publications p ON p.id=u.publication_id
            LEFT JOIN expedition_events e ON e.seq=u.capsule_event_id LEFT JOIN capsule_deliveries d ON d.id=e.delivery_id
            WHERE s.owner_id=? AND s.following=1 AND u.seq>s.seen_seq
            AND p.withdrawn_at IS NULL AND (u.capsule_event_id IS NULL OR (d.withdrawn_at IS NULL AND ${expeditionVisible}))
            ORDER BY u.seq DESC LIMIT 100`).bind(who.id,...expeditionBindings(who)).all();
          return json({ publications: results.map(publicRow), subscriptions, updates });
        }
        const editions = path.match(/^\/api\/threadwalks\/([a-f0-9]{64})$/);
        if (editions) {
          const { results } = await env.DB.prepare(rows + " WHERE p.threadwalk_id=? ORDER BY p.seq DESC").bind(editions[1]).all();
          if (!results.length) fail("Threadwalk not found", 404);
          return json({ publications: results.map(publicRow) });
        }
        if (path === "/api/instances") {
          const who = await identity(r, env);
          return json(
            await env.DB.prepare(
              "SELECT id,name,created_at,revoked_at FROM instances WHERE owner_id=?",
            )
              .bind(who.id)
              .all(),
          );
        }
        const match = path.match(
          /^\/api\/publications\/([a-f0-9]{64})(?:\/(bundle|player))?$/,
        );
        if (match) {
          const row = await publication(env, match[1]);
          if (!match[2]) return json(publicRow(row));
          const object = await env.INQUIRIES.get(row.object_key);
          if (!object) fail("Publication is temporarily unavailable", 503);
          const artifact = await object.json();
          return new Response(
            match[2] === "bundle"
              ? artifact.inquiry_json
              : artifact.player_json,
            {
              headers: {
                "Content-Type": "application/json; charset=utf-8",
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                ...(match[2] === "bundle"
                  ? {
                      "Content-Disposition": `attachment; filename="${row.inquiry_id.slice(0, 12)}.atlas-inquiry.json"`,
                    }
                  : {}),
              },
            },
          );
        }
        fail("Unknown Atlas resource", 404);
      }
      if (r.method !== "POST") fail("Method not allowed", 405);
      sameOrigin(r, env);
      if (path === "/api/pairings/exchange") {
        const data = await body(r);
        if (typeof data.code !== "string" || data.code.length > 100) fail("Enter the pairing code from your signed-in Atlas");
        const codeHash = await sha(data.code.trim()), id = crypto.randomUUID(), key = token();
        // Issuance and consumption share a transaction with respect to account revocation.
        // A lost exchange needs a new code; no recoverable bearer is stored on the service.
        await env.DB.batch([
          env.DB.prepare(`INSERT INTO instances SELECT ?,p.owner_id,p.name,?,?,NULL FROM pairings p
            WHERE p.code_hash=? AND p.expires_at>? AND
            (SELECT count(*) FROM instances i WHERE i.owner_id=p.owner_id AND i.revoked_at IS NULL)<10`)
            .bind(id,await sha(key),now(),codeHash,now()),
          env.DB.prepare("DELETE FROM pairings WHERE code_hash=? AND EXISTS(SELECT 1 FROM instances WHERE id=?)").bind(codeHash,id),
        ]);
        const instance = await env.DB.prepare("SELECT name FROM instances WHERE id=? AND revoked_at IS NULL").bind(id).first();
        if (!instance) {
          const pending = await env.DB.prepare("SELECT 1 FROM pairings WHERE code_hash=? AND expires_at>?").bind(codeHash,now()).first();
          if (pending) fail("Revoke an unused device first", 429);
          fail("Pairing code expired, already used or revoked; create a new one", 403);
        }
        return json({ id, service: env.SITE_ORIGIN, token: key, name: instance.name }, 201);
      }
      const who = await identity(r, env);
      if (path === "/api/logout") {
        await env.DB.prepare("DELETE FROM sessions WHERE hash=?")
          .bind(await sha(cookie(r, "atlas_session") || ""))
          .run();
        return new Response("{}", {
          headers: {
            "Content-Type": "application/json",
            "Set-Cookie": cookieHeader(env, "atlas_session", "", 0),
          },
        });
      }
      const data = await body(r);
      if (path.startsWith("/api/capsules") || path === "/api/blocks")
        return json(await capsulePost(env, path, who, data));
      if (path === "/api/account/revoke") {
        if (who.instance_id) fail("Disconnect all devices from your signed-in browser", 403);
        await env.DB.batch([
          env.DB.prepare("DELETE FROM sessions WHERE owner_id=?").bind(who.id),
          env.DB.prepare("DELETE FROM pairings WHERE owner_id=?").bind(who.id),
          env.DB.prepare("UPDATE instances SET revoked_at=COALESCE(revoked_at,?) WHERE owner_id=?").bind(now(), who.id),
        ]);
        return json({ revoked: true });
      }
      if (path === "/api/instances" || path === "/api/pairings") {
        if (who.instance_id) fail("Register devices from your signed-in browser", 403);
        if (typeof data.name !== "string" || !data.name.trim() || data.name.length > 80)
          fail("Give this Personal Atlas a name");
        if (path === "/api/instances") return json(await registerInstance(env, who.id, data.name.trim(), await sha(cookie(r, "atlas_session") || "")), 201);
        const code = token();
        const result = await env.DB.batch([
          env.DB.prepare("DELETE FROM pairings WHERE expires_at<? OR owner_id=?").bind(now(), who.id),
          env.DB.prepare(`INSERT INTO pairings SELECT ?,?,?,? WHERE EXISTS
            (SELECT 1 FROM sessions WHERE hash=? AND owner_id=? AND expires_at>?)`)
            .bind(await sha(code), who.id, data.name.trim(), now()+600, await sha(cookie(r,"atlas_session") || ""), who.id, now()),
        ]);
        if (!result[1].meta.changes) fail("Sign in again to pair this device", 401);
        return json({ code, service: env.SITE_ORIGIN, expires_in: 600 }, 201);
      }
      const subscription = path.match(/^\/api\/threadwalks\/([a-f0-9]{64})\/(subscription|seen)$/);
      if (subscription) {
        const id = subscription[1];
        const threadwalk = await env.DB.prepare("SELECT id FROM publications WHERE threadwalk_id=? ORDER BY seq DESC LIMIT 1").bind(id).first();
        if (!threadwalk) fail("Threadwalk not found", 404);
        const last = await env.DB.prepare("SELECT COALESCE(max(seq),0) AS seq FROM updates WHERE threadwalk_id=?").bind(id).first();
        if (subscription[2] === "seen") {
          if (!Number.isSafeInteger(data.through) || data.through < 0 || data.through > last.seq) fail("Invalid update receipt");
          await env.DB.prepare("UPDATE subscriptions SET seen_seq=max(seen_seq,?) WHERE owner_id=? AND threadwalk_id=?").bind(data.through, who.id, id).run();
        } else {
          if (typeof data.starred !== "boolean" || typeof data.following !== "boolean") fail("Choose Star and Follow updates separately");
          await env.DB.prepare(`INSERT INTO subscriptions VALUES(?,?,?,?,?) ON CONFLICT(owner_id,threadwalk_id)
            DO UPDATE SET starred=excluded.starred,following=excluded.following,
            seen_seq=CASE WHEN subscriptions.following=0 AND excluded.following=1 THEN excluded.seen_seq ELSE subscriptions.seen_seq END`)
            .bind(who.id,id,Number(data.starred),Number(data.following),last.seq).run();
        }
        return json({ saved: true });
      }
      const revoke = path.match(/^\/api\/instances\/([a-f0-9-]+)\/revoke$/);
      if (revoke) {
        if (who.instance_id && who.instance_id !== revoke[1]) fail("A device can only disconnect itself", 403);
        await env.DB.prepare(
          "UPDATE instances SET revoked_at=? WHERE id=? AND owner_id=?",
        )
          .bind(now(), revoke[1], who.id)
          .run();
        return json({ revoked: true });
      }
      if (path === "/api/publications") {
        if (data.reviewed !== true)
          fail("Review the complete inquiry before publishing");
        const { bundle } = await inspect(data.artifact),
          c = bundle.content,
          id = await sha(who.id + ":" + bundle.id);
        const existing = await env.DB.prepare(
          "SELECT * FROM publications WHERE id=?",
        )
          .bind(id)
          .first();
        if (existing) {
          if (existing.withdrawn_at)
            fail("This snapshot was withdrawn; publish a revised inquiry", 409);
          return json({ id, reused: true });
        }
        const previous = await env.DB.prepare("SELECT id FROM publications WHERE owner_id=? AND origin_id=? AND session_id=? ORDER BY seq DESC LIMIT 1")
          .bind(who.id,c.origin_id,c.session.id).first();
        if ((data.previous_id || null) !== (previous?.id || null))
          fail("This Threadwalk has a newer edition. Review it before publishing the next one", 409);
        const objectKey =
          "publications/" +
          id +
          "/" +
          (await sha(JSON.stringify(data.artifact)));
        await env.INQUIRIES.put(objectKey, JSON.stringify(data.artifact), {
          httpMetadata: { contentType: "application/json" },
        });
        await env.DB.batch([env.DB.prepare(
          `INSERT INTO publications(id,owner_id,instance_id,inquiry_id,origin_id,session_id,title,author,description,graph_count,thought_count,object_key,created_at,threadwalk_id,previous_id)
    SELECT ?,?,?,?,?,?,?,?,?,?,?,?,?,COALESCE((SELECT threadwalk_id FROM publications WHERE owner_id=? AND origin_id=? AND session_id=? ORDER BY seq LIMIT 1),?),?
    WHERE (SELECT count(*) FROM publications WHERE owner_id=?)<?
    AND (SELECT id FROM publications WHERE owner_id=? AND origin_id=? AND session_id=? ORDER BY seq DESC LIMIT 1) IS ? ON CONFLICT DO NOTHING`,
        )
          .bind(
            id,
            who.id,
            who.instance_id || null,
            bundle.id,
            c.origin_id,
            c.session.id,
            c.session.title,
            c.author,
            c.description,
            c.graphs.length,
            c.graphs.reduce((n, g) => n + g.graph.nodes.length, 0),
            objectKey,
            now(),
            who.id, c.origin_id, c.session.id, id, previous?.id || null,
            who.id,
            Number(env.MAX_PUBLICATIONS_PER_OWNER) || 20,
            who.id, c.origin_id, c.session.id, previous?.id || null,
          ), env.DB.prepare("INSERT INTO updates(threadwalk_id,publication_id,kind,created_at) SELECT threadwalk_id,id,'edition',created_at FROM publications WHERE id=? ON CONFLICT DO NOTHING").bind(id)]);
        const saved = await env.DB.prepare(
          "SELECT object_key,withdrawn_at FROM publications WHERE id=?",
        )
          .bind(id)
          .first();
        if (!saved) {
          await env.INQUIRIES.delete(objectKey);
          const latest = await env.DB.prepare("SELECT id FROM publications WHERE owner_id=? AND origin_id=? AND session_id=? ORDER BY seq DESC LIMIT 1").bind(who.id,c.origin_id,c.session.id).first();
          if ((latest?.id || null) !== (previous?.id || null)) fail("A newer edition arrived; review it before publishing", 409);
          fail("Preview publication limit reached", 429);
        }
        if (saved.object_key !== objectKey || saved.withdrawn_at)
          await env.INQUIRIES.delete(objectKey);
        if (saved.withdrawn_at)
          fail("This snapshot was withdrawn; publish a revised inquiry", 409);
        return json({ id, reused: false }, 201);
      }
      const withdraw = path.match(
        /^\/api\/publications\/([a-f0-9]{64})\/withdraw$/,
      );
      if (withdraw) {
        const row = await env.DB.prepare(
          "SELECT * FROM publications WHERE id=? AND owner_id=?",
        )
          .bind(withdraw[1], who.id)
          .first();
        if (!row) fail("Publication not owned by this account", 403);
        await env.DB.prepare(
          "UPDATE publications SET withdrawn_at=COALESCE(withdrawn_at,?) WHERE id=?",
        )
          .bind(now(), row.id)
          .run();
        await env.INQUIRIES.delete(row.object_key);
        return json({ withdrawn: true });
      }
      const report = path.match(
        /^\/api\/publications\/([a-f0-9]{64})\/report$/,
      );
      if (report) {
        await publication(env, report[1]);
        if (
          typeof data.reason !== "string" ||
          !data.reason.trim() ||
          data.reason.length > 2000
        )
          fail("Describe what needs review");
        await env.DB.prepare(
          "INSERT INTO reports VALUES(?,?,?,?) ON CONFLICT DO NOTHING",
        )
          .bind(report[1], who.id, data.reason.trim(), now())
          .run();
        return json({ received: true });
      }
      fail("Unknown Atlas action", 404);
    } catch (error) {
      return json(
        {
          error: error.status
            ? error.message
            : "Atlas is temporarily unavailable",
        },
        error.status || 503,
      );
    }
  },
};
