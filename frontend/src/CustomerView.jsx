import React, { useEffect, useRef, useState } from 'react';
import './customer-view.css';

const statusLabels = {
  NEW: 'Request received', IN_PROGRESS: 'In progress',
  WAITING_FOR_CUSTOMER: 'Your reply is needed',
  WAITING_FOR_SPECIALIST: 'Personal review', RESOLVED: 'Resolved', CLOSED: 'Closed',
};
const statusHelp = {
  NEW: 'We have received your request.',
  IN_PROGRESS: 'We are reviewing your request and the documents provided.',
  WAITING_FOR_CUSTOMER: 'Please provide the details requested in our latest message.',
  WAITING_FOR_SPECIALIST: 'Our service team is reviewing your request personally.',
  RESOLVED: 'You can find our reply in your message history.',
  CLOSED: 'You can find the previous conversation in your message history.',
};

export default function CustomerView({ caseDetail, busy = false, onReply, onUpload, error = '' }) {
  const caseId = caseDetail?.caseId || caseDetail?.id;
  const [draft, setDraft] = useState('42.00 EUR');
  const [attachmentIds, setAttachmentIds] = useState([]);
  const [localError, setLocalError] = useState('');
  const [uploadFailed, setUploadFailed] = useState(false);
  const [working, setWorking] = useState(false);
  const pending = useRef(false);
  const generation = useRef(0);
  useEffect(() => {
    generation.current++;
    setDraft('42.00 EUR'); setAttachmentIds([]); setLocalError(''); setUploadFailed(false);
  }, [caseId]);

  async function upload(file) {
    if (!file || pending.current || busy) return;
    pending.current = true; setWorking(true); setLocalError('');
    const token = generation.current;
    try {
      const result = await onUpload(file);
      if (!result?.attachmentId) throw new Error('The receipt could not be saved. Please upload it again.');
      if (token === generation.current) {
        setAttachmentIds(ids => [...new Set([...ids, result.attachmentId])]);
        setUploadFailed(false);
      }
    } catch (e) {
      if (token === generation.current) { setLocalError(e.message || 'The upload failed.'); setUploadFailed(true); }
    } finally { pending.current = false; setWorking(false); }
  }

  async function submit(event) {
    event.preventDefault();
    if (pending.current || busy || uploadFailed || !draft.trim()) return;
    pending.current = true; setWorking(true); setLocalError('');
    const token = generation.current;
    try {
      const succeeded = await onReply(draft.trim(), attachmentIds);
      if (succeeded === false) throw new Error('Your reply could not be fully processed. Please check the error message.');
      if (token === generation.current) { setDraft(''); setAttachmentIds([]); }
    } catch (e) {
      if (token === generation.current) setLocalError(e.message || 'Your reply could not be sent. Please try again.');
    } finally { pending.current = false; setWorking(false); }
  }

  if (!caseDetail) return <main className="customer-view"><p role="status">Loading your request …</p></main>;
  const messages = caseDetail.messages || caseDetail.snapshot?.messages || [];
  const attachments = caseDetail.attachments || caseDetail.snapshot?.attachments || [];
  const positions = caseDetail.financialPositions || [];
  const disabled = busy || working;
  return <main className="customer-view" aria-label="Customer view">
    <section className="customer-welcome">
      <div className="eyebrow">MY CONDOR SERVICE</div>
      <h1>Your request. All in one place.</h1>
      <p>Messages, documents and the current status of your request.</p>
      <div className="customer-demo-label">Demo · Synthetic customer data · Messages and payments simulated</div>
    </section>
    <div className="customer-layout">
      <section className="customer-conversation" aria-labelledby="customer-case-title">
        <div className="customer-case-heading"><small>CASE {caseId}</small><h2 id="customer-case-title">{caseDetail.subject}</h2></div>
        <h3>Your messages</h3>
        {messages.length ? messages.map(message => <article key={message.messageId} className={`customer-message ${message.direction === 'OUTBOUND' ? 'customer-service-message' : ''}`}>
          <small>{message.direction === 'OUTBOUND' ? 'CONDOR SERVICE · SIMULATED MESSAGE' : 'YOUR MESSAGE'}</small>
          <p>{message.body}</p>
        </article>) : <p>No messages yet.</p>}
        <form className="customer-reply" onSubmit={submit}>
          <label htmlFor="customer-reply">Your reply</label>
          <textarea id="customer-reply" value={draft} disabled={disabled} onChange={event => setDraft(event.target.value)} />
          <div className="customer-upload-actions">
            <button type="button" disabled={disabled} onClick={() => upload(new File(['SYNTHETIC DEMO RECEIPT\nMeal during flight disruption\nTotal: 42.00 EUR\nNo real purchase or payment.\n'], 'demo-receipt-42-eur.txt', { type: 'text/plain' }))}>Add demo receipt · EUR 42.00</button>
            <label className="customer-file-label">Choose a synthetic receipt
              <input type="file" disabled={disabled} onChange={event => { const file = event.target.files?.[0]; event.target.value = ''; upload(file); }} />
            </label>
          </div>
          {attachmentIds.length > 0 && <p className="customer-upload-confirmation" role="status">{attachmentIds.length} receipt(s) saved for your reply.</p>}
          {(localError || error) && <p className="customer-error" role="alert">{localError || error}</p>}
          {uploadFailed && <button type="button" disabled={disabled} onClick={() => { setUploadFailed(false); setLocalError(''); }}>Continue without another upload</button>}
          <button className="primary" type="submit" disabled={disabled || uploadFailed || !draft.trim()}>{disabled ? 'Processing …' : 'Send reply'}</button>
          <small className="customer-send-note">Your reply stays linked to this case. No real email is sent.</small>
        </form>
      </section>
      <aside className="customer-summary">
        <section className="customer-status-card"><div className="eyebrow">CURRENT STATUS</div><strong className={`badge ${caseDetail.status}`}>{statusLabels[caseDetail.status] || 'In progress'}</strong><p>{statusHelp[caseDetail.status] || statusHelp.IN_PROGRESS}</p></section>
        {positions.length > 0 && <section className="customer-payment"><div className="eyebrow">REIMBURSEMENT · SIMULATION</div>{positions.map((position, index) => <strong key={index}>{new Intl.NumberFormat('en-GB', { style: 'currency', currency: position.currency }).format(position.amountMinor / 100)}</strong>)}<p>The reimbursement was simulated for this demo. No real money is transferred.</p></section>}
        <section className="customer-documents"><h3>Your documents</h3>{attachments.length ? attachments.map(attachment => <a key={attachment.attachmentId} href={`/api/cases/${encodeURIComponent(caseId)}/attachments/${encodeURIComponent(attachment.attachmentId)}`} target="_blank" rel="noreferrer">↗ {attachment.filename}</a>) : <p>No documents yet.</p>}</section>
      </aside>
    </div>
  </main>;
}
