import { useEffect, useState } from 'react';
import AdminShell from '../../components/layout/AdminShell';
import OrganizationTable from '../../components/tables/OrganizationTable';
import { useAuth } from '../../context/AuthContext';
import api from '../../lib/api';

const PLANS = [
  { value: 'launch', label: 'Launch' },
  { value: 'growth', label: 'Growth' },
  { value: 'enterprise', label: 'Enterprise' },
];

export default function OrganizationsPage() {
  const { token, user } = useAuth();
  const [organizations, setOrganizations] = useState([]);
  const [form, setForm] = useState({ name: '', billing_email: '', plan: 'growth' });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const isSuperAdmin = user?.role === 'super_admin';

  useEffect(() => {
    if (!token || !isSuperAdmin) {
      setLoading(false);
      return;
    }
    async function load() {
      try {
        const data = await api.organizations(token);
        setOrganizations(data || []);
      } catch (err) {
        setError('Unable to load organizations.');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [token, isSuperAdmin]);

  const handleChange = (event) => {
    const { name, value } = event.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const createOrganization = async (event) => {
    event.preventDefault();
    setMessage('');
    setError('');
    try {
      const created = await api.createOrganization(token, form);
      setOrganizations((prev) => [created, ...prev]);
      setForm({ name: '', billing_email: '', plan: 'growth' });
      setMessage(`Organization ${created.name} created.`);
    } catch (err) {
      setError(err.message || 'Failed to create organization.');
    }
  };

  if (!isSuperAdmin) {
    return (
      <AdminShell title="Organizations">
        <p className="text-slate-400">Super admin permissions required.</p>
      </AdminShell>
    );
  }

  return (
    <AdminShell title="Organizations">
      {loading ? (
        <p className="text-slate-400">Loading tenants…</p>
      ) : (
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
          <section className="lg:col-span-2 space-y-4">
            <h2 className="text-lg font-semibold text-slate-100">Tenant Directory</h2>
            <OrganizationTable organizations={organizations} />
          </section>
          <section className="rounded-2xl border border-slate-900/70 bg-slate-950/60 p-6 shadow-lg shadow-black/30">
            <h2 className="text-lg font-semibold text-slate-100">Provision Organization</h2>
            <form onSubmit={createOrganization} className="mt-6 space-y-4">
              <label className="block text-xs uppercase tracking-[0.3em] text-slate-500">
                Name
                <input
                  name="name"
                  value={form.name}
                  onChange={handleChange}
                  required
                  className="mt-2 w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-slate-200"
                />
              </label>
              <label className="block text-xs uppercase tracking-[0.3em] text-slate-500">
                Billing Email
                <input
                  name="billing_email"
                  type="email"
                  value={form.billing_email}
                  onChange={handleChange}
                  required
                  className="mt-2 w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-slate-200"
                />
              </label>
              <label className="block text-xs uppercase tracking-[0.3em] text-slate-500">
                Plan
                <select
                  name="plan"
                  value={form.plan}
                  onChange={handleChange}
                  className="mt-2 w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-slate-200"
                >
                  {PLANS.map((plan) => (
                    <option key={plan.value} value={plan.value}>
                      {plan.label}
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="submit"
                className="w-full rounded-xl bg-gradient-to-r from-emerald-500/80 to-cyan-500/60 py-3 text-sm font-semibold uppercase tracking-[0.3em] text-slate-950 transition hover:from-emerald-400 hover:to-cyan-400"
              >
                Create Organization
              </button>
            </form>
            {message && <p className="mt-4 text-xs text-emerald-300">{message}</p>}
            {error && <p className="mt-4 text-xs text-rose-300">{error}</p>}
          </section>
        </div>
      )}
    </AdminShell>
  );
}
