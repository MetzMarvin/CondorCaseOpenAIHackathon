import React, { useEffect, useRef, useState } from 'react';
import './portal.css';

const STATUS = {
  NEW: 'Received', IN_PROGRESS: 'Ready for review', WAITING_FOR_CUSTOMER: 'Awaiting your reply',
  WAITING_FOR_SPECIALIST: 'With the service team', RESOLVED: 'Resolved', CLOSED: 'Closed',
};

async function api(url, options) {
  let response;
  try { response = await fetch(url, options); }
  catch { throw new Error('The service is currently unavailable. Your draft has been kept. Please try again.'); }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error?.message || 'Your request could not be processed. Please try again.');
  return data;
}

function useResource(url, revision = 0) {
  const [state, setState] = useState({ loading: true, data: null, error: '' });
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    setState(previous => ({ loading: true, data: previous.data, error: '' }));
    api(url).then(data => { if (active) setState({ loading: false, data, error: '' }); })
      .catch(error => { if (active) setState(previous => ({ loading: false, data: previous.data, error: error.message })); });
    return () => { active = false; };
  }, [url, revision, retry]);
  return { ...state, retry: () => setRetry(n => n + 1) };
}

function Link({ to, children, ...props }) {
  return <a href={to} {...props} onClick={event => {
    if (event.button || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault(); window.history.pushState({}, '', to); window.dispatchEvent(new PopStateEvent('popstate')); window.scrollTo(0, 0);
  }}>{children}</a>;
}

function Badge({ status }) { return <span className={`badge status-${status}`}>{STATUS[status] || status}</span>; }
function ErrorBox({ error, retry }) { return <div className="error" role="alert">{error}{retry && <button className="text-button" onClick={retry}>Try again</button>}</div>; }
function Loading() { return <p className="loading" role="status">Loading your case …</p>; }
function date(value) { return new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)); }

function MessageForm({ caseData, onSaved }) {
  const initialSender = caseData?.messages.find(m => m.direction === 'INBOUND')?.sender || '';
  const initialSubject = caseData ? `Additional information: ${caseData.subject}` : '';
  const [values, setValues] = useState({ sender: initialSender, subject: initialSubject, body: '' });
  const [files, setFiles] = useState([]);
  const [fileRevision, setFileRevision] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [receipt, setReceipt] = useState(null);
  const attempt = useRef(null);
  const fileInput = useRef(null);

  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    setError('');
    if (!values.subject.trim() || !values.body.trim()) { setError('Please enter a subject and a message.'); return; }
    if (files.length > 5 || files.some(file => file.size > 10 * 1024 * 1024)) {
      setError('Please select up to five files, each no larger than 10 MB.'); return;
    }
    const metadata = { ...values, channel: 'PORTAL', ...(caseData ? { caseId: caseData.caseId } : {}) };
    const signature = JSON.stringify({ metadata, fileRevision });
    if (attempt.current?.signature !== signature) attempt.current = { signature, id: crypto.randomUUID() };
    metadata.messageId = attempt.current.id;
    const form = new FormData();
    form.append('metadata', JSON.stringify(metadata));
    files.forEach(file => form.append('files', file));
    setBusy(true);
    try {
      const result = await api('/api/inbound/messages', files.length
        ? { method: 'POST', body: form }
        : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(metadata) });
      setReceipt(result);
      onSaved?.(result);
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  if (receipt) return <div className="success" role="status">
    <span className="success-icon" aria-hidden="true">✓</span>
    <p className="eyebrow">Message received</p>
    <h2>{caseData ? 'Your update has arrived.' : 'Your claim has arrived.'}</h2>
    <p>Your message and documents have been added to your case. Keep your case link to check its status or add more information.</p>
    <div className="receipt"><span>Your case reference</span><strong>{receipt.caseId}</strong></div>
    <div className="button-row"><Link className="button primary" to={receipt.customerCaseUrl}>View case <span aria-hidden="true">↗</span></Link>
      <button className="button secondary" onClick={() => {
        setReceipt(null); setValues({ sender: initialSender, subject: initialSubject, body: '' });
        setFiles([]); setFileRevision(n => n + 1); attempt.current = null;
      }}>{caseData ? 'Another message' : 'New claim'}</button></div>
  </div>;

  return <form onSubmit={submit}>
    <fieldset disabled={busy}>
      <div className="field"><label htmlFor="sender">Your email address <span>*</span></label>
        <input id="sender" name="sender" type="email" required maxLength={254} autoComplete="email" placeholder="name@example.com" value={values.sender} onChange={e => setValues({ ...values, sender: e.target.value })} />
      </div>
      <div className="field"><label htmlFor="subject">Subject <span>*</span></label>
        <input id="subject" name="subject" required maxLength={200} placeholder="How can we help?" value={values.subject} onChange={e => setValues({ ...values, subject: e.target.value })} />
      </div>
      <div className="field"><label htmlFor="body">{caseData ? 'Your update' : 'Your message'} <span>*</span></label>
        <textarea id="body" name="body" required maxLength={20000} rows={6} placeholder="Tell us what happened. Include flight details or a booking reference if you have them." value={values.body} onChange={e => setValues({ ...values, body: e.target.value })} />
        <small>Missing some details? You can add them later.</small>
      </div>
      <div className="upload"><label htmlFor="files"><span className="upload-icon" aria-hidden="true">↥</span><strong>Add supporting documents</strong><span>Optional · PDF, JPEG or PNG · up to 5 files, 10 MB each</span></label>
        <input ref={fileInput} id="files" name="files" type="file" multiple accept=".pdf,.jpg,.jpeg,.png" onChange={e => { setFiles([...e.target.files]); setFileRevision(n => n + 1); }} />
        {files.length > 0 && <ul className="file-list">{files.map((file, i) => <li key={`${file.name}-${i}`}><span>{file.name}</span><small>{Math.max(1, Math.round(file.size / 1024))} KB</small></li>)}</ul>}
        {files.length > 0 && <button className="text-button" type="button" onClick={() => { setFiles([]); fileInput.current.value = ''; setFileRevision(n => n + 1); }}>Clear selection</button>}
      </div>
      {error && <ErrorBox error={error} />}
      <div className="form-footer"><small>* Required fields</small><button className="button primary" type="submit">{busy ? 'Saving …' : caseData ? 'Send update' : 'Submit claim'} <span aria-hidden="true">→</span></button></div>
    </fieldset>
  </form>;
}

function Portal() {
  return <><div className="page-heading"><p className="eyebrow">Here to help</p><h1>Tell us how we can help.</h1><p>Tell us what happened. Keep your messages and supporting documents together in one place.</p></div>
    <div className="two-column"><section className="card"><div className="section-heading"><span className="step-number">01</span><div><h2>Submit a claim</h2><p>A short message is all you need to get started.</p></div></div><MessageForm /></section>
      <aside><div className="side-card"><h2>What happens next</h2><ol className="steps"><li><strong>Send your claim</strong><p>Tell us about your experience in your own words.</p></li><li><strong>Keep your case link</strong><p>Use your link to see your case status and messages.</p></li><li><strong>Add details anytime</strong><p>Send supporting documents and extra details whenever you are ready.</p></li></ol></div>
        <div className="demo-note"><span className="eyebrow">Hackathon demo</span><p>Please use fictional data only. Messages and claims in this demo are simulated.</p></div></aside>
    </div></>;
}

function Conversation({ data }) {
  return <div className="conversation">{data.messages.map(message => <article key={message.messageId} className={`message ${message.direction === 'OUTBOUND' ? 'outbound' : ''}`}>
    <div className="message-heading"><strong>{message.direction === 'OUTBOUND' ? 'Condor service team · Demo' : message.sender}</strong><time dateTime={message.timestamp}>{date(message.timestamp)}</time></div>
    <div className="message-tags"><span>{message.channel === 'EMAIL' ? 'Email' : 'Customer portal'}</span>{message.storedExample && <span>Stored example</span>}</div>
    <h3>{message.subject}</h3><p className="message-body">{message.body}</p>
    {message.attachments.length > 0 && <ul className="attachments">{message.attachments.map(file => <li key={file.attachmentId}><a href={file.url} download>↓ {file.filename}</a><small>{Math.max(1, Math.round(file.size / 1024))} KB</small></li>)}</ul>}
  </article>)}</div>;
}

function CasePage({ caseId }) {
  const [revision, setRevision] = useState(0);
  const state = useResource(`/api/portal/cases/${encodeURIComponent(caseId)}`, revision);
  if (state.loading && !state.data) return <Loading />;
  if (state.error && !state.data) return <ErrorBox error={state.error} retry={state.retry} />;
  const data = state.data;
  return <><div className="page-heading case-heading"><Link className="back-link" to="/portal">← Back to the portal</Link><p className="eyebrow">Your case</p><h1>{data.subject}</h1><div className="case-meta"><Badge status={data.status} /><span className="case-reference">{data.caseId}</span></div></div>
    <div className="two-column"><div>{state.error && <ErrorBox error={state.error} retry={state.retry} />}<section className="card conversation-card"><div className="section-heading"><div><h2>Your messages</h2><p>Your conversation, together in one place.</p></div><button className="text-button" onClick={() => setRevision(n => n + 1)}>Refresh</button></div><Conversation data={data} /></section>
      <section className="card reply-card"><h2>Add an update</h2><p className="muted">A new message or a missing document? Add it here.</p><MessageForm key={caseId} caseData={data} onSaved={() => setRevision(n => n + 1)} /></section></div>
      <aside><div className="side-card"><h2>Your direct connection</h2><p>Keep this link to return to your case whenever you need to.</p><p className="muted">Last updated<br /><strong>{date(data.updatedAt)}</strong></p></div><div className="demo-note"><p>Demo case link · Use fictional information only. Keep your link to return to this conversation.</p></div></aside>
    </div></>;
}

export default function CustomerPortal() {
  const [path, setPath] = useState(window.location.pathname);
  useEffect(() => {
    const handler = () => setPath(window.location.pathname);
    window.addEventListener('popstate', handler);
    return () => window.removeEventListener('popstate', handler);
  }, []);
  const match = path.match(/^\/portal\/cases\/([A-Za-z0-9_-]+)$/);
  const page = match ? <CasePage key={match[1]} caseId={match[1]} />
    : path === '/' || path === '/portal' ? <Portal />
    : <section className="card"><h1>Page not found</h1><p>This page is not part of the customer portal.</p><Link to="/portal">Back to the portal</Link></section>;
  return <div className="customer-app">
    <a className="skip-link" href="#main">Skip to content</a>
    <header className="topbar"><div className="header-inner">
      <Link to="/portal" className="brand" aria-label="Condor Care Hub home"><span className="brand-mark" aria-hidden="true">≋</span><span>condor <span className="brand-light">Care Hub</span></span></Link>
      <span className="header-meta">CUSTOMER CARE</span>
      <nav aria-label="Customer navigation"><Link to="/portal" aria-current={path === '/portal' || path === '/' ? 'page' : undefined}>Submit a claim</Link></nav>
    </div></header>
    <div className="controlbar"><div className="controlbar-inner"><strong>Customer portal</strong><span>Demo · Fictional information only</span></div></div>
    <main id="main" key={path}>{page}</main>
    <footer><span>Condor Care Hub · Customer care</span><span>Claims and messages are simulated.</span></footer>
  </div>;
}
