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
