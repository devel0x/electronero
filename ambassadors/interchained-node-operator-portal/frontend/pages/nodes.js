import { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import axios from 'axios';
import GlassContainer from '../components/GlassContainer';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

export default function NodesPage() {
  const router = useRouter();
  const [node, setNode] = useState(null);
  const [form, setForm] = useState({ p2p_address: '', rpc_url: '', wallet_address: '' });
  const [status, setStatus] = useState('');

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) {
      router.push('/login');
      return;
    }

    const client = axios.create({
      baseURL: API_BASE,
      headers: { Authorization: `Bearer ${token}` },
    });

    client
      .get('/nodes/me')
      .then((response) => {
        setNode(response.data);
        setForm({
          p2p_address: response.data.p2p_address,
          rpc_url: response.data.rpc_url,
          wallet_address: response.data.wallet_address,
        });
      })
      .catch(() => setNode(null));

    NodesPage.client = client;
  }, [router]);

  const handleChange = (event) => {
    const { name, value } = event.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setStatus('');
    const token = localStorage.getItem('token');
    if (!token) {
      router.push('/login');
      return;
    }

    const client = axios.create({
      baseURL: API_BASE,
      headers: { Authorization: `Bearer ${token}` },
    });

    try {
      if (node) {
        const response = await client.patch('/nodes/me', form);
        setNode(response.data);
        setStatus('Node updated successfully.');
      } else {
        const me = await client.get('/users/me');
        const response = await client.post('/nodes/register', { ...form, email: me.data.email });
        setNode(response.data);
        setStatus('Node registered successfully.');
      }
    } catch (err) {
      setStatus(err.response?.data?.detail || 'Unable to save node.');
    }
  };

  return (
    <div className="px-6 py-12 flex justify-center">
      <GlassContainer className="w-full max-w-2xl">
        <h1 className="text-3xl font-heading text-neon-blue mb-6">Node Configuration</h1>
        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label className="block text-sm text-slate-300">
              P2P Address
              <input
                name="p2p_address"
                value={form.p2p_address}
                onChange={handleChange}
                required
                placeholder="node.example.com:18080"
                className="mt-1 w-full rounded-lg bg-slate-900/60 border border-slate-700 px-3 py-2 focus:outline-none focus:border-neon-blue"
              />
            </label>
          </div>
          <div>
            <label className="block text-sm text-slate-300">
              RPC URL
              <input
                name="rpc_url"
                type="url"
                value={form.rpc_url}
                onChange={handleChange}
                required
                placeholder="https://node.example.com:18089/json_rpc"
                className="mt-1 w-full rounded-lg bg-slate-900/60 border border-slate-700 px-3 py-2 focus:outline-none focus:border-neon-pink"
              />
            </label>
          </div>
          <div>
            <label className="block text-sm text-slate-300">
              Wallet Address
              <input
                name="wallet_address"
                value={form.wallet_address}
                onChange={handleChange}
                required
                className="mt-1 w-full rounded-lg bg-slate-900/60 border border-slate-700 px-3 py-2 focus:outline-none focus:border-neon-purple"
              />
            </label>
          </div>
          <button
            type="submit"
            className="w-full py-3 rounded-full bg-gradient-to-r from-neon-pink to-neon-blue uppercase tracking-widest"
          >
            {node ? 'Update Node' : 'Register Node'}
          </button>
        </form>
        {status && <p className="mt-4 text-sm text-slate-300">{status}</p>}
      </GlassContainer>
    </div>
  );
}
