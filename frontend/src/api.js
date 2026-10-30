export async function api(path, body) {
  const response = await fetch(`/api${path}`, body === undefined ? {} : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(data.detail?.message || (response.status === 422 ? 'Please check your input.' : 'Request failed.'));
    error.status = response.status;
    throw error;
  }
  return data;
}
export const key = () => crypto.randomUUID();
