/* Portable inquiry review and a thin adapter to the existing chamber renderer. */
(() => {
  'use strict';
  const inquiryId = window.TA_INQUIRY_ID;
  const nativeFetch = window.fetch.bind(window);
  const bar = document.createElement('div'); bar.id = 'portable-bar';
  document.body.append(bar);
  const element = (tag, text, parent) => {
    const node = document.createElement(tag); if(text) node.textContent = text;
    if(parent) parent.append(node); return node;
  };
  const button = (text, parent, action) => {
    const node = element('button', text, parent); node.type = 'button'; node.onclick = action; return node;
  };
  async function api(path, body) {
    const response = await nativeFetch(path, body === undefined ? {} : {
      method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)
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
  function showReview(bundle, info, importing) {
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
    element('pre',JSON.stringify(bundle,null,2),exact);
    const consent = element('label','',review); const check=element('input','',consent); check.type='checkbox';
    consent.append(document.createTextNode(importing ? 'I want to keep this snapshot in my imported inquiries.' : 'I reviewed these contents and want to save this file for sharing.'));
    const commit = button(importing ? 'Import and visit' : 'Save inquiry file',review,() => run(async () => {
      if(!check.checked) return;
      if(importing) { const result=await api('/api/inquiries/import',bundle); location.assign(result.url); }
      else {
        const blob = new Blob([JSON.stringify(bundle)], {type:'application/json'});
        const url=URL.createObjectURL(blob); const link=element('a');link.href=url;
        link.download=`inquiry-${info.id.slice(0,12)}.atlas-inquiry.json`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
        commit.textContent='Saved · ready to share';
      }
    }));
    commit.disabled=true; check.onchange=()=>{commit.disabled=!check.checked;};
    review.scrollIntoView({block:'start'});
  }
  form.onsubmit = event => { event.preventDefault(); run(async () => {
    const result=await api('/api/inquiries/preview',{session_id:select.value,author:author.value,description:description.value});
    showReview(result.bundle,result.summary,false);
  }); };
  file.onchange = () => run(async () => {
    review.hidden=true; const selected=file.files[0]; if(!selected) return;
    if(selected.size > 8*1024*1024) throw Error('Inquiry file exceeds 8 MiB');
    const bundle=JSON.parse(await selected.text());const info=await api('/api/inquiries/inspect',bundle);showReview(bundle,info,true);
  });
  dialog.addEventListener('keydown',event=>event.stopPropagation());
  function open() { dialog.showModal(); review.hidden=true; run(refresh); }
  button('Portable inquiries',bar,open);
  const workspace=document.getElementById('workspace-menu');
  const section=element('section','',workspace);section.className='menu-section';button('Portable inquiries',section,open);
})();
