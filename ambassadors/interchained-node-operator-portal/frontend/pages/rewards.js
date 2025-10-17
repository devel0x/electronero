import { useEffect, useMemo, useState } from 'react';
import AdminShell from '../components/layout/AdminShell';
import RewardGraph from '../components/RewardGraph';
import { useAuth } from '../context/AuthContext';
import api from '../lib/api';

export default function RewardsPage() {
  const { token, user } = useAuth();
  const [history, setHistory] = useState([]);
  const [today, setToday] = useState({ rewards: {} });
  const [nodes, setNodes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [exportError, setExportError] = useState('');
  const [exporting, setExporting] = useState(false);
  const [poolAmount, setPoolAmount] = useState('');
  const [poolError, setPoolError] = useState('');
  const [poolSuccess, setPoolSuccess] = useState('');
  const [poolLoading, setPoolLoading] = useState(false);
  const [countdown, setCountdown] = useState('');

  useEffect(() => {
    if (!token) return;
    async function load() {
      try {
        const [historyRes, todayRes, nodesRes] = await Promise.all([
          api.rewardHistory(token),
          api.rewardSummary(token),
          api.listNodes(token),
        ]);
        setHistory(historyRes.history || []);
        setToday(todayRes);
        setNodes(nodesRes || []);
      } catch (err) {
        setError('Unable to load reward data.');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [token]);

  const nodeIndex = useMemo(() => {
    const map = new Map();
    nodes.forEach((node) => map.set(node.id, node));
    return map;
  }, [nodes]);

  const graphData = useMemo(() => {
    const totals = history.reduce((acc, item) => {
      const key = new Date(item.date).toLocaleDateString();
      acc[key] = (acc[key] || 0) + Number(item.amount);
      return acc;
    }, {});
    return Object.entries(totals).map(([date, amount]) => ({ date, amount }));
  }, [history]);

  const totalToday = useMemo(() => {
    return Object.values(today.rewards || {}).reduce((sum, amount) => sum + Number(amount), 0);
  }, [today]);

  const lifetime = useMemo(() => {
    return history.reduce((sum, entry) => sum + Number(entry.amount), 0);
  }, [history]);

  const handleExport = async () => {
    if (!token) return;
    setExportError('');
    setExporting(true);
    try {
      const { blob, filename } = await api.exportRewardsCsv(token);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setExportError('Unable to export rewards CSV. Please try again.');
    } finally {
      setExporting(false);
    }
  };

  const handlePoolTopUp = async (event) => {
    event.preventDefault();
    if (!token) return;
    const amountValue = Number(poolAmount);
    if (!Number.isFinite(amountValue) || amountValue <= 0) {
      setPoolError('Enter a positive amount to fund the pool.');
      setPoolSuccess('');
      return;
    }
    setPoolError('');
    setPoolSuccess('');
    setPoolLoading(true);
    try {
      const response = await api.topUpRewardPool(token, amountValue);
      setToday((prev) => ({ ...prev, pool_balance: response.balance }));
      setPoolSuccess(`Pool balance updated to ${response.balance.toFixed(4)} ITC.`);
      setPoolAmount('');
    } catch (err) {
      setPoolError('Unable to update reward pool. Please try again.');
    } finally {
      setPoolLoading(false);
    }
  };

  useEffect(() => {
    if (!today?.next_payout_at) {
      setCountdown('');
      return undefined;
    }
    const target = new Date(today.next_payout_at);
    if (Number.isNaN(target.getTime())) {
      setCountdown('');
      return undefined;
    }

    const updateCountdown = () => {
      const diff = target.getTime() - Date.now();
      if (diff <= 0) {
        setCountdown('Ready to run');
        return;
      }
      const totalSeconds = Math.floor(diff / 1000);
      const days = Math.floor(totalSeconds / 86400);
      const hours = Math.floor((totalSeconds % 86400) / 3600);
      const minutes = Math.floor((totalSeconds % 3600) / 60);
      const seconds = totalSeconds % 60;
      const parts = [];
      if (days > 0) parts.push(`${days}d`);
      parts.push(`${hours.toString().padStart(2, '0')}h`);
      parts.push(`${minutes.toString().padStart(2, '0')}m`);
      parts.push(`${seconds.toString().padStart(2, '0')}s`);
      setCountdown(parts.join(' '));
    };

    updateCountdown();
    const interval = setInterval(updateCountdown, 1000);
    return () => clearInterval(interval);
  }, [today?.next_payout_at]);

  return (
    <AdminShell title="Rewards & Incentives">
      {loading ? (
        <p className="text-slate-400">Aggregating distribution records…</p>
      ) : error ? (
        <p className="rounded-xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">{error}</p>
      ) : (
        <div className="space-y-8">
          <section className="rounded-2xl border border-slate-900/70 bg-slate-950/60 p-6 shadow-lg shadow-black/30">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold text-slate-100">Reward Velocity</h2>
                <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Daily distributions</p>
              </div>
              <div className="flex flex-wrap items-center gap-4">
                <div className="text-right text-sm text-slate-400">
                  <div>Lifetime distributed</div>
                  <div className="text-lg font-semibold text-emerald-300">{lifetime.toFixed(4)} ITC</div>
                </div>
                <div className="text-right text-sm text-slate-400">
                  <div>Current pool balance</div>
                  <div className="text-lg font-semibold text-sky-300">{Number(today.pool_balance || 0).toFixed(4)} ITC</div>
                </div>
                <div className="text-right text-sm text-slate-400">
                  <div>Next payout window</div>
                  <div className="text-lg font-semibold text-violet-300">{countdown || 'Scheduling…'}</div>
                  {today?.next_payout_at && (
                    <div className="text-xs text-slate-500">
                      {new Date(today.next_payout_at).toLocaleString()}
                    </div>
                  )}
                </div>
                <button
                  type="button"
                  onClick={handleExport}
                  disabled={exporting}
                  className="rounded-xl border border-emerald-400/40 bg-emerald-500/10 px-4 py-2 text-sm font-semibold text-emerald-200 shadow-inner shadow-emerald-500/20 transition hover:bg-emerald-500/20 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {exporting ? 'Preparing CSV…' : 'Download CSV'}
                </button>
              </div>
            </div>
            {exportError && (
              <p className="mb-4 rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">
                {exportError}
              </p>
            )}
            {user?.role === 'SUPER_ADMIN' && (
              <form
                onSubmit={handlePoolTopUp}
                className="mb-4 flex flex-wrap items-end gap-3 rounded-xl border border-slate-900/60 bg-slate-900/30 px-4 py-3"
              >
                <div className="flex flex-col text-sm">
                  <label htmlFor="poolAmount" className="text-xs uppercase tracking-wide text-slate-500">
                    Fund reward pool
                  </label>
                  <input
                    id="poolAmount"
                    type="number"
                    min="0"
                    step="0.00000001"
                    value={poolAmount}
                    onChange={(e) => setPoolAmount(e.target.value)}
                    placeholder="Amount in ITC"
                    className="mt-1 w-40 rounded-lg border border-slate-800 bg-slate-950/80 px-3 py-2 text-slate-100 focus:border-emerald-400/60 focus:outline-none"
                  />
                </div>
                <button
                  type="submit"
                  disabled={poolLoading}
                  className="rounded-xl border border-emerald-400/40 bg-emerald-500/10 px-4 py-2 text-sm font-semibold text-emerald-200 shadow-inner shadow-emerald-500/20 transition hover:bg-emerald-500/20 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {poolLoading ? 'Updating…' : 'Add to Pool'}
                </button>
                <div className="flex-1 text-sm">
                  {poolError && <p className="text-rose-300">{poolError}</p>}
                  {poolSuccess && <p className="text-emerald-300">{poolSuccess}</p>}
                </div>
              </form>
            )}
            <RewardGraph data={graphData} />
          </section>

          <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div className="rounded-2xl border border-slate-900/70 bg-slate-950/60 p-6 shadow-lg shadow-black/30">
              <h2 className="text-lg font-semibold text-slate-100">Today&apos;s Allocations</h2>
              <p className="mt-2 text-sm text-slate-400">Total pool distributed: {totalToday.toFixed(4)} ITC</p>
              <div className="mt-4 space-y-3 text-sm text-slate-300">
                {Object.entries(today.rewards || {}).map(([nodeId, amount]) => {
                  const node = nodeIndex.get(nodeId);
                  return (
                    <div key={nodeId} className="flex items-center justify-between rounded-xl border border-slate-900/60 bg-slate-900/40 px-4 py-3">
                      <div>
                        <div className="font-semibold text-slate-100">{node?.name || nodeId}</div>
                        <div className="text-xs text-slate-500">{node?.wallet_address || 'Wallet not assigned'}</div>
                      </div>
                      <div className="text-emerald-300">{Number(amount).toFixed(4)} ITC</div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="rounded-2xl border border-slate-900/70 bg-slate-950/60 p-6 shadow-lg shadow-black/30">
              <h2 className="text-lg font-semibold text-slate-100">Recent Payout Events</h2>
              <div className="mt-4 space-y-3 text-sm text-slate-300">
                {history.slice(-10).reverse().map((entry) => {
                  const node = nodeIndex.get(entry.node_id);
                  return (
                    <div key={`${entry.node_id}-${entry.date}`} className="rounded-xl border border-slate-900/60 bg-slate-900/30 px-4 py-3">
                      <div className="flex items-center justify-between">
                        <span className="text-slate-100">{node?.name || entry.node_id}</span>
                        <span className="text-emerald-300">{Number(entry.amount).toFixed(4)} ITC</span>
                      </div>
                      <div className="text-xs text-slate-500">{new Date(entry.date).toLocaleString()}</div>
                    </div>
                  );
                })}
              </div>
            </div>
          </section>
        </div>
      )}
    </AdminShell>
  );
}
