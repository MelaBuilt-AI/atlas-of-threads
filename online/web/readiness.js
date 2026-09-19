/* Explicit account activity and reviewed moderation; no local Atlas access. */
window.AtlasReadiness = (() => {
  const $=id=>document.getElementById(id);
  function node(tag,text,parent){const n=document.createElement(tag);n.textContent=text;parent.append(n);return n;}
  let api, refresh;
  function init(request,onChange){api=request;refresh=onChange;}
  async function activityPanel(){
    const host=$('activity-content');host.replaceChildren();
    const state=await api('/api/activity');
    const label=node('label','',host),check=node('input','',label);check.type='checkbox';check.checked=state.enabled;
    label.append(document.createTextNode(' Share a coarse activity light'));
    node('p','Shows a green light beside your public Threadwalks while this Atlas browser is active. No location, chamber, or conversation is shared. The light expires within 90 seconds without a visible online tab.',host);
    const status=node('p',state.enabled?'Sharing is on.':'Activity sharing is off.',host);status.setAttribute('role','status');
    check.onchange=async()=>{check.disabled=true;try{const result=await api('/api/activity',{enabled:check.checked});check.checked=result.enabled;status.textContent=result.enabled?'Sharing is on.':'Activity sharing is off.';await refresh();}catch(e){check.checked=!check.checked;status.textContent=e.message;}finally{check.disabled=false;}};
  }
  async function heartbeat(){if(!document.hidden&&navigator.onLine)await api('/api/activity',{action:'heartbeat'});}
  function report(item){
    const host=$('report-content');host.replaceChildren();node('h3',item.title,host);
    node('p','Describe a concern about this exact public snapshot. Your report is visible only to moderators; it does not automatically remove the inquiry.',host);
    const form=node('form','',host),label=node('label','Reason for review',form),reason=node('textarea','',label);reason.required=true;reason.maxLength=2000;
    const button=node('button','Send report',form),status=node('p','',form);status.setAttribute('role','status');
    form.onsubmit=async e=>{e.preventDefault();button.disabled=true;try{await api(`/api/publications/${item.id}/report`,{reason:reason.value});status.textContent='Report received. This is a review queue, with no promised response time.';}catch(error){status.textContent=error.message;button.disabled=false;}};
    $('report-dialog').showModal();
  }
  async function reports(){
    const host=$('reports-content');host.replaceChildren();
    const label=node('label','Report queue ',host),filter=node('select','',label);
    for(const value of ['open','dismissed','withdrawn']){const option=node('option',value,filter);option.value=value;}
    const list=node('div','',host),more=node('button','Load more',host),status=node('p','',host);status.setAttribute('role','status');let cursor=null;
    async function load(append=false){
      try{const data=await api('/api/reports?status='+filter.value+(append&&cursor?'&after='+cursor:''));if(!append)list.replaceChildren();
        if(!append&&!data.reports.length)node('p','No reports in this queue.',list);
        for(const item of data.reports){
          const row=node('article','',list);node('h3',item.title,row);node('p','Reported by @'+item.reporter_login,row);node('p',item.reason,row);
          const link=node('a','Read exact snapshot',row);link.href='/player/?publication='+item.publication_id;link.target='_blank';link.rel='noopener';
          if(item.status!=='open'){node('p',item.status+' · '+item.review_note,row);continue;}
          const form=node('form','',row),noteLabel=node('label','Decision reason',form),note=node('textarea','',noteLabel);note.required=true;note.maxLength=2000;
          const consent=node('label','',form),check=node('input','',consent);check.type='checkbox';
          consent.append(document.createTextNode(' Remove this exact public snapshot and its shared doors. Downloaded copies remain. This cannot be undone.'));
          const dismiss=node('button','Dismiss report',form),withdraw=node('button','Withdraw snapshot',form);withdraw.disabled=true;
          check.onchange=()=>withdraw.disabled=!check.checked;
          form.onsubmit=async e=>{e.preventDefault();const decision=e.submitter===withdraw?'withdrawn':'dismissed';dismiss.disabled=withdraw.disabled=true;
            try{await api('/api/reports/review',{publication_id:item.publication_id,reporter_id:item.owner_id,status:decision,note:note.value,confirm_withdrawal:check.checked});await load();await refresh();}
            catch(error){status.textContent=error.message;dismiss.disabled=false;withdraw.disabled=!check.checked;}};
        }
        cursor=data.next;more.hidden=!cursor;
      }catch(error){status.textContent=error.message;}
    }
    filter.onchange=()=>load();more.onclick=()=>load(true);await load();$('reports-dialog').showModal();
  }
  return {init,activityPanel,heartbeat,report,reports};
})();
