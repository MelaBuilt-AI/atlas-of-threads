/* Thin setup UI: Python owns discovery, host verification and registration. */
(() => {
  const el = (id) => document.getElementById(id);
  let refresh = async () => {};
  let scanning = false;
  let remoteBusy = false;
  let destinationVersion = 0;
  const post = async (path, body = {}) => {
    const r = await fetch(path, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
    const result = await r.json();
    if (!r.ok) throw new Error(result.error || "Connection setup failed.");
    return result;
  };
  function text(tag, value) {
    const node = document.createElement(tag);
    node.textContent = value;
    return node;
  }
  function renderAgents(root, result, remote) {
    root.replaceChildren();
    if (!result.agents.length) {
      root.append(text("p", remote ? "No configured Hermes or OpenClaw agents found on this host. Complete native setup there, then check again." : "No additional Hermes or OpenClaw agents detected. Other local CLI types are listed above."));
    }
    for (const agent of result.agents) {
      const card = document.createElement("article");
      card.className = "onboarding-collaborator discovered-agent";
      const copy = document.createElement("div");
      copy.append(text("strong", agent.display_name), text("small", `${agent.family} · ${agent.model || "model not configured"}`), text("p", agent.detail));
      card.append(copy);
      if (agent.ready) {
        const form = document.createElement("form");
        const label = document.createElement("label");
        label.textContent = "Name in Atlas";
        const display = document.createElement("input");
        display.value = agent.display_name;
        display.required = true;
        display.maxLength = 100;
        label.append(display);
        const keyLabel = document.createElement("label");
        keyLabel.textContent = "Connection name";
        const key = document.createElement("input");
        key.value = `${remote ? "remote" : "local"}-${agent.id.replace(/[^a-zA-Z0-9._-]/g, "-")}`.slice(0, 64);
        key.required = true;
        key.maxLength = 64;
        key.pattern = "[A-Za-z0-9][A-Za-z0-9._-]{0,63}";
        keyLabel.append(key);
        const button = text("button", "Connect agent");
        button.type = "submit";
        const status = text("p", "");
        status.setAttribute("role", "status");
        form.append(label, keyLabel, button, status);
        form.addEventListener("submit", async (event) => {
          event.preventDefault();
          button.disabled = true;
          status.textContent = "Connecting the selected agent…";
          try {
            await post("/api/onboarding/agent/connect", {token: result.token, agent_id: agent.id, name: key.value, display_name: display.value});
            button.textContent = "Connected";
            display.disabled = true;
            key.disabled = true;
            status.textContent = "Connected. Choose its collaborator or guide role in Workspace.";
            await refresh();
          } catch (error) {
            status.textContent = error.message;
            button.disabled = false;
          }
        });
        card.append(form);
      }
      root.append(card);
    }
  }
  async function scanLocal() {
    if (scanning) return;
    scanning = true;
    el("agent-scan-local").disabled = true;
    el("agent-local-status").textContent = "Finding installed agents on this PC…";
    try {
      const result = await post("/api/onboarding/discover");
      renderAgents(el("agent-local-results"), result, false);
      el("agent-local-status").textContent = "Scan complete. Discovery does not call a model or connect an agent until you choose it.";
    } catch (error) {
      el("agent-local-status").textContent = error.message;
    } finally {
      scanning = false;
      el("agent-scan-local").disabled = false;
    }
  }
  function renderHelp(help) {
    const root = el("agent-help-content");
    root.replaceChildren();
    if (!help) return;
    root.append(text("p", help.source_ip ? `Atlas PC address for these rules: ${help.source_ip}` : "Replace <ATLAS_PC_LAN_IP> with this Atlas PC’s LAN address before running any command."));
    for (const section of help.sections) {
      const details = document.createElement("details");
      details.append(text("summary", section.title), text("pre", section.text));
      const copy = text("button", "Copy guidance");
      copy.type = "button";
      copy.addEventListener("click", async () => {
        try { await navigator.clipboard.writeText(section.text); copy.textContent = "Copied"; }
        catch { copy.textContent = "Select the text to copy"; }
      });
      details.append(copy);
      root.append(details);
    }
    for (const link of help.links) {
      const a = text("a", link.title);
      a.href = link.url;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      root.append(a);
    }
  }
  function renderRemote(result) {
    el("agent-remote-status").textContent = result.message;
    el("agent-host-trust").replaceChildren();
    el("agent-remote-results").replaceChildren();
    renderHelp(result.help);
    el("agent-connection-help").open = result.status !== "ready";
    if (result.status === "verify_host") {
      const root = el("agent-host-trust");
      root.append(text("pre", result.fingerprints.join("\n")));
      const label = document.createElement("label");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      label.append(checkbox, document.createTextNode(" I compared this fingerprint on the agent PC."));
      const button = text("button", "Trust verified host and find agents");
      button.disabled = true;
      checkbox.addEventListener("change", () => {button.disabled = !checkbox.checked;});
      button.addEventListener("click", () => checkRemote("/api/onboarding/remote/trust", {token: result.token}));
      root.append(label, button);
    }
    if (result.status === "ready") renderAgents(el("agent-remote-results"), result, true);
  }
  async function checkRemote(path, body) {
    if (remoteBusy) return;
    remoteBusy = true;
    const version = destinationVersion;
    el("agent-remote-form").querySelector("button").disabled = true;
    el("agent-host-trust").replaceChildren();
    el("agent-remote-results").replaceChildren();
    el("agent-remote-status").textContent = "Checking SSH and the configured agents…";
    try {
      const result = await post(path, body);
      if (version === destinationVersion) renderRemote(result);
    }
    catch (error) {el("agent-remote-status").textContent = error.message;}
    finally {
      remoteBusy = false;
      el("agent-remote-form").querySelector("button").disabled = false;
    }
  }
  el("agent-remote-setup").addEventListener("toggle", async () => {
    if (!el("agent-remote-setup").open || el("agent-help-content").childElementCount) return;
    try { renderHelp(await post("/api/onboarding/remote/help", Object.fromEntries(new FormData(el("agent-remote-form"))))); }
    catch (error) {el("agent-help-content").textContent = error.message;}
  });
  el("agent-remote-form").addEventListener("change", async (event) => {
    if (!["platform", "port"].includes(event.target.name)) return;
    try { renderHelp(await post("/api/onboarding/remote/help", Object.fromEntries(new FormData(event.currentTarget)))); }
    catch (error) {el("agent-help-content").textContent = error.message;}
  });
  el("agent-remote-form").addEventListener("submit", (event) => {
    event.preventDefault();
    checkRemote("/api/onboarding/remote/check", Object.fromEntries(new FormData(event.currentTarget)));
  });
  // Editing the destination invalidates visible results from the old host.
  el("agent-remote-form").addEventListener("input", () => {
    destinationVersion += 1;
    el("agent-host-trust").replaceChildren();
    el("agent-remote-results").replaceChildren();
    el("agent-remote-status").textContent = "Check this destination to find its agents.";
  });
  el("agent-scan-local").addEventListener("click", async () => {await refresh(); await scanLocal();});
  window.AtlasAgentConnect = {open: (callback) => {refresh = callback; scanLocal();}};
})();
