import { useEffect, useMemo, useState } from 'react';
import AdminShell from '../components/layout/AdminShell';
import NodeTable from '../components/NodeTable';
import MetricCard from '../components/cards/MetricCard';
import UptimeTrend from '../components/charts/UptimeTrend';
import { useAuth } from '../context/AuthContext';
import api from '../lib/api';

export default function Dashboard() {
  const { token } = useAuth();
  const [metrics, setMetrics] = useState(null);
  const [nodes, setNodes] = useState([]);
  const [rewardSummary, setRewardSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!token) return;
    async function load() {
      try {
        const [metricsRes, nodesRes, rewardRes] = await Promise.all([
          api.dashboardMetrics(token).catch(() => null),
          api.listNodes(token).catch(() => []),
          api.rewardSummary(token).catch(() => ({ rewards: {} })),
        ]);
        setMetrics(metricsRes);
        setNodes(nodesRes || []);
        setRewardSummary(rewardRes);
      } catch (err) {
        setError('Unable to load dashboard data.');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [token]);

  const rewardTotal = useMemo(() => {
    if (!rewardSummary?.rewards) return 0;
    return Object.values(rewardSummary.rewards).reduce((acc, value) => acc + Number(value), 0);
  }, [rewardSummary]);

  return (
    <AdminShell title="Executive Overview">
      {loading ? (
        <p className="text-slate-400">Synthesising live telemetry…</p>
      ) : error ? (
        <p className="rounded-xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">{error}</p>
      ) : (
        <div className="space-y-8">
          <div className="grid grid-cols-1 gap-6 md:grid-cols-4">
            <MetricCard
              label="Active Nodes"
              value={metrics?.total_active_nodes ?? nodes.length}
              helper="Nodes responding to orchestration"
            />
            <MetricCard
              label="Avg Uptime"
              value={`${((metrics?.avg_uptime || 0) * 100).toFixed(2)}%`}
              helper="Weighted across fleet"
              tone="amber"
            />
            <MetricCard
              label="Flagged Nodes"
              value={metrics?.flagged_nodes ?? 0}
              helper="Requires operator attention"
              tone="fuchsia"
            />
            <MetricCard
              label="Rewards Today"
              value={`${rewardTotal.toFixed(4)} ITC`}
              helper="Distributed during last cycle"
              tone="slate"
            />
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <div className="rounded-2xl border border-slate-900/70 bg-slate-950/60 p-6 shadow-lg shadow-black/30 lg:col-span-2">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-lg font-semibold text-slate-100">Fleet Uptime</h2>
                <span className="text-xs uppercase tracking-[0.3em] text-slate-500">Last 7 days</span>
              </div>
              <UptimeTrend data={metrics?.uptime_timeseries || []} />
            </div>
            <div className="rounded-2xl border border-slate-900/70 bg-slate-950/60 p-6 shadow-lg shadow-black/30">
              <h2 className="text-lg font-semibold text-slate-100">Plan Mix</h2>
              <div className="mt-4 space-y-3 text-sm">
                {metrics?.plan_distribution && Object.keys(metrics.plan_distribution).length ? (
                  Object.entries(metrics.plan_distribution).map(([plan, count]) => (
                    <div key={plan} className="flex items-center justify-between">
                      <span className="uppercase tracking-wide text-slate-400">{plan}</span>
                      <span className="text-slate-200">{count}</span>
                    </div>
                  ))
                ) : (
                  <p className="text-slate-500">No organisations tracked yet.</p>
                )}
              </div>
            </div>
          </div>

          <section>
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-slate-100">Node Health Snapshot</h2>
              <span className="text-xs text-slate-500">Showing {nodes.length} nodes</span>
            </div>
            <NodeTable nodes={nodes} />
          </section>
        </div>
      )}
    </AdminShell>
  );
}
