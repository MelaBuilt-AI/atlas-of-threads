import validate from "../dist/validate.js";
import { parse, stringify, isLosslessNumber } from "lossless-json";
export const MAX_BYTES = 8 * 1024 * 1024;
export function fail(message, status = 400) {
  throw Object.assign(new Error(message), { status });
}
export async function sha(value) {
  const bytes =
    typeof value === "string" ? new TextEncoder().encode(value) : value;
  return Array.from(
    new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)),
    (x) => x.toString(16).padStart(2, "0"),
  ).join("");
}
function sorted(value) {
  if (!value || typeof value !== "object" || isLosslessNumber(value))
    return value;
  if (Array.isArray(value)) return value.map(sorted);
  return Object.fromEntries(
    Object.keys(value)
      .sort((a, b) => {
        const x = Array.from(a, (c) => c.codePointAt(0)),
          y = Array.from(b, (c) => c.codePointAt(0));
        for (let i = 0; i < Math.min(x.length, y.length); i++)
          if (x[i] !== y[i]) return x[i] - y[i];
        return x.length - y.length;
      })
      .map((k) => [k, sorted(value[k])]),
  );
}
export const canonical = (value) => stringify(sorted(value)) + "\n";
export async function inspect(artifact) {
  if (
    artifact?.format !== "atlas-publication" ||
    artifact.version !== 1 ||
    typeof artifact.inquiry_json !== "string" ||
    typeof artifact.player_json !== "string" ||
    Object.keys(artifact).some(
      (k) => !["format", "version", "inquiry_json", "player_json"].includes(k),
    )
  )
    fail("Choose an Atlas online publication file");
  if (new TextEncoder().encode(JSON.stringify(artifact)).length > MAX_BYTES)
    fail("Publication exceeds 8 MiB", 413);
  let bundle, lossless, player;
  try {
    bundle = JSON.parse(artifact.inquiry_json);
    lossless = parse(artifact.inquiry_json);
    player = JSON.parse(artifact.player_json);
  } catch {
    fail("Publication contains invalid JSON");
  }
  if (!validate(bundle)) fail("Inquiry does not match the portable schema");
  if ((await sha(canonical(lossless.content))) !== bundle.id)
    fail("Inquiry checksum does not match");
  const c = bundle.content,
    graphs = new Map(c.graphs.map((r) => [r.graph.id, r.graph]));
  if (
    graphs.size !== c.graphs.length ||
    new Set(c.graphs.map((r) => r.graph.turn_id)).size !== graphs.size ||
    !graphs.has(c.session.head_graph_id)
  )
    fail("Incomplete or repeated inquiry identity");
  const nodes = new Map();
  for (let i = 0; i < c.graphs.length; i++) {
    const r = c.graphs[i],
      g = r.graph;
    if (
      g.session_id !== c.session.id ||
      !g.nodes.length ||
      "hidden_reasoning" in g ||
      Object.keys(g.metadata || {}).some((k) => k !== "workspace_origin") ||
      ("workspace_origin" in (g.metadata || {}) &&
        g.metadata.workspace_origin !== true) ||
      g.nodes.some((n) => "probe_ids" in n || "sensor_ids" in n)
    )
      fail("Inquiry contains private or unsupported fields");
    if (
      (await sha(canonical(lossless.content.graphs[i].graph))) !==
      r.shared_sha256
    )
      fail("Graph checksum does not match");
    const ids = new Set(g.nodes.map((n) => n.id));
    if (
      ids.size !== g.nodes.length ||
      g.edges.some((e) => !ids.has(e.source_id) || !ids.has(e.target_id))
    )
      fail("Invalid thought references");
    nodes.set(g.id, ids);
    const seen = new Set([g.id]);
    let parent = g.parent_graph_id;
    while (parent) {
      if (!graphs.has(parent) || seen.has(parent))
        fail("Invalid inquiry ancestry");
      seen.add(parent);
      parent = graphs.get(parent).parent_graph_id;
    }
  }
  for (const r of c.graphs) {
    for (const ref of [
      r.source,
      r.graph.fork && {
        graph_id: r.graph.fork.from_graph_id,
        node_id: r.graph.fork.from_node_id,
      },
    ])
      if (ref && !nodes.get(ref.graph_id)?.has(ref.node_id))
        fail("Source leaves this inquiry");
    if (
      r.graph.fork?.discarded_graph_id &&
      !graphs.has(r.graph.fork.discarded_graph_id)
    )
      fail("Missing discarded graph");
  }
  const evidence = new Set();
  for (const e of c.evidence) {
    if (
      evidence.has(e.id) ||
      !nodes.get(e.graph_id)?.has(e.node_id) ||
      !e.artifact_refs.length
    )
      fail("Invalid evidence");
    evidence.add(e.id);
    for (const ref of e.artifact_refs) {
      let u;
      try {
        u = new URL(ref);
      } catch {
        fail("Invalid evidence link");
      }
      if (!["https:", "http:"].includes(u.protocol) || u.username || u.password)
        fail("Evidence must use public web links");
    }
  }
  // Python prepares the display projection. It is inert, reviewed publisher content,
  // never executable assets or a source of authority for graph writes.
  if (
    !player ||
    Object.keys(player).sort().join(",") !== "inhabit,sessions,threads" ||
    Object.keys(player.threads || {}).length !== graphs.size ||
    Object.keys(player.inhabit || {}).length !==
      c.graphs.reduce((n, r) => n + r.graph.nodes.length, 0) ||
    player.sessions?.sessions?.length !== 1 ||
    player.sessions.sessions[0].id !== c.session.id
  )
    fail("Incomplete player projection");
  for (const g of graphs.values()) {
    if (player.threads[g.id]?.session_id !== c.session.id)
      fail("Player Threadwalk differs from inquiry");
    for (const n of g.nodes) {
      const view = player.inhabit[g.id + ":" + n.id];
      if (
        view?.graph_id !== g.id ||
        view.session_id !== c.session.id ||
        view.node?.id !== n.id ||
        view.node.text !== n.text ||
        view.node.kind !== n.kind
      )
        fail("Player chamber differs from inquiry");
    }
  }
  return { bundle, player };
}
export function position(seq) {
  const angle = (seq - 1) * 2.399963229728653,
    radius = seq === 1 ? 0 : 24 * Math.sqrt(seq - 1);
  return {
    x: Math.round(Math.cos(angle) * radius * 100) / 100,
    z: Math.round(Math.sin(angle) * radius * 100) / 100,
  };
}
