import { useEffect, useState } from 'react';
import AdminShell from '../components/layout/AdminShell';
import NodeTable from '../components/NodeTable';
import { useAuth } from '../context/AuthContext';
import api from '../lib/api';

const DEFAULT_FORM = {
  name: '',
  p2p_address: '',
  rpc_url: '',
  wallet_address: '',
  tags: '',
};

export default function NodesPage() {
  const { token, user } = useAuth();
  const [nodes, setNodes] = useState([]);
  const [form, setForm] = useState(DEFAULT_FORM);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    if (!token) return;
    async function load() {
      try {
        const data = await api.listNodes(token);
        setNodes(data);
      } catch (err) {
        setError('Unable to load node inventory.');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [token]);

  const handleChange = (event) => {
    const { name, value } = event.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const resetForm = () => {
    setForm(DEFAULT_FORM);
  };

  const handleCreate = async (event) => {
    event.preventDefault();
    if (!token) return;
    setMessage('');
    setError('');
    try {
      const payload = {
        name: form.name,
        p2p_address: form.p2p_address,
        rpc_url: form.rpc_url,
        wallet_address: form.wallet_address,
        tags: form.tags
          .split(',')
          .map((tag) => tag.trim())
          .filter(Boolean),
      };
      const created = await api.createNode(token, payload);
      setNodes((prev) => [created, ...prev]);
      resetForm();
      setMessage(`Node ${created.name} registered.`);
    } catch (err) {
      setError(err.message || 'Unable to register node.');
    }
  };

  const toggleFlag = async (node) => {
    if (!token) return;
    try {
      const updated = await api.updateNode(token, node.id, { is_flagged: !node.is_flagged });
      setNodes((prev) => prev.map((entry) => (entry.id === updated.id ? updated : entry)));
    } catch (err) {
      setError('Failed to update node flag.');
    }
  };

  return (
    <AdminShell title="Node Operations">
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
        <section className="lg:col-span-2 space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-slate-100">Registered Nodes</h2>
            <span className="text-xs text-slate-500">{nodes.length} total</span>
          </div>
          {loading ? (
            <p className="text-slate-400">Querying fleet telemetry…</p>
          ) : (
            <NodeTable nodes={nodes} />
          )}
          {!loading && nodes.length > 0 && (
            <div className="rounded-xl border border-slate-900/70 bg-slate-950/60 p-4 text-sm text-slate-400">
              <h3 className="mb-2 text-sm font-semibold uppercase tracking-[0.3em] text-slate-500">Flagged nodes</h3>
              <div className="space-y-2">
                {nodes.filter((node) => node.is_flagged).length ? (
                  nodes
                    .filter((node) => node.is_flagged)
                    .map((node) => (
                      <div key={node.id} className="flex items-center justify-between">
                        <span className="text-slate-200">{node.name}</span>
                        <button
                          onClick={() => toggleFlag(node)}
                          className="text-xs uppercase tracking-wide text-fuchsia-300 hover:text-fuchsia-100"
                        >
                          Clear Flag
                        </button>
                      </div>
                    ))
                ) : (
                  <p className="text-slate-500">No nodes currently flagged for review.</p>
                )}
              </div>
            </div>
          )}
        </section>

        <section className="rounded-2xl border border-slate-900/70 bg-slate-950/60 p-6 shadow-lg shadow-black/30">
          <h2 className="text-lg font-semibold text-slate-100">Provision Node</h2>
          <p className="mt-2 text-sm text-slate-400">
            Register a node with the control plane to start receiving uptime scoring and reward attribution. Tags are optional
            and help categorise infrastructure (e.g. edge, validator, apac).
          </p>
          <form onSubmit={handleCreate} className="mt-6 space-y-4">
            <label className="block text-xs uppercase tracking-[0.3em] text-slate-500">
              Friendly Name
              <input
                name="name"
                value={form.name}
                onChange={handleChange}
                required
                placeholder="Northern Lights Validator"
                className="mt-2 w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-slate-200 focus:border-emerald-400/60 focus:outline-none"
              />
            </label>
            <label className="block text-xs uppercase tracking-[0.3em] text-slate-500">
              P2P Address
              <input
                name="p2p_address"
                value={form.p2p_address}
                onChange={handleChange}
                required
                placeholder="node.example.com:18080"
                className="mt-2 w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-slate-200 focus:border-emerald-400/60 focus:outline-none"
              />
            </label>
            <label className="block text-xs uppercase tracking-[0.3em] text-slate-500">
              RPC URL
              <input
                name="rpc_url"
                type="url"
                value={form.rpc_url}
                onChange={handleChange}
                required
                placeholder="https://node.example.com:18089/json_rpc"
                className="mt-2 w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-slate-200 focus:border-emerald-400/60 focus:outline-none"
              />
            </label>
            <label className="block text-xs uppercase tracking-[0.3em] text-slate-500">
              Wallet Address
              <input
                name="wallet_address"
                value={form.wallet_address}
                onChange={handleChange}
                required
                className="mt-2 w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-slate-200 focus:border-emerald-400/60 focus:outline-none"
              />
            </label>
            <label className="block text-xs uppercase tracking-[0.3em] text-slate-500">
              Tags
              <input
                name="tags"
                value={form.tags}
                onChange={handleChange}
                placeholder="edge, apac"
                className="mt-2 w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-slate-200 focus:border-emerald-400/60 focus:outline-none"
              />
            </label>
            <button
              type="submit"
              className="w-full rounded-xl bg-gradient-to-r from-emerald-500/80 to-cyan-500/60 py-3 text-sm font-semibold uppercase tracking-[0.3em] text-slate-950 transition hover:from-emerald-400 hover:to-cyan-400"
            >
              Register Node
            </button>
          </form>
          {message && <p className="mt-4 text-xs text-emerald-300">{message}</p>}
          {error && <p className="mt-4 text-xs text-rose-300">{error}</p>}
        </section>
      </div>
    </AdminShell>
  );
}
