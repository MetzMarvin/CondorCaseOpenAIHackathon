// Shared API contracts stay canonical; this adapter only prepares display fields.
export function caseForView(value) {
  if (!value || !value.caseId) return value;
  const snapshot = value.snapshot;
  const runs = value.runResults || [];
  const latest = runs.at(-1)?.proposedAction;
  return {
    ...value, id: value.caseId, caseVersion: value.version,
    messages: (snapshot?.messages || []).map(message => ({ ...message,
      direction: message.sender === 'condor-service@example.com' ? 'OUTBOUND' : 'INBOUND' })),
    attachments: snapshot?.attachments || [],
    facts: (snapshot?.knownFacts || []).map(fact => `${fact.name}: ${typeof fact.value === 'object' ? JSON.stringify(fact.value) : fact.value}`),
    missingInformation: (snapshot?.missingInformation || []).map(fact => fact.name),
    sourceReferences: (value.sourceReferences || []).map(source => ({ ...source, id: source.sourceId, title: source.sourceId })),
    handoff: latest?.type === 'HANDOFF' ? latest.payload : null,
    financialPositions: [...new Map((value.history || []).filter(event => event.type === 'action.applied' && event.data?.actionId).map(event => [event.data.actionId, event.data.financialPositions || []])).values()].flat(),
  };
}
export async function api(path, body) {
  const response = await fetch(`/api${path}`, body === undefined ? {} : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  let data;
  try { data = await response.json(); } catch { data = {}; }
  if (!response.ok) {
    const error = new Error(data.message || data.detail?.message || (response.status === 422 ? 'Please check your input.' : 'Request failed.'));
    error.status = response.status;
    error.code = data.code || data.detail?.code;
    throw error;
  }
  if (Array.isArray(data)) return data.map(caseForView);
  if (data.case) return { ...data, case: caseForView(data.case) };
  return caseForView(data);
}
export const key = () => crypto.randomUUID();
