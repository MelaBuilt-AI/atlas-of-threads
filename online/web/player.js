/* Read-only transport adapter; all chamber/read semantics come from Python. */
(() => {
  "use strict";
  const id = new URL(location.href).searchParams.get("publication"),
    nativeFetch = window.fetch.bind(window);
  const reply = (data, status = 200) =>
    new Response(JSON.stringify(data), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  const load = async (kind) => {
    const r = await nativeFetch(`/api/publications/${id}/${kind}`);
    const d = await r.json();
    if (!r.ok) throw Error(d.error);
    return d;
  };
  window.TA_INQUIRY_ID = id;
  const data = Promise.all([load("bundle"), load("player")]);
  window.TASound =
    window.parent !== window ? window.parent.AtlasWorldAudio?.sound : undefined;
  // The parent owns the score so entering and leaving never restarts the album.
  const blocked = new Set(["f", "v", "q", "p", "w", "j", "k", "m"]);
  window.addEventListener(
    "keydown",
    (e) => {
      if (e.target.closest?.("input,textarea,select")) return;
      if (blocked.has(e.key.toLowerCase())) {
        e.preventDefault();
        e.stopImmediatePropagation();
      }
    },
    true,
  );
  window.fetch = async (input, init) => {
    const url = new URL(
      typeof input === "string" ? input : input.url,
      location.href,
    );
    if (!url.pathname.startsWith("/api/")) return nativeFetch(input, init);
    if ((init?.method || "GET") !== "GET")
      return reply(
        {
          error:
            "Published inquiries are read-only. Download this inquiry to continue in Personal Atlas.",
        },
        403,
      );
    try {
      const [bundle, player] = await data,
        c = bundle.content,
        path = url.pathname.slice(5),
        graphId = url.searchParams.get("graph");
      if (path === "sessions") return reply(player.sessions);
      if (path === "health")
        return reply({ ok: true, write: false, mode: "published-inquiry" });
      if (path === "workspace")
        return reply({
          platform: "web",
          history: player.sessions.sessions.map((s) => ({
            ...s,
            graph_count: c.graphs.length,
          })),
          harnesses: [],
          available_harnesses: [],
          agent_candidates: [],
          pending: [],
          guide: null,
          service: { installed: false },
        });
      if (path === "application/update")
        return reply({ supported: false, available: false });
      if (path === "continuations")
        return reply({ requests: [], parallel_batches: [] });
      if (path === "field-notes" || path === "knowledge-capsules")
        return reply([]);
      if (path === "guide") return reply({ messages: [], enabled: false });
      if (path.startsWith("graphs/")) {
        const g = c.graphs.find((r) => r.graph.id === path.slice(7));
        return g
          ? reply(g.graph)
          : reply({ error: "Graph not in publication" }, 404);
      }
      if (path === "thread/" + c.session.id) {
        const thread = player.threads[graphId || c.session.head_graph_id];
        return thread
          ? reply(thread)
          : reply({ error: "Threadwalk not found" }, 404);
      }
      if (path.startsWith("inhabit/")) {
        const view =
          player.inhabit[
            (graphId || c.session.head_graph_id) + ":" + path.slice(8)
          ];
        if(!view)return reply({ error: "Chamber not found" }, 404);
        const external_doors=[];
        // Read current accepted links separately from the immutable Python chamber projection.
        let cursor=0;
        do {
          const response=await nativeFetch('/api/doorways/public?publication='+id+'&after='+cursor);
          if(!response.ok)throw Error('Shared doorways temporarily unavailable');
          const page=await response.json();cursor=page.next;
          for(const d of page.doorways){
            const source=d.source.publication_id===id&&d.source.graph_id===view.graph_id&&d.source.node_id===view.node.id;
            const returning=d.target.publication_id===id&&(new URL(location.href).searchParams.get('arrival')===d.id||(d.target.graph_id===view.graph_id&&d.target.node_id===view.node.id));
            if(!source&&!returning)continue;
            const dest=source?d.target:d.source;
            external_doors.push({id:d.id,scope:'shared',anchorGraphId:view.graph_id,graphId:dest.graph_id,nodeId:dest.node_id,kind:'claim',
              title:source?dest.title:'Return to source chamber',text:dest.author,returnOrigin:!source,entry:{graph_id:d.target.graph_id,node_id:d.target.node_id},
              description:'An explicitly accepted public contribution doorway.',
              href:'/player/?publication='+dest.publication_id+(source?'&arrival='+d.id:'')+'#/g/'+dest.graph_id+'/n/'+dest.node_id});
          }
        }while(cursor);
        return reply({...view,external_doors});
      }
      return reply({ error: "Unavailable in a published inquiry" }, 404);
    } catch (e) {
      return reply({ error: e.message }, 503);
    }
  };
  data
    .then(([bundle]) => {
      const first =
        bundle.content.graphs.find((r) => r.role === "assistant") ||
        bundle.content.graphs[0];
      if (!location.hash)
        location.hash = `/g/${first.graph.id}/n/${first.graph.nodes.find((n) => n.kind === "claim")?.id || first.graph.nodes[0].id}`;
    })
    .catch((e) => {
      const banner = document.createElement("div");
      banner.className = "publication-error";
      banner.textContent = e.message;
      document.body.append(banner);
    });
})();
