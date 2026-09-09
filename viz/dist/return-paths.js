/* Local return-path review. Network delivery and the shared world are separate. */
(() => {
  'use strict';
  // Capture before the imported-inquiry adapter redirects renderer API calls.
  const fetchLocal = window.fetch.bind(window);
  const el = (tag, text, parent) => {
    const node = document.createElement(tag); if(text) node.textContent = text;
    if(parent) parent.append(node); return node;
  };
  const button = (text, parent, action) => {
    const node = el('button', text, parent); node.type='button'; node.onclick=action; return node;
  };
  const link = (text, href, parent) => { const node=el('a',text,parent);node.href=href;return node; };
  const stand = () => { const m=location.hash.match(/^#\/g\/([^/]+)\/n\/([^/]+)/);return m ? {graph_id:m[1],node_id:m[2]} : null; };
  const sourceUrl = source => `/#/g/${source.graph_id}/n/${source.node_id}`;
  const visitUrl = offer => offer.inquiry.url.replace('/#', `/?arrival=${offer.id}#`);
  async function api(action, body) {
    const response=await fetchLocal(`/api/return-paths${action}`,body === undefined ? {} : {
      method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)
    });
    const data=await response.json();if(!response.ok) throw Error(data.error || 'Return-path request failed');return data;
  }
  function init() {
    const bar=document.getElementById('portable-bar');
    const dialog=el('dialog','',document.body);dialog.id='return-path-dialog';dialog.className='return-path-dialog';
    const header=el('header','',dialog);el('h2','Returned paths',header);button('Close',header,()=>dialog.close());
    const status=el('p','',dialog);status.setAttribute('role','status');
    const content=el('div','',dialog);
    dialog.addEventListener('keydown',event=>event.stopPropagation());
    const run=async action=>{status.textContent='';try{await action();}catch(error){status.textContent=error.message;}};
    function open() { content.replaceChildren();status.textContent='';if(!dialog.open) dialog.showModal(); }
    function exact(data, parent) {
      const details=el('details','',parent);el('summary','Inspect exact contents',details);el('pre',JSON.stringify(data,null,2),details);
    }
    function consent(text, actionText, action) {
      const label=el('label','',content);const check=el('input','',label);check.type='checkbox';label.append(document.createTextNode(text));
      const commit=button(actionText,content,()=>run(async()=>{if(!check.checked || commit.disabled)return;commit.disabled=true;try{await action();}finally{commit.disabled=!check.checked;}}));
      commit.disabled=true;check.onchange=()=>{commit.disabled=!check.checked;};
    }
    function save(data) {
      const url=URL.createObjectURL(new Blob([JSON.stringify(data)],{type:'application/json'}));
      const a=link('',url);a.download=`return-${data.id.slice(0,12)}.atlas-return.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    }
    function showOffer(offer, info, importing, pending=false) {
      content.replaceChildren();
      el('h3',importing || pending ? 'Review incoming path' : 'Review path to offer back',content);
      el('p',`${info.inquiry.author} · ${info.inquiry.graph_count} generations`,content);
      el('p',`Question: ${info.question}`,content);
      el('p','Sharing names are self-reported. This path is anchored to the exact source; receiving it does not accept it or call an agent.',content);
      for(const record of offer.content.inquiry.content.graphs) {
        const d=el('details','',content);el('summary',record.graph.model.name,d);el('pre',record.graph.prose,d);
        for(const thought of record.graph.nodes) el('p',`${thought.kind} · ${thought.text}`,d);
      }
      exact(offer,content);
      if(pending) {
        consent('Accept this path as a doorway at its source chamber.', 'Accept path',async()=>{
          await api('/decide',{id:offer.id,decision:'accepted'});await showLibrary();await showDoors();
        });
        button('Decline',content,()=>run(async()=>{await api('/decide',{id:offer.id,decision:'declined'});await showLibrary();}));
        return;
      }
      consent(importing ? 'Keep this offer pending in my inbox.' : 'I reviewed these contents and want to save this offer for sharing.',
        importing ? 'Receive for review' : 'Save return-path file', async()=>{
          if(importing){await api('/receive',offer);await showLibrary();}
          else {save(offer);status.textContent='Saved. Share the file with the source inhabitant when ready.';}
        });
    }
    async function showLibrary() {
      content.replaceChildren();const data=await api('');
      el('h3','My private continuations',content);
      el('p','A continuation stays in your Atlas until you review and share an offer.',content);
      for(const path of data.private_paths) {
        const section=el('section','',content);link(path.title,path.url,section);
        const label=el('label','Sharing name',section);const author=el('input','',label);author.maxLength=120;
        button('Review offer back',section,()=>run(async()=>{
          const offer=await api('/export',{session_id:path.session_id,author:author.value});
          showOffer(offer,{inquiry:{author:offer.content.inquiry.content.author,graph_count:offer.content.inquiry.content.graphs.length},question:offer.content.question},false);
        }));
      }
      if(!data.private_paths.length) el('p','Visit an imported inquiry and choose Continue privately to begin.',content);
      el('h3','Receive a return-path file',content);
      const file=el('input','',content);file.type='file';file.accept='.json,application/json';file.setAttribute('aria-label','Choose Atlas return-path file');
      file.onchange=()=>run(async()=>{
        const selected=file.files[0];if(!selected)return;
        if(selected.size>8*1024*1024)throw Error('Return-path file exceeds 8 MiB');
        const offer=JSON.parse(await selected.text());showOffer(offer,await api('/inspect',offer),true);
      });
      el('h3','Incoming paths',content);
      if(!data.offers.length) el('p','No incoming paths yet.',content);
      for(const offer of data.offers) {
        const section=el('section','',content);
        el('p',`${offer.inquiry.author} · ${offer.question} · ${offer.status}`,section);
        link('Source chamber',sourceUrl(offer.source),section);
        if(offer.status==='pending') {
          button('Review path',section,()=>run(async()=>showOffer(await api(`/offers/${offer.id}`),offer,false,true)));
        } else if(offer.status==='accepted') link('Enter accepted path',visitUrl(offer),section);
      }
    }
    if(window.TA_INQUIRY_ID) {
      button('Continue privately',bar,()=>run(async()=>{
        open();const selected=stand();if(!selected)throw Error('Enter a chamber first.');
        el('h3','Continue from this chamber',content);
        el('p','Your collaborator will receive the selected answer, thought and your question. The new path stays private.',content);
        const label=el('label','Your question',content);const question=el('textarea','',label);question.maxLength=400;question.rows=3;
        button('Review context',content,()=>run(async()=>{
          const review=await api('/preview',{...selected,inquiry_id:window.TA_INQUIRY_ID,question:question.value});
          content.replaceChildren();el('h3',`Ask ${review.collaborator}`,content);
          el('p',review.reviewed.question,content);el('p',`Source: ${review.reviewed.context.source.author}`,content);
          el('p',review.reviewed.context.thought.text,content);el('pre',review.reviewed.context.answer,content);exact(review.reviewed.context,content);
          consent('Send this question and source context to my local collaborator.', 'Create private continuation',async()=>{
            const result=await api('/begin',review);location.assign(result.url);
          });
        }));
      }));
      const arrival=new URLSearchParams(location.search).get('arrival');
      if(arrival) run(async()=>{
        const offer=(await api('')).offers.find(item=>item.id===arrival && item.status==='accepted' && item.inquiry.id===window.TA_INQUIRY_ID);
        if(offer) link('Return to source chamber',sourceUrl(offer.source),bar);
      });
    } else {
      button('Returned paths',bar,()=>{open();run(showLibrary);});
    }
    const doors=el('div','',document.body);doors.id='return-path-doors';doors.setAttribute('aria-label','External paths at this chamber');
    async function showDoors() {
      doors.replaceChildren();if(window.TA_INQUIRY_ID)return;
      const selected=stand();if(!selected)return;
      const route=location.hash;
      const data=await api(`/at?graph=${encodeURIComponent(selected.graph_id)}&node=${encodeURIComponent(selected.node_id)}`);
      if(route!==location.hash)return;
      if(data.private_path) {
        const source=data.private_path.source;
        link(`Source · ${source.author}`,`/inquiries/${source.inquiry_id}/#/g/${source.graph_id}/n/${source.node_id}`,doors);
      }
      for(const offer of data.arrivals) link(`Accepted path · ${offer.inquiry.author}`,visitUrl(offer),doors);
    }
    window.addEventListener('hashchange',()=>run(showDoors));run(showDoors);
  }
  document.addEventListener('DOMContentLoaded',init);
})();
