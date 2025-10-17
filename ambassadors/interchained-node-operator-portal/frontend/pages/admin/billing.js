import { useEffect, useState } from 'react';
import AdminShell from '../../components/layout/AdminShell';
import { useAuth } from '../../context/AuthContext';
import api from '../../lib/api';

const PLAN_COPY = {
  launch: {
    headline: 'Launch Tier',
    description: 'Optimised for early ecosystem bootstrapping and small node fleets.',
    perks: ['5 included nodes', 'Standard analytics', 'Community support'],
  },
  growth: {
    headline: 'Growth Tier',
    description: 'Adds scaling capabilities and advanced monitoring for expanding teams.',
    perks: ['20 included nodes', 'Performance reporting', 'Priority support'],
  },
  enterprise: {
    headline: 'Enterprise Tier',
    description: 'Unlimited scale, compliance-ready reporting and dedicated TAM services.',
    perks: ['100 included nodes', 'AI uptime forecasts', 'Dedicated success manager'],
  },
};

export default function BillingPage() {
  const { token, user } = useAuth();
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!token || !user) return;
    async function load() {
      try {
        const data = await api.billingSummary(token, user.organization_id);
        setSummary(data);
      } catch (err) {
        setError('Unable to load billing summary.');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [token, user]);

  return (
    <AdminShell title="Billing & Usage">
      {loading ? (
        <p className="text-slate-400">Calculating utilisation…</p>
      ) : error ? (
        <p className="rounded-xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">{error}</p>
      ) : summary ? (
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
          <section className="rounded-2xl border border-slate-900/70 bg-slate-950/60 p-6 shadow-lg shadow-black/30">
            <h2 className="text-lg font-semibold text-slate-100">Plan Overview</h2>
            <p className="mt-2 text-sm text-slate-400">Monthly recurring charge calculated on active node usage.</p>
            <div className="mt-6 space-y-3 text-sm text-slate-300">
              <div className="flex items-center justify-between">
                <span>Current Plan</span>
                <span className="font-semibold text-emerald-300">{summary.plan}</span>
              </div>
              <div className="flex items-center justify-between">
                <span>Monthly Cost</span>
                <span className="font-semibold text-slate-100">${summary.monthly_cost.toFixed(2)}</span>
              </div>
              <div className="flex items-center justify-between">
                <span>Included Nodes</span>
                <span>{summary.included_nodes}</span>
              </div>
              <div className="flex items-center justify-between">
                <span>Current Month Usage</span>
                <span>{summary.current_month_usage}</span>
              </div>
              <div className="flex items-center justify-between">
                <span>Additional Node Price</span>
                <span>${summary.additional_node_price.toFixed(2)}</span>
              </div>
            </div>
          </section>
          <section className="rounded-2xl border border-slate-900/70 bg-slate-950/60 p-6 shadow-lg shadow-black/30">
            <h2 className="text-lg font-semibold text-slate-100">Plan Benefits</h2>
            <div className="mt-4 space-y-4 text-sm text-slate-300">
              {(PLAN_COPY[summary.plan] || PLAN_COPY.launch).perks.map((perk) => (
                <div key={perk} className="flex items-start gap-3">
                  <span className="mt-1 inline-block h-2 w-2 rounded-full bg-emerald-400" />
                  <span>{perk}</span>
                </div>
              ))}
            </div>
          </section>
        </div>
      ) : (
        <p className="text-slate-400">No billing data available.</p>
      )}
    </AdminShell>
  );
}
