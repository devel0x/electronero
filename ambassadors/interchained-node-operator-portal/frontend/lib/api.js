const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000/api/v1';

async function request(path, { method = 'GET', body, token } = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(errorText || 'Request failed');
  }
  if (res.status === 204) {
    return null;
  }
  return res.json();
}

function parseFilenameFromDisposition(disposition) {
  if (!disposition) return null;
  const match = disposition.match(/filename="?([^";]+)"?/i);
  return match ? match[1] : null;
}

export const api = {
  login: (payload) => request('/users/login', { method: 'POST', body: payload }),
  register: (payload) => request('/users/register', { method: 'POST', body: payload }),
  me: (token) => request('/users/me', { token }),
  listNodes: (token) => request('/nodes', { token }),
  createNode: (token, payload) => request('/nodes', { method: 'POST', body: payload, token }),
  updateNode: (token, nodeId, payload) => request(`/nodes/${nodeId}`, { method: 'PATCH', body: payload, token }),
  dashboardMetrics: (token) => request('/analytics/dashboard', { token }),
  billingSummary: (token, orgId) => request(`/analytics/billing/${orgId}`, { token }),
  rewardSummary: (token) => request('/rewards/today', { token }),
  rewardHistory: (token) => request('/rewards/history', { token }),
  topUpRewardPool: (token, amount) => request('/rewards/pool/top-up', { method: 'POST', body: { amount }, token }),
  awardNodeRewards: (token, payload) => request('/rewards/award', { method: 'POST', body: payload, token }),
  exportRewardsCsv: async (token, params = {}) => {
    const search = new URLSearchParams();
    if (params.date) search.set('date', params.date);
    if (params.organizationId) search.set('organizationId', params.organizationId);
    const query = search.toString();
    const url = `${API_BASE}/rewards/export${query ? `?${query}` : ''}`;
    const headers = {};
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    const res = await fetch(url, { headers });
    if (!res.ok) {
      const errorText = await res.text();
      throw new Error(errorText || 'Export failed');
    }
    const blob = await res.blob();
    const filename = parseFilenameFromDisposition(res.headers.get('Content-Disposition')) ||
      `reward-export-${params.date || new Date().toISOString().slice(0, 10)}.csv`;
    return { blob, filename };
  },
  organizations: (token) => request('/admin/organizations', { token }),
  createOrganization: (token, payload) => request('/admin/organizations', { method: 'POST', body: payload, token }),
  updateOrganization: (token, orgId, payload) => request(`/admin/organizations/${orgId}`, { method: 'PATCH', body: payload, token }),
  listUsers: (token, orgId) => request(`/admin/organizations/${orgId}/users`, { token }),
  createUser: (token, payload) => request('/admin/users', { method: 'POST', body: payload, token }),
  updateUserRole: (token, email, role) => request(`/admin/users/${encodeURIComponent(email)}/role?role=${role}`, { method: 'POST', token }),
  deactivateUser: (token, email) => request(`/admin/users/${encodeURIComponent(email)}/deactivate`, { method: 'POST', token }),
  createInvite: (token, payload) => request('/users/invites', { method: 'POST', body: payload, token }),
  listInvites: (token) => request('/users/invites', { token }),
  auditLog: (token, limit = 100) => request(`/audit?limit=${limit}`, { token }),
};

export default api;
