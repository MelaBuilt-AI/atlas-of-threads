/* Deliberate Capsule preparation and offline exchange; Python owns frozen scope. */
(() => {
  'use strict';
  const fetchLocal = window.fetch.bind(window);
  const el = (tag, text, parent) => {
    const n = document.createElement(tag); if(text) n.textContent=text; if(parent) parent.append(n); return n;
  };
  const button = (text,parent,action) => { const n=el('button',text,parent);n.type='button';n.onclick=action;return n; };
  const api = async (path,body) => {
    const response=await fetchLocal(path,body === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const data=await response.json();if(!response.ok) throw Error(data.error || 'Capsule action failed');return data;
  };
  const intents={invitation:'Invite perspectives',offering:'Share a finding',return:'Return a contribution'};
  document.addEventListener('DOMContentLoaded', () => {
    const dialog=el('dialog','',document.body);dialog.id='capsules-dialog';
    const header=el('header','',dialog);el('h2','Capsules',header);button('Close',header,()=>dialog.close());
    const nav=el('nav','',dialog), status=el('p','',dialog), content=el('div','',dialog);status.setAttribute('role','status');
    const run=async action=>{status.textContent='';try{await action();}catch(e){status.textContent=e.message;}};
    const open=()=>{if(!dialog.open)dialog.showModal();};
    const reset=()=>{content.replaceChildren();status.textContent='';dialog.scrollTop=0;};
    const link=(text,href,parent)=>{const n=el('a',text,parent);n.href=href;if(href.startsWith('/#/'))n.onclick=()=>dialog.close();return n;};
    const exact=(value,parent)=>{const d=el('details','',parent);el('summary','Inspect every included field and source reference',d);el('pre',JSON.stringify(value,null,2),d);};
    const field=(label,tag,parent,value='',limit)=>{
      const row=el('label',label,parent), input=el(tag,'',row);input.value=value;
      if(limit)input.maxLength=limit;if(tag==='textarea')input.rows=3;return input;
    };
    function consent(label,actionLabel,action,parent=content) {
      const row=el('label','',parent),check=el('input','',row);check.type='checkbox';row.append(document.createTextNode(label));
      const commit=button(actionLabel,parent,()=>run(async()=>{if(!check.checked||commit.disabled)return;commit.disabled=true;try{await action();}finally{commit.disabled=!check.checked;}}));
      commit.disabled=true;check.onchange=()=>{commit.disabled=!check.checked;};
    }
    function downloads(id,parent=content) {
      const row=el('p','',parent);
      link('Download Capsule JSON',`/api/capsules/download/${id}/json`,row).download=`${id.slice(0,12)}.atlas-capsule.json`;
      row.append(document.createTextNode(' · '));link('Download readable Markdown',`/api/capsules/download/${id}/markdown`,row).download=`${id.slice(0,12)}.capsule.md`;
    }
    function render(capsule) {
      const c=capsule.content;
      el('h3',c.title,content);el('p',`${intents[c.intent]} · sharing name: ${c.author}`,content);
      el('p','Sharing names are supplied by the sender. The checksum identifies this payload; source hashes name the original graph versions. This is an excerpt collection, not a complete Threadwalk.',content);
      el('h4','Question or finding',content);el('pre',c.message,content);
      if(c.interpretation){el('h4','Human interpretation',content);el('pre',c.interpretation,content);}
      if(c.reply_to)el('p',`Return anchored to ${c.reply_to.kind} ${c.reply_to.id || c.reply_to.source.inquiry_id}`,content);
      if(!c.excerpts.length)el('p','No source thoughts included. This Capsule carries only the reviewed message and interpretation.',content);
      for(const excerpt of c.excerpts) {
        const section=el('section','',content);el('h4',`Selected thoughts · ${excerpt.source.model.name}`,section);
        for(const n of excerpt.thoughts){el('p',`${n.kind} · ${n.status}`,section);el('pre',n.text,section);if(n.notes)el('pre',`Notes: ${n.notes}`,section);}
        if(excerpt.question!==null){el('h4','Included source question',section);el('pre',excerpt.question.question,section);}
        if(excerpt.answer!==null){el('h4','Included full answer',section);el('pre',excerpt.answer,section);}
        for(const e of excerpt.evidence){el('p',`Evidence · ${e.summary}`,section);for(const ref of e.artifact_refs)el('pre',ref,section);}
      }
      exact(capsule,content);
    }
    async function prepareView(reply=null, initial={}) {
      reset();
      el('p','Choose what this Capsule carries. Nothing is shared or sent to an agent by choosing an intent.',content);
      const form=el('form','',content), intent=field('Intent','select',form);
      for(const [value,text] of Object.entries(intents)){const o=el('option',text,intent);o.value=value;o.disabled=value==='return'&&!reply;}
      intent.value=initial.intent || (reply?'return':'invitation');
      if(reply) { intent.disabled=true;el('p',`Returning to a received ${reply.kind}. The exact source will be pinned during review.`,form); }
      const title=field('Capsule title','input',form,initial.title || '',240);title.required=true;
      const author=field('Sharing name','input',form,initial.author || '',120);author.required=true;
      const message=field('Question or finding','textarea',form,initial.message || '',4000);message.required=true;
      const interpretation=field('Your interpretation (optional)','textarea',form,initial.interpretation || '',8000);
      const session=field('Optional source Threadwalk','select',form);el('option','No source excerpts',session).value='';
      const data=await api('/api/sessions');
      for(const item of data.sessions || []) {const o=el('option',item.title,session);o.value=item.id;}
      session.value=initial.session_id || '';
      const choices=new Map((initial.selections || []).map(s=>[s.graph_id,structuredClone(s)]));
      const selected=el('p','',form), graphArea=el('section','',form), pickArea=el('section','',form);
      const count=()=>selected.textContent=`Selected: ${[...choices.values()].reduce((n,s)=>n+s.node_ids.length,0)} thoughts across ${choices.size} graphs`;
      count();
      async function graphPicker() {
        graphArea.replaceChildren();pickArea.replaceChildren();if(!session.value)return;
        const data=await api('/api/capsules/graphs?session='+encodeURIComponent(session.value));
        const graph=field('Graph to select from','select',graphArea);el('option','Choose a graph',graph).value='';
        for(const item of data.graphs){const o=el('option',`${item.model} · ${item.created_at} · ${item.id.slice(-6)} · ${item.thought_count} thoughts`,graph);o.value=item.id;}
        graph.onchange=()=>run(async()=>{
          pickArea.replaceChildren();if(!graph.value)return;
          const ctx=await api('/api/capsules/context?graph='+encodeURIComponent(graph.value));
          const choice=choices.get(ctx.graph_id) || {graph_id:ctx.graph_id,node_ids:[],evidence_ids:[],include_answer:false,include_question:false};
          const evidenceChecks=[];
          const saveChoice=()=>{if(choice.node_ids.length)choices.set(ctx.graph_id,choice);else choices.delete(ctx.graph_id);count();};
          el('h4','Choose exact thoughts',pickArea);
          for(const node of ctx.thoughts){
            const row=el('label','',pickArea),check=el('input','',row);check.type='checkbox';check.checked=choice.node_ids.includes(node.id);
            row.append(document.createTextNode(`${node.kind} · ${node.text}`));
            if(node.notes)el('pre',`Notes: ${node.notes}`,row);
            check.onchange=()=>{
              choice.node_ids=check.checked?[...choice.node_ids,node.id]:choice.node_ids.filter(id=>id!==node.id);
              for(const e of evidenceChecks){e.check.disabled=!choice.node_ids.includes(e.node_id);if(e.check.disabled){e.check.checked=false;choice.evidence_ids=choice.evidence_ids.filter(id=>id!==e.id);}}
              saveChoice();
            };
          }
          const option=(text,key,body)=>{
            const row=el('label','',pickArea),check=el('input','',row);check.type='checkbox';check.checked=choice[key];row.append(document.createTextNode(text));
            const details=el('details','',pickArea);el('summary','Read optional text before including it',details);el('pre',body,details);
            check.onchange=()=>{choice[key]=check.checked;saveChoice();};
          };
          option('Include the full answer too (may contain unselected thoughts)','include_answer',ctx.answer);
          if(ctx.question)option('Include the source question too','include_question',ctx.question.question);
          if(ctx.evidence.length)el('h4','Choose web evidence attached to selected thoughts',pickArea);
          for(const e of ctx.evidence){
            const row=el('label','',pickArea),check=el('input','',row);check.type='checkbox';check.checked=choice.evidence_ids.includes(e.id);check.disabled=!choice.node_ids.includes(e.node_id);
            row.append(document.createTextNode(e.summary));for(const ref of e.artifact_refs)el('pre',ref,row);
            evidenceChecks.push({check,node_id:e.node_id,id:e.id});
            check.onchange=()=>{choice.evidence_ids=check.checked?[...choice.evidence_ids,e.id]:choice.evidence_ids.filter(id=>id!==e.id);saveChoice();};
          }
          button('Clear this graph selection',pickArea,()=>{choices.delete(ctx.graph_id);count();graph.onchange();});
        });
      }
      session.onchange=()=>{choices.clear();count();run(graphPicker);};await graphPicker();
      const submit=el('button','Review exact Capsule',form);submit.type='submit';
      form.onsubmit=e=>{e.preventDefault();run(async()=>{
        const draft={intent:intent.value,title:title.value,author:author.value,message:message.value,interpretation:interpretation.value,session_id:session.value||null,selections:[...choices.values()],reply_to:reply};
        const result=await api('/api/capsules/prepare',draft);reset();render(result.capsule);
        el('p','Unselected thoughts, private guide conversations, old Capsule history, local evidence files and credentials are excluded. Review included prose for anything else private.',content);
        const destination=field('Destination','select',content);el('option','Keep privately in Personal Atlas',destination).value='private';el('option','Export Capsule files for deliberate sharing',destination).value='file';
        consent('I reviewed this complete payload and want to freeze it.','Freeze reviewed Capsule',async()=>{
          const saved=await api('/api/capsules/freeze',{draft,capsule:result.capsule,reviewed:true,destination:destination.value});
          reset();render(result.capsule);el('p',saved.export?'Frozen and exported locally. Nothing was uploaded.':'Frozen and kept privately. You can export this exact Capsule later.',content);
          if(saved.export)downloads(saved.capsule.id);button('Open Capsule library',content,()=>run(libraryView));
        });
        button('Edit contents',content,()=>run(()=>prepareView(reply,draft)));
      });};
    }
    async function savedView(category,id) {
      const capsule=await api(`/api/capsules/${category}/${id}`);reset();render(capsule);
      if(category==='prepared') {
        consent('Export this exact frozen Capsule for sharing.','Export Capsule files',async()=>{await api('/api/capsules/export',{id,reviewed:true});downloads(id);status.textContent='Exported locally. Nothing was uploaded.';});
      } else {
        el('p','Received for private reading. This does not accept a returned contribution or create a shared connection.',content);
        button('Prepare a return Capsule',content,()=>run(()=>prepareView({kind:'capsule',id})));
        button('Continue privately with my collaborator',content,()=>run(()=>workView(capsule)));
      }
    }
    async function workView(capsule) {
      reset();el('h3','Continue from this Capsule',content);
      el('p','Choose excerpts for your collaborator. The question/finding and human interpretation will also be included. Your new Threadwalk stays private.',content);
      const question=field('Your private question','textarea',content,'',400);
      const checked=[];
      capsule.content.excerpts.forEach((e,i)=>{
        const row=el('label','',content),check=el('input','',row);check.type='checkbox';check.checked=true;
        row.append(document.createTextNode(`${e.source.model.name} · ${e.thoughts.length} selected thoughts`));checked.push({check,i});
      });
      button('Review collaborator context',content,()=>run(async()=>{
        const data=await api('/api/capsules/work-preview',{id:capsule.id,question:question.value,excerpts:checked.filter(e=>e.check.checked).map(e=>e.i)});
        reset();el('h3',`Ask ${data.collaborator}`,content);el('pre',data.reviewed.question,content);exact(data.reviewed.context,content);
        consent('Send this reviewed question and Capsule context to my collaborator.','Create private continuation',async()=>{
          const result=await api('/api/capsules/begin-work',{reviewed:true,context:data.reviewed,collaborator:data.collaborator});dialog.close();location.assign(result.url);
        });
        button('Change question or excerpts',content,()=>run(()=>workView(capsule)));
      }));
    }
    async function libraryView() {
      reset();const data=await api('/api/capsules/library');
      el('h3','Receive a Capsule file',content);el('p','Inspect first, then choose whether to keep it. Receipt never invokes an agent or accepts a contribution.',content);
      const file=el('input','',content);file.type='file';file.accept='.json,application/json';file.setAttribute('aria-label','Choose Capsule JSON file');
      file.onchange=()=>run(async()=>{
        const selected=file.files[0];if(!selected)return;if(selected.size>256*1024)throw Error('Capsule exceeds 256 KiB');
        const capsule=JSON.parse(await selected.text());await api('/api/capsules/inspect',capsule);reset();render(capsule);
        consent('Keep this Capsule in my received collection for private review.','Receive Capsule',async()=>{await api('/api/capsules/receive',{capsule,reviewed:true});await savedView('received',capsule.id);});
      });
      for(const category of ['prepared','received']) {
        el('h3',category==='prepared'?'Prepared Capsules':'Received Capsules',content);
        if(!data[category].length)el('p','None yet.',content);
        for(const c of data[category]){const row=el('section','',content);el('p',`${c.title} · ${intents[c.intent]} · ${c.author} · ${c.thought_count} thoughts`,row);button('Read Capsule',row,()=>run(()=>savedView(category,c.id)));}
      }
      el('h3','Private work from Capsules',content);
      if(!data.workspaces.length)el('p','Received Capsules can start a separate, reviewed private continuation.',content);
      for(const work of data.workspaces){const row=el('section','',content);link(work.title,work.url,row);button('Read source Capsule',row,()=>run(()=>savedView('received',work.capsule_id)));button('Prepare a return',row,()=>run(()=>prepareView({kind:'capsule',id:work.capsule_id},{session_id:work.session_id})));}
      if(data.legacy.length){
        el('h3','Original local Capsules',content);el('p','Your original one-shot Capsule dossiers and launch history retain their original meaning.',content);
        for(const c of data.legacy){const row=el('section','',content);el('p',c.title,row);button('Read original Capsule',row,()=>run(async()=>{
          const old=await api('/api/knowledge-capsules/'+c.id);reset();el('h3',old.session_title,content);el('p',`Original local Capsule · ${old.state} · ${old.artifact_count} artifacts · integrity ${old.integrity}`,content);
          if(old.markdown_path)el('pre',old.markdown_path,content);link('Visit original Capsule chamber',`/#/g/${old.source_graph_id}/n/${old.source_node_id}`,content);exact(old,content);
        }));}
      }
    }
    button('Prepare',nav,()=>run(()=>prepareView()));button('Library & receive',nav,()=>run(libraryView));
    button('Capsules',document.getElementById('portable-bar'),()=>{open();run(libraryView);});
    if(window.TA_INQUIRY_ID)button('Return Capsule',document.getElementById('portable-bar'),()=>run(async()=>{
      const match=location.hash.match(/^#\/g\/([^/]+)\/n\/([^/]+)/);if(!match)throw Error('Choose an imported thought first');
      open();await prepareView({kind:'inquiry',inquiry_id:window.TA_INQUIRY_ID,graph_id:match[1],node_id:match[2]});
    }));
    dialog.addEventListener('keydown',e=>e.stopPropagation());
  });
})();
