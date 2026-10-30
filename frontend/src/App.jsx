import React, { useEffect, useRef, useState } from 'react';
import { api, key } from './api.js';
import CustomerView from './CustomerView.jsx';

const labels = { NEW:'New', IN_PROGRESS:'In progress', WAITING_FOR_CUSTOMER:'Waiting for customer', WAITING_FOR_SPECIALIST:'With specialists', RESOLVED:'Resolved', CLOSED:'Closed' };
const demos = [ ['case-clear','01','Automatically resolved','Complete evidence. One clear answer.'], ['case-evidence','02','The evidence loop','One question. The same case.'], ['case-serious','03','A human takes over','A serious incident, with full context.'], ['case-angry','04','Frustrated, but solvable','Empathy without unnecessary escalation.'], ['case-unsupported','05','Recognising limits','Unsupported action → specialist team.'] ];
const nodes = [
 ['intake','01','Intake','Message → case',20,24], ['extract_evidence','02','Context','Data & evidence',305,24], ['assess','03','Assessment','Complete? Supported?',590,24], ['retrieve_policy','04','Knowledge','Demo policy v2',875,24],
 ['validate_action','05','Action validation','Version · Ownership · Authority',875,145], ['send_reply','06','Reply & resolution','Simulated delivery',590,145], ['request_information','↻','Request information','Supply missing information',305,145], ['human_handoff','↗','Specialist team','Reasoned handoff',20,145],
];
const explanations = {
 intake:['One case. One history.','System 1 links messages, evidence and the case version.'],
 extract_evidence:['Data becomes context.','Customer messages and receipts are assembled for assessment.'],
 assess:['Facts before sentiment.','Missing details trigger a question. Negative sentiment alone never triggers a handoff.'],
 retrieve_policy:['A traceable foundation.','System 2 checks stored demo policies. No model access required.'],
 validate_action:['Validate before acting.','System 1 checks version, ownership and authority before execution.'],
 request_information:['AI asks automatically.','AI retains ownership when a clear information gap requires a question.'],
 wait_for_customer:['The reply stays in the case.','The demo reply supplies EUR 42.00. The same case is reassessed.'],
 send_reply:['One reply. One resolution.','The accepted action is simulated. Current case status comes from System 1.'],
 human_handoff:['A handoff with context.','The case includes a reason, facts, evidence and open questions.'],
};
function Badge({status}) { return <span className={`badge ${status}`}>{labels[status] || status}</span>; }
export function Flow({events, index}) {
 const current = events[index];
 const step = current?.stepId === 'wait_for_customer' ? 'request_information' : current?.stepId;
 const done = new Set(events.slice(0,index+1).map(e=>e.stepId));
 return <div className="flow"><svg viewBox="0 0 1160 250" aria-hidden="true"><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0 0 L6 3 L0 6" fill="none" stroke="currentColor"/></marker></defs><g fill="none" stroke="#b8c4cc" strokeWidth="2" markerEnd="url(#arrow)"><path d="M255 65H305 M540 65H590 M825 65H875 M992 102V145 M875 184H825"/><path strokeDasharray="5 6" d="M992 223V245H422V223 M992 245H137V223 M422 145V124H707V102"/></g></svg>
 {nodes.map(([id,num,title,sub,x,y])=><div key={id} className={`node ${done.has(id)?'visited':''} ${step===id?'active':''}`} style={{left:x,top:y}}><span className="node-number">{num}</span><div><strong>{title}</strong><small>{sub}</small></div>{step===id&&<span className="pulse"/>}</div>)}
 <span className="edge-caption">Information request or handoff after action validation</span></div>;
}

export default function App() {
 const [cases,setCases]=useState([]), [selected,setSelected]=useState('case-clear'), [detail,setDetail]=useState(null), [events,setEvents]=useState([]);
 const [view,setView]=useState('console'), [filter,setFilter]=useState('ALL'), [busy,setBusy]=useState(false), [error,setError]=useState(''), [index,setIndex]=useState(0), [playing,setPlaying]=useState(false);
 const [ratio,setRatio]=useState('16:9'),[scale,setScale]=useState(.8),[speed,setSpeed]=useState(1600),[draft,setDraft]=useState('42.00 EUR'),[humanReply,setHumanReply]=useState('Thank you for your patience. We have reviewed your case personally and completed it. This is a simulated reply.');
 const [retry,setRetry]=useState(null); const viewport=useRef(null), generation=useRef(0), pending=useRef(false), execution=useRef(null);
 const stageHeight=ratio==='4:3'?960:ratio==='16:10'?800:720;
 const demo=demos.find(d=>d[0]===selected)||[selected,'06',detail?.subject||'Service case','Shared case history'];
 const current=events[index], explanation=explanations[current?.stepId]||['The action has been applied.','System 1 stores authoritative case status.'];
 const showDemoControls=import.meta.env.VITE_DEMO_CONTROLS!=='false';
 async function refresh(cid=selected) {
   const token=++generation.current;
   const [list,c,feed]=await Promise.all([api('/cases'),api(`/cases/${cid}`),api(`/events?caseId=${encodeURIComponent(cid)}`)]);
   if(token!==generation.current)return;
   setCases(list);setDetail(c);setEvents([...new Map(feed.events.map(event=>[event.eventId,event])).values()].sort((a,b)=>a.sequence-b.sequence));return c;
 }
 useEffect(()=>{setDetail(null);setEvents([]);setIndex(0);setPlaying(false);setError('');setRetry(null);refresh(selected).catch(e=>setError(e.message));return()=>{generation.current++;};},[selected]);
 useEffect(()=>{if(!playing)return;const timer=setInterval(()=>setIndex(i=>{if(i>=events.length-1){setPlaying(false);return i;}return i+1;}),speed);return()=>clearInterval(timer);},[playing,events.length,speed]);
 useEffect(()=>{const size=()=>{if(viewport.current)setScale(Math.max(.1,Math.min((viewport.current.clientWidth-64)/1280,(viewport.current.clientHeight-44)/stageHeight,1.5)));};size();const observer=new ResizeObserver(size);if(viewport.current)observer.observe(viewport.current);return()=>observer.disconnect();},[stageHeight,view]);
 // Keep each accepted command and its original key when resuming a failed submission.
 async function command(path,body) {
   const context=execution.current;
   if(!context)return api(path,body);
   const slot=context.cursor++;
   const step=context.steps[slot]||(context.steps[slot]={path,body});
   if(step.done)return step.result;
   step.result=await api(step.path,step.body);step.done=true;return step.result;
 }
 async function perform(fn,resume=null) {
   if(pending.current)return false;
   pending.current=true;setBusy(true);setError('');setRetry(null);setPlaying(false);
   const context={fn,steps:resume?.steps||[],cursor:0};execution.current=context;
   try {
     const outcome=await fn();
     if(outcome?.selectCaseId){setSelected(outcome.selectCaseId);await refresh(outcome.selectCaseId);}else await refresh();
     return true;
   } catch(e) {
     setError(e.message);
     if(!e.status||e.status>=500)setRetry({fn,steps:context.steps});
     await refresh().catch(()=>{});
     return false;
   } finally {execution.current=null;pending.current=false;setBusy(false);}
 }
 async function process(c) {
   const result=await command(`/cases/${c.id}/process`,{requestId:key(),expectedCaseVersion:c.caseVersion});
   if(result.runResult?.status==='FAILED'){
     const failure=new Error(result.runResult.technicalError?.message||'Assessment failed. Please take over the case manually.');failure.status=422;throw failure;
   }
   return result.case;
 }
 async function reply(c,body=draft,attachmentIds=[]) {
   const updated=await command('/inbound/messages',{messageId:key(),caseId:c.id,channel:'EMAIL',sender:'guest@example.com',body,attachmentIds});
   return updated.owner.type==='AI'?process(updated):updated;
 }
 async function runDemo() {
   const succeeded=await perform(async()=>{
     let c=detail;
     if(['NEW','IN_PROGRESS'].includes(c.status)&&c.owner.type==='AI')c=await process(c);
     if(c.status==='WAITING_FOR_CUSTOMER')await reply(c,'42.00 EUR');
   });
   if(succeeded){setView('presentation');setIndex(0);setPlaying(true);}
 }
 async function upload(file) {
   if(!file||pending.current)return null;
   pending.current=true;setBusy(true);setError('');
   try {
     const form=new FormData();form.append('file',file);
     const response=await fetch(`/api/cases/${selected}/attachments`,{method:'POST',body:form});
     const attachment=await response.json();
     if(!response.ok)throw new Error(attachment.message||attachment.detail?.message||'Attachment could not be saved (maximum 2 MB).');
     await refresh();return attachment;
   } catch(e){setError(e.message);throw e;}finally{pending.current=false;setBusy(false);}
 }
 const metrics=[['ALL','All cases',cases.length],['RESOLVED','Resolved',cases.filter(c=>c.status==='RESOLVED').length],['WAITING_FOR_CUSTOMER','Waiting for customer',cases.filter(c=>c.status==='WAITING_FOR_CUSTOMER').length],['WAITING_FOR_SPECIALIST','With specialists',cases.filter(c=>c.status==='WAITING_FOR_SPECIALIST').length]];
 const visibleCases=filter==='ALL'?cases:cases.filter(c=>c.status===filter);
 const sourcePayload=(detail?.sourceReferences||[]).map(({sourceId,version})=>({sourceId,version}));
 return <div className="app">
  <header className="topbar"><a href="#" className="brand" aria-label="Condor Care Hub"><span className="brand-mark">⤴</span><span>condor<span className="brand-light"> care hub</span></span></a><div className="top-meta"><span className="live-dot"/> Out of The Dark · OpenAI Hackathon</div><div className="tabs">{[['console','Dashboard & Service'],['customer','Customer view'],['presentation','Process view']].map(([id,title])=><button key={id} className={view===id?'selected':''} onClick={()=>setView(id)}>{title}</button>)}</div></header>
  {view!=='customer'&&<div className="controlbar"><div className="scenario-select"><label htmlFor="demo">DEMO SCENARIO</label><select id="demo" value={selected} disabled={busy} onChange={e=>{setFilter('ALL');setSelected(e.target.value);}}>{demos.map(d=><option key={d[0]} value={d[0]}>{d[1]} / {d[2]}</option>)}{cases.filter(c=>!demos.some(d=>d[0]===c.id)).map(c=><option key={c.id} value={c.id}>{c.subject}</option>)}</select></div><div className="control-right">{view==='presentation'&&<><label htmlFor="format">Format</label><select id="format" value={ratio} onChange={e=>setRatio(e.target.value)}><option>16:9</option><option>16:10</option><option>4:3</option></select><button onClick={()=>{const operation=document.fullscreenElement?document.exitFullscreen():document.documentElement.requestFullscreen();operation?.catch(()=>setError('Fullscreen is unavailable in this browser.'));}}>⛶ Fullscreen</button></>}{showDemoControls&&<button disabled={busy} onClick={()=>perform(async()=>{await command('/demo/reset',{actionId:key()});setFilter('ALL');setIndex(0);return {selectCaseId:'case-clear'};})}>Reset demo</button>}<button className="primary" disabled={busy||!detail} onClick={runDemo}>{busy?'Running …':detail&&['RESOLVED','WAITING_FOR_SPECIALIST'].includes(detail.status)?'▶ Replay history':'▶ Start demo'}</button></div></div>}
  {error&&<div className="error" role="alert">{error}<button disabled={busy} onClick={()=>retry?perform(retry.fn,retry):perform(()=>Promise.resolve())}>{retry?'Retry action':'Reload'}</button></div>}
  {view==='customer'?<CustomerView caseDetail={detail} busy={busy} onReply={(body,attachments)=>perform(()=>reply(detail,body,attachments))} onUpload={upload}/>:
  view==='presentation'?<div className="viewport" ref={viewport}><div style={{width:1280*scale,height:stageHeight*scale}}><section className="stage" style={{height:stageHeight,transform:`scale(${scale})`}} aria-label="Workflow presentation"><div className="stripe"/><div className="stage-content"><div className="eyebrow">CONDOR CARE HUB <span> / </span> Out of The Dark</div><div className="hero"><div><div className="demo-kicker">DEMO {demo[1]} <span>•</span> {demo[3]}</div><h1>{demo[2]}<span className="yellow-period">.</span></h1></div><div className="case-ticket"><small>CURRENT CASE STATUS · SYSTEM 1</small><strong>{detail?.id||'Loading …'}</strong>{detail&&<Badge status={detail.status}/>}</div></div><div className="diagram-heading"><span>THE CASE JOURNEY</span><span className="replay-label">● REPLAY OF RECORDED EVENTS</span></div><Flow events={events} index={index}/><div className="explain-row"><article className="explain-main"><div className="eyebrow">{current?`EVENT ${index+1} / ${events.length}`:'READY FOR THE DEMO'}</div><h2>{current?explanation[0]:'From request to resolution.'}</h2><p>{current?.summary||'Start a scenario. System 1 assesses the case and records its history for replay.'}</p></article><article className="explain-detail"><div className="eyebrow">WHY THIS STEP?</div><p>{current?explanation[1]:'Every step comes from the shared event log. Animation does not change case data.'}</p><div className="owner-label">Owner: <b>{detail?.owner.type==='HUMAN'?'Demo agent':detail?.owner.type==='QUEUE'?'Specialist team':'AI service'}</b> · Version {detail?.caseVersion||'–'}</div></article></div><div className="playback"><button aria-label={playing?'Pause replay':'Start replay'} disabled={!events.length} onClick={()=>{if(index===events.length-1)setIndex(0);setPlaying(!playing);}}>{playing?'Ⅱ':'▶'}</button><button aria-label="Previous event" disabled={index===0} onClick={()=>{setPlaying(false);setIndex(i=>i-1);}}>←</button><input aria-label="Select event" type="range" min="0" max={Math.max(0,events.length-1)} value={index} onChange={e=>{setPlaying(false);setIndex(Number(e.target.value));}}/><button aria-label="Next event" disabled={index>=events.length-1} onClick={()=>{setPlaying(false);setIndex(i=>i+1);}}>→</button><select aria-label="Playback speed" value={speed} onChange={e=>setSpeed(Number(e.target.value))}><option value="2600">Slow</option><option value="1600">Normal</option><option value="800">Fast</option></select><span>{String(events.length?index+1:0).padStart(2,'0')} / {String(events.length).padStart(2,'0')}</span></div><footer className="stage-footer"><span>SIMULATION · AI, EMAIL & PAYMENTS · SYNTHETIC DATA</span><span>Out of The Dark <b> / </b> OpenAI Codex Enterprise Hackathon</span></footer></div></section></div></div>:
  <><section className="dashboard" aria-label="Case overview">{metrics.map(([status,title,count])=><button key={status} className={`metric ${filter===status?'active':''}`} disabled={busy} aria-pressed={filter===status} onClick={()=>{setFilter(status);const first=cases.find(c=>status==='ALL'||c.status===status);if(first)setSelected(first.id);}}><span>{title}</span><strong>{count}</strong><small>Stored cases · System 1</small></button>)}</section>
  <main className="console"><aside className="case-list"><div className="list-title"><h2>Service inbox</h2><span>{visibleCases.length} cases</span></div>{visibleCases.length===0&&<p>No cases in this selection.</p>}{visibleCases.map(c=><button key={c.id} disabled={busy} className={`case-item ${selected===c.id?'active':''}`} onClick={()=>setSelected(c.id)}><small>{c.id} · {c.priority}</small><strong>{c.subject}</strong><Badge status={c.status}/><span>{c.owner.type} · {c.nextAction}</span></button>)}</aside><section className="case-detail">{detail?<><div className="detail-heading"><div className="eyebrow">{detail.id} · VERSION {detail.caseVersion}</div><h1>{detail.subject}</h1><Badge status={detail.status}/><span className="detail-owner">{detail.owner.type} / {detail.queue}</span></div><div className="detail-columns"><div><h3>Message history</h3>{detail.messages.map(m=><article key={m.messageId} className={`message ${m.direction==='OUTBOUND'?'outgoing':''}`}><small>{m.direction==='OUTBOUND'?'CONDOR SERVICE · SIMULATED DELIVERY':'CUSTOMER MESSAGE'}</small><p>{m.body}</p></article>)}{detail.handoff&&<article className="handoff"><h3>Prepared handoff</h3><strong>{detail.handoff.reasonCode}</strong><p>{detail.handoff.summary}</p><p>{detail.handoff.unresolvedQuestions.join(' · ')}</p><small>{detail.handoff.priorAttempts.join(' · ')}</small></article>}{detail.financialPositions.length>0&&<article className="financial-result"><h3>Simulated reimbursement</h3>{detail.financialPositions.map((position,i)=><p key={i}>{new Intl.NumberFormat('en-GB',{style:'currency',currency:position.currency}).format(position.amountMinor/100)} · {position.explanation}</p>)}</article>}<h3>Facts & sources</h3>{detail.facts.map((fact,i)=><p key={i} className="fact">✓ {fact}</p>)}{detail.sourceReferences.map(source=><p className="fact" key={`${source.id}-${source.version}`}>{source.title} · v{source.version}</p>)}{detail.attachments.map(attachment=><a className="attachment" key={attachment.attachmentId} href={`/api/cases/${detail.id}/attachments/${attachment.attachmentId}`} target="_blank" rel="noreferrer">↗ {attachment.filename}</a>)}</div><aside className="actions"><h3>Next step</h3><p>{detail.nextAction}</p><button className="primary" disabled={busy||detail.owner.type!=='AI'||!['NEW','IN_PROGRESS'].includes(detail.status)} onClick={()=>perform(()=>process(detail))}>Start AI processing</button><button disabled={busy||['RESOLVED','CLOSED'].includes(detail.status)||detail.owner.type==='HUMAN'} onClick={()=>perform(()=>command(`/cases/${selected}/takeover`,{actionId:key(),expectedCaseVersion:detail.caseVersion,operatorId:'demo-agent'}))}>Take over case</button><label htmlFor="reply">Simulate customer reply</label><textarea id="reply" value={draft} onChange={e=>setDraft(e.target.value)}/><label className="upload">＋ Add synthetic attachment<input type="file" disabled={busy} onChange={e=>{upload(e.target.files[0]).catch(()=>{});e.target.value='';}}/></label><button disabled={busy||!draft.trim()} onClick={()=>perform(()=>reply(detail))}>Submit reply & assess</button>{detail.owner.type==='HUMAN'&&<><label htmlFor="human">Human reply</label><textarea id="human" value={humanReply} onChange={e=>setHumanReply(e.target.value)}/><button className="primary" disabled={busy||!humanReply.trim()||detail.status!=='IN_PROGRESS'} onClick={()=>perform(()=>command(`/cases/${selected}/actions`,{actionId:key(),caseId:selected,expectedCaseVersion:detail.caseVersion,type:'RESOLVE',sources:sourcePayload,payload:{outcome:'MANUAL_REVIEW',explanation:'Personal demo review completed',replyDe:humanReply,sources:sourcePayload,financialPositions:[]}}))}>Send reply & resolve</button></>}<div className="simulation-note">Demo: AI, messages and reimbursements are simulated. No real payments or emails are sent.</div></aside></div><h3>Activity · shared event log</h3><ol className="timeline">{events.map(event=><li key={event.eventId}><small>#{event.sequence} · {event.stepId||event.type}</small><span>{event.summary}</span></li>)}</ol></>:<p>Loading case …</p>}</section></main></>}
 </div>;
}
