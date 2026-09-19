/* Portable inquiry review and a thin adapter to the existing chamber renderer. */
(() => {
  'use strict';
  const inquiryId = window.TA_INQUIRY_ID;
  const nativeFetch = window.fetch.bind(window);
  const bar = document.createElement('div'); bar.id = 'portable-bar';
  const element = (tag, text, parent) => {
    const node = document.createElement(tag); if(text) node.textContent = text;
    if(parent) parent.append(node); return node;
  };
  const button = (text, parent, action) => {
    const node = element('button', text, parent); node.type = 'button'; node.onclick = action; return node;
  };
  const menu = element('nav', '', document.body); menu.id = 'atlas-menu'; menu.setAttribute('aria-label', 'Atlas menu');
  const panel = element('div', '', menu); panel.className = 'atlas-menu-panel';
  const clip = element('div', '', panel); clip.className = 'atlas-menu-clip'; clip.append(bar);
  const toggle = button('', menu, () => setExpanded(toggle.getAttribute('aria-expanded') !== 'true'));
  toggle.id = 'atlas-menu-toggle'; toggle.setAttribute('aria-controls', 'portable-bar');
  const neuron = element('span', '', toggle); neuron.className = 'atlas-menu-neuron'; neuron.setAttribute('aria-hidden', 'true');
  neuron.innerHTML = '<svg viewBox="0 0 40 40" focusable="false"><path d="M20 20 7 7m13 13L5 25m15-5 8-14m-8 14 15 8m-15-8-3 15M7 7 4 12m24-6 7 1M17 35l7 2"/><circle cx="20" cy="20" r="5"/><circle cx="7" cy="7" r="2"/><circle cx="5" cy="25" r="2"/><circle cx="28" cy="6" r="2"/><circle cx="35" cy="28" r="2"/><circle cx="17" cy="35" r="2"/></svg><i></i><i></i><i></i>';
  const arrow = element('span', '', toggle); arrow.className = 'atlas-menu-arrow'; arrow.setAttribute('aria-hidden', 'true');
  function setExpanded(expanded) {
    menu.dataset.expanded = String(expanded);
    toggle.setAttribute('aria-expanded', String(expanded));
    toggle.setAttribute('aria-label', expanded ? 'Collapse Atlas menu' : 'Expand Atlas menu');
    toggle.title = expanded ? 'Collapse Atlas menu' : 'Expand Atlas menu';
    arrow.textContent = expanded ? '▴' : '▾';
    panel.inert = !expanded; panel.setAttribute('aria-hidden', String(!expanded));
    try { sessionStorage.setItem('atlas.menu.expanded.v1', String(expanded)); } catch {}
  }
  let expanded = false;
  try { expanded = sessionStorage.getItem('atlas.menu.expanded.v1') === 'true'; } catch {}
  setExpanded(expanded);
  menu.addEventListener('keydown', event => {
    if (event.key === 'Escape' && toggle.getAttribute('aria-expanded') === 'true') {
      event.stopPropagation(); setExpanded(false); toggle.focus();
    }
  });
  new ResizeObserver(() => document.documentElement.style.setProperty('--atlas-menu-height', `${menu.getBoundingClientRect().height}px`)).observe(menu);
  async function api(path, body) {
    const response = await nativeFetch(path, body === undefined ? {} : {
      method:'POST', headers:{'Content-Type':'application/json'}, body:typeof body === 'string' ? body : JSON.stringify(body)
    });
    const data = await response.json(); if(!response.ok) throw Error(data.error || 'Inquiry request failed'); return data;
  }
  if(inquiryId) {
    document.body.classList.add('imported-inquiry');
    window.fetch = (input, options) => {
      if(typeof input === 'string' && input.startsWith('/api/')) input = `/api/inquiries/${inquiryId}/${input.slice(5)}`;
      return nativeFetch(input, options);
    };
    const label = element('span', 'Visiting shared inquiry', bar);
    const home = element('a', 'Return to my Atlas', bar); home.href = '/';
    api(`/api/inquiries/${inquiryId}/info`).then(info => {
      label.textContent = `${info.title} · shared by ${info.author}`;
      label.title = `${info.description}\nPublisher-supplied attribution · read-only snapshot · guide discussion stays private`;
    }).catch(error => { label.textContent = error.message; });
    window.addEventListener('keydown', event => {
      if(event.target.closest?.('input,textarea,[contenteditable="true"]')) return;
      if(['f','v','q','p','w','j','k','m'].includes(event.key.toLowerCase())) {
        event.preventDefault(); event.stopImmediatePropagation();
      }
    }, true);
    return;
  }
  const connection = element('dialog', '', document.body); connection.id = 'online-connection-dialog';
  const connectionHeader = element('header', '', connection); element('h2', 'Connect to the Atlas', connectionHeader);
  button('Close', connectionHeader, () => connection.close());
  element('p', 'Connecting identifies this Personal Atlas with your verified GitHub account. It does not publish your inquiries, send Capsules or call an agent.', connection);
  const connectionStatus = element('p', '', connection); connectionStatus.setAttribute('role', 'status');
  const connectionControls = element('section', '', connection);
  const connectionButtons = [];
  const travel = element('a', 'Travel to the Atlas', bar);
  travel.target = '_blank'; travel.rel = 'noopener noreferrer'; travel.hidden = true;
  travel.title = 'Open the shared Atlas in a new tab';
  let checkingConnection = false;
  function paintConnection(online) {
    for (const control of connectionButtons) {
      control.textContent = online ? 'You are connected to the Atlas' : 'Connect to the Atlas';
      control.dataset.connected = String(online);
    }
  }
  async function refreshConnection() {
    if (checkingConnection || document.hidden) return;
    if (!navigator.onLine) { paintConnection(false); return; }
    checkingConnection = true;
    try {
      const saved = await api('/api/online/connection');
      travel.href = saved.service; travel.hidden = false;
      const verified = saved.connected && await api('/api/online/check', {});
      paintConnection(!!verified?.verified_now && navigator.onLine);
    } catch { paintConnection(false); }
    finally { checkingConnection = false; }
  }
  async function showConnection() {
    connectionControls.replaceChildren();
    const info = await api('/api/online/connection');
    if (info.connected) {
      connectionStatus.textContent = `Saved connection: @${info.device.owner.login} · ${info.device.name}. Check connection to verify it is still active.`;
      button('Check connection', connectionControls, () => connectionAction(async () => {
        const result = await api('/api/online/check', {}); paintConnection(!!result.verified_now && navigator.onLine);
        connectionStatus.textContent = result.verified_now ? 'Connected and verified now. Your inquiries remain private until you publish them.' : 'This Personal Atlas is no longer connected.';
      }));
      button('Disconnect this Personal Atlas', connectionControls, () => connectionAction(async () => {
        await api('/api/online/disconnect', {}); paintConnection(false); await showConnection();
      }));
      const details = element('details', '', connectionControls); element('summary', 'Offline or already revoked?', details);
      element('p', 'Forget the credential on this computer if you cannot reach the service. To revoke any still-active access, open your online Atlas account and disconnect this device there.', details);
      button('Forget local connection', details, () => connectionAction(async () => {
        await api('/api/online/disconnect', {forget_only:true}); paintConnection(false); await showConnection();
        connectionStatus.textContent = 'Local credential removed. Disconnect the device in your online account to revoke any remaining access.';
      }));
    } else {
      connectionStatus.textContent = 'Local-only · no account required for your Personal Atlas.';
      const link = element('a', 'Open the online Atlas', connectionControls); link.href = info.service; link.target = '_blank'; link.rel = 'noopener noreferrer';
      element('p', 'Sign in there, open your account name, and create a pairing code for this computer. Paste the code below within ten minutes.', connectionControls);
      const form = element('form', '', connectionControls), label = element('label', 'Single-use pairing code', form);
      const code = element('input', '', label); code.type = 'password'; code.required = true; code.maxLength = 100; code.autocomplete = 'off';
      const submit = element('button', 'Connect this Personal Atlas', form); submit.type = 'submit';
      form.onsubmit = event => {
        event.preventDefault(); submit.disabled = true;
        connectionAction(async () => { await api('/api/online/connect', {code:code.value}); paintConnection(navigator.onLine); code.value=''; await showConnection(); }).finally(() => { submit.disabled=false; });
      };
    }
  }
  async function connectionAction(action) {
    try { await action(); } catch (error) { paintConnection(false); connectionStatus.textContent = error.message; }
  }
  connection.addEventListener('keydown', event => event.stopPropagation());
  connection.addEventListener('close', () => connectionControls.replaceChildren());
  const openConnection = () => { connection.showModal(); connectionAction(showConnection); };
  connectionButtons.push(button('Connect to the Atlas', bar, openConnection));
  const dialog = document.createElement('dialog'); dialog.id = 'portable-dialog'; document.body.append(dialog);
  const heading = element('header', '', dialog); element('h2', 'Portable inquiries', heading);
  button('Close', heading, () => dialog.close());
  element('p', 'Share one reviewed Threadwalk, or visit a snapshot someone has sent you. Your guide discussion stays in your own Atlas.', dialog);
  const status = element('p', '', dialog); status.setAttribute('role','status');
  const controls = element('div', '', dialog);
  const exportSection = element('section', '', controls); element('h3', 'Prepare a Threadwalk', exportSection);
  const form = element('form', '', exportSection);
  const label = (text, node) => { const row = element('label', text, form); row.append(node); return node; };
  const select = label('Threadwalk', element('select')); select.required = true;
  const author = label('Sharing name', element('input')); author.required = true; author.maxLength = 120; author.autocomplete='off';
  const description = label('Description', element('textarea')); description.maxLength = 2000; description.rows = 2;
  const previewButton = element('button', 'Review export', form); previewButton.type = 'submit';
  const importSection = element('section', '', controls); element('h3', 'Open an inquiry file', importSection);
  const file = element('input', '', importSection); file.type='file'; file.accept='.json,application/json'; file.setAttribute('aria-label','Choose Atlas inquiry file');
  const importStatus = element('p', '', importSection); importStatus.setAttribute('role', 'status');
  const review = element('section', '', dialog); review.hidden = true;
  const library = element('section', '', dialog);
  const run = async action => {
    status.textContent = 'Reading inquiry…';
    try { await action(); status.textContent = ''; } catch(error) { status.textContent = error.message; }
  };
  async function refresh() {
    const [sessions, imported] = await Promise.all([api('/api/sessions'), api('/api/inquiries')]);
    select.replaceChildren();
    for(const session of sessions.sessions || []) {
      if(!session.head_graph_id) continue;
      const option = element('option', session.title, select); option.value = session.id;
    }
    previewButton.disabled = !select.options.length;
    library.replaceChildren(); element('h3','Imported inquiries',library);
    if(!imported.inquiries.length) element('p','No imported inquiries yet.',library);
    for(const info of imported.inquiries) {
      const row = element('p','',library); const link = element('a',info.title,row); link.href=info.url;
      element('span',` · ${info.author} · ${info.graph_count} generations`,row);
    }
  }
  function showReview(bundle, info, importing, inquiryJSON) {
    review.replaceChildren(); review.hidden=false;
    element('h3', `${importing ? 'Review import' : 'Review export'} · ${info.title}`, review);
    element('p',`${info.author} · ${info.graph_count} ${info.graph_count === 1 ? "generation" : "generations"} · ${info.thought_count} thoughts · ${info.evidence_count} web evidence links`,review);
    element('p',info.description,review);
    element('p','The sharing name is supplied by the publisher. Checksums identify this snapshot; they do not verify the author.',review);
    element('p',`Excluded: ${info.excluded.join('; ')}. ${info.omitted_evidence_count} other evidence bindings omitted.`,review);
    element('p','Review the text and links below for anything private. The full contents include every generation of this selected Threadwalk. Nothing is sent to an agent until you ask your guide.',review);
    for(const record of bundle.content.graphs) {
      const details = element('details','',review);
      element('summary',`${record.graph.model.name} · ${record.graph.nodes[0].text.slice(0,110)}`,details);
      if(record.source) element('p',`Source question (${record.source.author}): ${record.source.question}`,details);
      element('pre',record.graph.prose,details);
      for(const node of record.graph.nodes) element('p',`${node.kind} · ${node.text}`,details);
    }
    const exact = element('details','',review); element('summary','Inspect exact file, source references and checksums',exact);
    element('pre',inquiryJSON,exact);
    const consent = element('label','',review); const check=element('input','',consent); check.type='checkbox';
    consent.append(document.createTextNode(importing ? 'I want to keep this snapshot in my imported inquiries.' : 'I reviewed these contents and want to save this file for sharing.'));
    const commit = button(importing ? 'Import and visit' : 'Save inquiry file',review,() => run(async () => {
      if(!check.checked) return;
      if(importing) { const result=await api('/api/inquiries/import',inquiryJSON); location.assign(result.url); }
      else {
        const blob = new Blob([inquiryJSON], {type:'application/json'});
        const url=URL.createObjectURL(blob); const link=element('a');link.href=url;
        link.download=`inquiry-${info.id.slice(0,12)}.atlas-inquiry.json`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
        commit.textContent='Saved · ready to share';
      }
    }));
    const online = !importing ? button('Save online publication file', review, () => run(async () => {
      if(!check.checked) return;
      const artifact = await api('/api/online/prepare', inquiryJSON);
      const url = URL.createObjectURL(new Blob([JSON.stringify(artifact)], {type:'application/json'}));
      const link = element('a'); link.href=url; link.download=`inquiry-${info.id.slice(0,12)}.atlas-publication.json`;
      link.click(); setTimeout(()=>URL.revokeObjectURL(url),1000);
      online.textContent='Saved · upload and review in the online Atlas';
    })) : null;
    if(online) online.disabled=true;
    commit.disabled=true; check.onchange=()=>{commit.disabled=!check.checked; if(online) online.disabled=!check.checked;};
    review.scrollIntoView({block:'start'});
  }
  form.onsubmit = event => { event.preventDefault(); run(async () => {
    const result=await api('/api/inquiries/preview',{session_id:select.value,author:author.value,description:description.value});
    showReview(result.bundle,result.summary,false,result.inquiry_json);
  }); };
  file.onchange = async () => {
    review.hidden=true; importStatus.textContent=''; const selected=file.files[0]; if(!selected) return;
    importStatus.textContent='Reading and checking your inquiry…';
    try {
      if(selected.size > 8*1024*1024) throw Error('Inquiry file exceeds 8 MiB');
      const inquiryJSON=await selected.text(), bundle=JSON.parse(inquiryJSON);
      const info=await api('/api/inquiries/inspect',inquiryJSON);
      showReview(bundle,info,true,inquiryJSON); importStatus.textContent='Ready to review below.';
    } catch(error) { importStatus.textContent=error.message; }
    finally { file.value=''; }
  };
  dialog.addEventListener('keydown',event=>event.stopPropagation());
  function open() { dialog.showModal(); review.hidden=true; run(refresh); }
  button('Portable inquiries',bar,open);
  const workspace=document.getElementById('workspace-menu');
  const section=element('section','',workspace);section.className='menu-section';button('Portable inquiries',section,open);connectionButtons.push(button('Connect to the Atlas',section,openConnection));
  addEventListener('offline', () => paintConnection(false));
  addEventListener('online', refreshConnection);
  document.addEventListener('visibilitychange', refreshConnection);
  setInterval(refreshConnection, 30000);
  refreshConnection();
})();
