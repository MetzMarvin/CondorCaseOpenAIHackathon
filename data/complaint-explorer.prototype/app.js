// THROWAWAY UI: three structures over the same full local complaint snapshot.
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const title = value => String(value ?? '').replaceAll('_', ' ').replace(/^\w/, c => c.toUpperCase());
const number = value => Number(value).toLocaleString('en-GB');
const names = {A:'Overview', B:'Case inbox', C:'Action board'};
const actionNames = {resolve_demo:'Demo resolution', request_missing_info:'Missing evidence', request_clarification:'Clarification', escalate_human:'Specialist handoff'};
const state = {variant: new URLSearchParams(location.search).get('variant') || 'A', selected:null, page:0, tab:'complaint', boardLimit:20, filters:{search:'', category:'', language:'', scenario:'', action:'', split:''}};
if (!names[state.variant]) state.variant = 'A';
let data, all = [], filtered = [], by = {};
const countBy = (items, get) => items.reduce((result, item) => (result[get(item)] = (result[get(item)] || 0) + 1, result), {});
const pill = action => `<span class="pill ${esc(action)}">${esc(actionNames[action] || title(action))}</span>`;
const fact = (label, value) => `<div class="fact"><small>${esc(label)}</small><strong>${esc(value)}</strong></div>`;

async function load() {
  $('status').textContent = 'Loading all complaints and linked records…';
  try {
    const response = await fetch('/api/snapshot');
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    data = await response.json();
    for (const table of ['contacts','bookings','flights','messages','attachments']) by[table] = Object.fromEntries(data[table].map(row => [row.id, row]));
    for (const table of ['labels','provenance','simulator']) by[table] = Object.fromEntries(data[table].map(row => [row.case_id, row]));
    all = data.cases.map(c => {
      const booking = by.bookings[c.booking_id], contact = by.contacts[c.contact_id], label = by.labels[c.id];
      const flights = booking.flight_ids.map(id => by.flights[id]);
      const search = [c.id,c.subject,c.description,booking.reference,contact.name,contact.email,...flights.map(f => [f.flight_number,f.origin,f.destination].join(' '))].join(' ').toLocaleLowerCase();
      return {c, booking, contact, label, flights, search};
    });
    for (const [id, values] of Object.entries({category:[...new Set(data.labels.flatMap(l => l.categories))], scenario:[...new Set(data.labels.map(l => l.scenario))], action:Object.keys(actionNames)})) {
      const first = $(id).options[0].outerHTML;
      $(id).innerHTML = first + values.sort().map(value => `<option value="${esc(value)}">${esc(id === 'action' ? actionNames[value] : title(value))}</option>`).join('');
      $(id).value = state.filters[id];
    }
    $('source-badge').innerHTML = `<strong>${number(all.length)} cases</strong> · ${data.validation.valid ? 'Validated' : 'Validation failed'}<br><span class="mono">τ² ${esc(data.manifest.source_revision.slice(0,8))}</span> · seed ${esc(data.manifest.seed)}`;
    render();
  } catch (error) {
    $('status').textContent = `Could not load local data: ${error.message}. Run python3 -m pipeline build, then reload.`;
  }
}

function render() {
  const f = state.filters;
  filtered = all.filter(r => (!f.search || r.search.includes(f.search.toLocaleLowerCase())) && (!f.category || r.label.categories.includes(f.category)) && (!f.language || r.c.language === f.language) && (!f.scenario || r.label.scenario === f.scenario) && (!f.action || r.label.expected_next_action === f.action) && (!f.split || r.label.split === f.split));
  if (!filtered.some(r => r.c.id === state.selected)) state.selected = filtered[0]?.c.id || null;
  const size = state.variant === 'B' ? 15 : 40;
  state.page = Math.min(state.page, Math.max(0,Math.ceil(filtered.length/size)-1));
  $('status').textContent = `${number(filtered.length)} of ${number(all.length)} complaints · ${data.source} · expectations are synthetic and unreviewed`;
  $('variant-label').textContent = `${state.variant} · ${names[state.variant]}`;
  $('view').innerHTML = ({A:VariantA,B:VariantB,C:VariantC}[state.variant])();
  $('state').textContent = JSON.stringify({...state, matching_cases:filtered.length, total_cases:all.length, source:data.source, data_modified:false}, null, 2);
}

function bars(counts, filter, label = title) {
  const max = Math.max(1,...Object.values(counts));
  return Object.entries(counts).sort((a,b) => b[1]-a[1]).map(([key,n]) => `<button class="bar-row" data-filter="${esc(filter)}" data-value="${esc(key)}"><span>${esc(label(key))}</span><span class="bar-track"><i style="width:${n/max*100}%"></i></span><span>${number(n)}</span></button>`).join('');
}

function stats() {
  const actions = countBy(filtered, r => r.label.expected_next_action);
  return `<div class="stats"><div class="stat accent"><small>Complaints in view</small><strong>${number(filtered.length)}</strong><p>${number(filtered.filter(r => r.c.language==='de').length)} DE / ${number(filtered.filter(r => r.c.language==='en').length)} EN</p></div>
    <div class="stat"><small>Demo resolution</small><strong>${number(actions.resolve_demo || 0)}</strong><p>Expected next action</p></div>
    <div class="stat"><small>Need information</small><strong>${number((actions.request_missing_info || 0) + (actions.request_clarification || 0))}</strong><p>Missing or conflicting evidence</p></div>
    <div class="stat"><small>Specialist handoff</small><strong>${number(actions.escalate_human || 0)}</strong><p>Serious or unsupported cases</p></div></div>`;
}

function pager(size) {
  return `<div class="pager"><span>${filtered.length ? state.page*size+1 : 0}–${Math.min((state.page+1)*size,filtered.length)} of ${number(filtered.length)}</span><button data-page="-1" ${state.page===0?'disabled':''}>← Previous</button><button data-page="1" ${(state.page+1)*size>=filtered.length?'disabled':''}>Next →</button></div>`;
}

function VariantA() {
  return stats() + `<div class="charts"><section class="panel"><h2>What are customers reporting?</h2>${bars(countBy(filtered,r=>r.label.categories[0]),'category')}</section><section class="panel"><h2>How did we vary the cases?</h2>${bars(countBy(filtered,r=>r.label.scenario),'scenario')}</section></div>
    <div class="section-heading"><h2>Complaint inventory</h2><span class="small-label">Click a row to inspect its full record</span></div>
    ${filtered.length ? `<div class="table-wrap"><table><thead><tr><th>Case / flight</th><th>Complaint</th><th>Topics</th><th>Language</th><th>Scenario</th><th>Expected next action</th></tr></thead><tbody>${filtered.slice(state.page*40,(state.page+1)*40).map(r=>`<tr data-case="${esc(r.c.id)}" tabindex="0"><td class="mono">${esc(r.c.id)}<br><span class="muted">${esc(r.flights[0].origin)} → ${esc(r.flights[0].destination)}</span></td><td class="subject"><strong>${esc(r.c.subject)}</strong><small>${esc(r.booking.reference)} · ${esc(r.c.created_at.slice(0,10))}</small></td><td>${r.label.categories.map(c=>`<span class="pill">${esc(title(c))}</span>`).join(' ')}</td><td>${esc(r.c.language.toUpperCase())}</td><td>${esc(title(r.label.scenario))}</td><td>${pill(r.label.expected_next_action)}</td></tr>`).join('')}</tbody></table></div>${pager(40)}` : empty()}`;
}

function VariantB() {
  if (!filtered.length) return empty();
  const selected = filtered.find(r=>r.c.id === state.selected);
  return `<div class="section-heading"><h2>Read the customer’s story</h2><span class="small-label">Select a complaint on the left; inspect its context on the right</span></div><div class="inbox"><div><div class="inbox-list">${filtered.slice(state.page*15,(state.page+1)*15).map(r=>`<button class="inbox-row ${r.c.id===state.selected?'active':''}" data-case="${esc(r.c.id)}"><span class="mono">${esc(r.c.id)}</span> <span class="pill">${esc(r.c.language.toUpperCase())}</span><strong>${esc(r.label.categories.map(title).join(' + '))} · ${esc(r.flights[0].origin)} → ${esc(r.flights[0].destination)}</strong><span class="preview">${esc(r.c.description)}</span></button>`).join('')}</div>${pager(15)}</div>${detail(selected)}</div>`;
}

function VariantC() {
  if (!filtered.length) return empty();
  return `<div class="section-heading"><h2>Group by the next expected step</h2><span class="small-label">These columns show reference labels, not live case status</span></div><div class="board">${Object.entries(actionNames).map(([action,label])=>{
    const items = filtered.filter(r=>r.label.expected_next_action===action);
    return `<section class="lane"><div class="lane-header">${esc(label)}<span>${number(items.length)}</span></div>${items.slice(0,state.boardLimit).map(r=>`<button class="card" data-case="${esc(r.c.id)}"><span class="mono muted">${esc(r.c.id)}</span><strong>${esc(r.label.categories.map(title).join(' + '))}</strong><div class="preview">${esc(r.c.description)}</div><footer><span>${esc(r.flights[0].origin)} → ${esc(r.flights[0].destination)} · ${esc(r.c.language.toUpperCase())}</span><span>${esc(title(r.label.scenario))}</span></footer></button>`).join('')}${items.length>state.boardLimit?`<button class="quiet" data-more="true">Show 20 more · ${number(items.length-state.boardLimit)} remaining</button>`:''}${!items.length?'<p class="muted">No matching complaints</p>':''}</section>`;
  }).join('')}</div>`;
}

function empty() { return '<div class="empty">No complaints match these filters. Try another search or reset the filters.</div>'; }

function detail(r) {
  const {c,booking,contact,label,flights} = r;
  const messages = c.message_ids.map(id=>by.messages[id]);
  const attachments = messages.flatMap(m=>m.attachment_ids.map(id=>by.attachments[id]));
  const flight = flights[0];
  const delay = flight.actual_arrival ? Math.round((Date.parse(flight.actual_arrival)-Date.parse(flight.scheduled_arrival))/60000) : 'Cancelled';
  const raw = {case:c,contact,booking,flights,messages,attachments,events:data.events.filter(e=>e.case_id===c.id),synthetic_reference:label,provenance:by.provenance[c.id],future_customer_reply:by.simulator[c.id] || null};
  let body = '';
  if (state.tab === 'complaint') body = `<div class="small-label">FROM ${esc(contact.email)} · ${esc(c.created_at)}</div><div class="message">${esc(c.description)}</div><div class="facts">${fact('Booking',booking.reference)}${fact('Route',`${flight.origin} → ${flight.destination}`)}${fact('Flight',flight.flight_number)}${fact('Passengers',booking.passengers.length)}${fact('Scheduled arrival',flight.scheduled_arrival)}${fact('Actual arrival / delay',`${flight.actual_arrival || 'No arrival · cancelled'} / ${delay}${typeof delay==='number'?' min':''}`)}</div><h3>Evidence attached to the first message</h3>${attachments.length ? attachments.map(a=>`<a class="evidence" href="/api/evidence?id=${encodeURIComponent(a.id)}" target="_blank" rel="noopener">↗ ${esc(title(a.kind))} <span class="mono">${esc(a.id)}</span><br><small>Booking ${esc(a.booking_reference)}${a.amount_eur===null?'':` · EUR ${esc(a.amount_eur)}`} · HTML mock document</small></a>`).join('') : '<p class="muted">No attachment supplied in the initial message.</p>'}`;
  else if (state.tab === 'expectations') body = `<div class="expected"><small>SYNTHETIC REFERENCE · NOT EXPERT REVIEWED</small><h3>${esc(actionNames[label.expected_next_action])}</h3><p>Reason: ${esc(title(label.reason))}</p><p>Missing: ${esc(label.missing_fields.join(', ') || 'None specified')}</p></div><div class="facts">${fact('Primary / all topics',label.categories.map(title).join(' / '))}${fact('Scenario',title(label.scenario))}${fact('Severity',title(label.severity))}${fact('Sentiment',title(label.sentiment))}${fact('Evaluation split',label.split)}${fact('Policy',label.policy_version)}</div><p class="muted">No legal entitlement or compensation amount is asserted. Anger does not itself trigger a handoff.</p>${by.simulator[c.id] ? `<h3 style="margin-top:24px">Hidden customer follow-up fixture</h3><p class="muted">Test-harness data, excluded from the initial runtime input.</p><div class="message">${esc(by.simulator[c.id].reply_body)}</div>` : ''}`;
  else body = `<div class="raw">${Object.entries(raw).map(([name,value])=>`<details ${name==='case'?'open':''}><summary>${esc(title(name))}</summary><pre>${esc(JSON.stringify(value,null,2))}</pre></details>`).join('')}</div>`;
  return `<article class="detail"><div class="detail-header"><span class="mono muted">${esc(c.id)} · ${esc(c.language.toUpperCase())} · ${esc(c.status)} · ${esc(c.channel)}</span><h2>${esc(c.subject)}</h2>${pill(label.expected_next_action)} <span class="pill">${esc(label.split)}</span></div><div class="detail-body"><div class="tabs">${[['complaint','Complaint & facts'],['expectations','Test expectations'],['raw','Full JSON']].map(([id,name])=>`<button class="tab ${state.tab===id?'active':''}" data-tab="${id}">${name}</button>`).join('')}</div>${body}</div></article>`;
}

function openCase(id) {
  state.selected = id;
  if (state.variant === 'B') render();
  else renderOverlay();
  $('state').textContent = JSON.stringify({...state,matching_cases:filtered.length,total_cases:all.length,data_modified:false},null,2);
}

function renderOverlay() {
  const r = all.find(row=>row.c.id===state.selected);
  const previousScroll = $('overlay').querySelector('.drawer')?.scrollTop || 0;
  $('overlay').hidden = false;
  $('overlay').innerHTML = `<div class="overlay-shade"><div class="drawer" role="dialog" aria-modal="true" aria-label="Complaint detail"><div class="drawer-top"><span>COMPLAINT INSPECTOR</span><button class="quiet" data-close="true">Close ✕</button></div>${detail(r)}</div></div>`;
  $('overlay').querySelector('.drawer').scrollTop = previousScroll;
  document.body.style.overflow = 'hidden';
  $('overlay').querySelector('[data-close]').focus({preventScroll:true});
}

function closeOverlay() {
  $('overlay').hidden = true;
  $('overlay').innerHTML = '';
  document.body.style.overflow = '';
}

function cycle(delta) {
  const variants = Object.keys(names);
  state.variant = variants[(variants.indexOf(state.variant)+delta+variants.length)%variants.length];
  state.page = 0;
  const url = new URL(location.href);
  url.searchParams.set('variant',state.variant);
  history.replaceState(null,'',url);
  closeOverlay();
  if (data) render();
}

for (const id of Object.keys(state.filters)) $(id).addEventListener(id==='search'?'input':'change',event=>{
  state.filters[id] = event.target.value;
  state.page = 0;
  state.boardLimit = 20;
  if (data) render();
});
$('reset').onclick = () => { for (const id in state.filters) {state.filters[id]='';$(id).value='';}state.page=0;state.boardLimit=20;render(); };
$('reload').onclick = () => {closeOverlay();load();};
$('previous').onclick = () => cycle(-1);
$('next').onclick = () => cycle(1);
document.addEventListener('click',event=>{
  const target = event.target.closest('[data-case],[data-page],[data-filter],[data-more],[data-tab],[data-close]');
  if (!target) { if (event.target.classList.contains('overlay-shade')) closeOverlay(); return; }
  if (target.dataset.case) openCase(target.dataset.case);
  if (target.dataset.page) {state.page+=Number(target.dataset.page);if(state.variant==='B')state.selected=filtered[state.page*15]?.c.id;render();}
  if (target.dataset.filter) {state.filters[target.dataset.filter]=target.dataset.value;$(target.dataset.filter).value=target.dataset.value;state.page=0;render();}
  if (target.dataset.more) {state.boardLimit+=20;render();}
  if (target.dataset.tab) {state.tab=target.dataset.tab;if (!$('overlay').hidden) renderOverlay();else render();}
  if (target.dataset.close) closeOverlay();
});
document.addEventListener('keydown',event=>{
  if (event.key==='Escape') closeOverlay();
  if (event.key==='Enter' && event.target.matches('tr[data-case]')) openCase(event.target.dataset.case);
  if (event.target.closest('input,textarea,select,[contenteditable]')) return;
  if (!$('overlay').hidden) {
    if (event.key==='Tab') {
      const focusables = [...$('overlay').querySelectorAll('button,a[href],summary')];
      const first = focusables[0], last = focusables.at(-1);
      if (event.shiftKey && document.activeElement===first) {event.preventDefault();last.focus();}
      else if (!event.shiftKey && document.activeElement===last) {event.preventDefault();first.focus();}
    }
    return;
  }
  if (event.key==='ArrowLeft' || event.key==='ArrowRight') {event.preventDefault();cycle(event.key==='ArrowLeft'?-1:1);}
});
load();
