import { useEffect, useState } from 'react';
import AdminShell from '../../components/layout/AdminShell';
import { useAuth } from '../../context/AuthContext';
import api from '../../lib/api';

const ROLE_OPTIONS = [
  { value: 'super_admin', label: 'Super Admin' },
  { value: 'org_admin', label: 'Org Admin' },
  { value: 'operator', label: 'Operator' },
  { value: 'auditor', label: 'Auditor' },
];

export default function TeamAccessPage() {
  const { token, user } = useAuth();
  const [members, setMembers] = useState([]);
  const [invites, setInvites] = useState([]);
  const [role, setRole] = useState('operator');
  const [expiresIn, setExpiresIn] = useState(72);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const isSuperAdmin = user?.role === 'super_admin';

  useEffect(() => {
    if (!token || !user) return;
    async function load() {
      try {
        const [membersRes, inviteRes] = await Promise.all([
          api.listUsers(token, user.organization_id),
          api.listInvites(token),
        ]);
        setMembers(membersRes || []);
        setInvites(inviteRes || []);
      } catch (err) {
        setError('Unable to load team roster.');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [token, user]);

  const refreshInvites = async () => {
    if (!token) return;
    const inviteRes = await api.listInvites(token);
    setInvites(inviteRes || []);
  };

  const refreshMembers = async () => {
    if (!token || !user) return;
    const membersRes = await api.listUsers(token, user.organization_id);
    setMembers(membersRes || []);
  };

  const createInvite = async (event) => {
    event.preventDefault();
    setMessage('');
    setError('');
    try {
      const invite = await api.createInvite(token, {
        organization_id: user.organization_id,
        role,
        expires_in_hours: expiresIn,
      });
      setMessage(`Invite generated: ${invite.code}`);
      await refreshInvites();
    } catch (err) {
      setError(err.message || 'Failed to create invite.');
    }
  };

  const promoteUser = async (member, newRole) => {
    setError('');
    try {
      await api.updateUserRole(token, member.email, newRole);
      await refreshMembers();
    } catch (err) {
      setError('Unable to update user role.');
    }
  };

  const deactivateUser = async (member) => {
    setError('');
    try {
      await api.deactivateUser(token, member.email);
      await refreshMembers();
    } catch (err) {
      setError('Unable to deactivate user.');
    }
  };

  return (
    <AdminShell title="Team Access">
      {loading ? (
        <p className="text-slate-400">Loading access roster…</p>
      ) : (
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
          <section className="rounded-2xl border border-slate-900/70 bg-slate-950/60 p-6 shadow-lg shadow-black/30">
            <h2 className="text-lg font-semibold text-slate-100">Members</h2>
            <div className="mt-4 space-y-3 text-sm text-slate-300">
              {members.map((member) => (
                <div key={member.email} className="rounded-xl border border-slate-900/60 bg-slate-900/40 px-4 py-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-semibold text-slate-100">{member.full_name || member.email}</div>
                      <div className="text-xs uppercase tracking-[0.3em] text-slate-500">{member.role}</div>
                      <div className="text-xs text-slate-500">Joined {new Date(member.created_at).toLocaleString()}</div>
                    </div>
                    <div className="flex flex-col items-end gap-2">
                      <select
                        value={member.role}
                        onChange={(event) => promoteUser(member, event.target.value)}
                        className="rounded-lg border border-slate-800 bg-slate-950 px-2 py-1 text-xs uppercase tracking-widest text-slate-200"
                        disabled={!isSuperAdmin && member.email === user.email}
                      >
                        {ROLE_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                      {member.email !== user.email && (
                        <button
                          onClick={() => deactivateUser(member)}
                          className="text-xs uppercase tracking-[0.3em] text-rose-300 hover:text-rose-200"
                        >
                          Deactivate
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="rounded-2xl border border-slate-900/70 bg-slate-950/60 p-6 shadow-lg shadow-black/30">
            <h2 className="text-lg font-semibold text-slate-100">Invite Collaborators</h2>
            <p className="mt-2 text-sm text-slate-400">
              Generate time-bound invites to onboard additional operators or auditors. Invites expire automatically and can be
              rescinded by regenerating the link.
            </p>
            <form onSubmit={createInvite} className="mt-6 space-y-4">
              <label className="block text-xs uppercase tracking-[0.3em] text-slate-500">
                Role
                <select
                  value={role}
                  onChange={(event) => setRole(event.target.value)}
                  className="mt-2 w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-slate-200"
                >
                  {ROLE_OPTIONS.filter((option) => option.value !== 'super_admin' || isSuperAdmin).map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-xs uppercase tracking-[0.3em] text-slate-500">
                Expiry (hours)
                <input
                  type="number"
                  value={expiresIn}
                  min={1}
                  max={336}
                  onChange={(event) => setExpiresIn(Number(event.target.value))}
                  className="mt-2 w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-slate-200"
                />
              </label>
              <button
                type="submit"
                className="w-full rounded-xl bg-gradient-to-r from-cyan-500/80 to-blue-500/60 py-3 text-sm font-semibold uppercase tracking-[0.3em] text-slate-950 transition hover:from-cyan-400 hover:to-blue-400"
              >
                Generate Invite
              </button>
            </form>
            <div className="mt-6 space-y-3 text-xs text-slate-400">
              <h3 className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">Active Invites</h3>
              {invites.length ? (
                invites.map((invite) => (
                  <div key={invite.code} className="rounded-lg border border-slate-900/60 bg-slate-900/40 px-4 py-3">
                    <div className="flex items-center justify-between">
                      <span className="text-slate-200">{invite.code}</span>
                      <span className="uppercase tracking-[0.3em] text-slate-500">{invite.role}</span>
                    </div>
                    <div className="mt-1 text-[10px] uppercase tracking-[0.3em] text-slate-500">
                      Expires {new Date(invite.expires_at).toLocaleString()}
                    </div>
                  </div>
                ))
              ) : (
                <p>No active invites.</p>
              )}
            </div>
            {message && <p className="mt-4 text-xs text-emerald-300">{message}</p>}
            {error && <p className="mt-4 text-xs text-rose-300">{error}</p>}
          </section>
        </div>
      )}
    </AdminShell>
  );
}
