import { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import axios from 'axios';
import NeonCard from '../components/NeonCard';
import GlassContainer from '../components/GlassContainer';
import NodeTable from '../components/NodeTable';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

export default function Dashboard() {
  const router = useRouter();
  const [profile, setProfile] = useState(null);
  const [node, setNode] = useState(null);
  const [rewards, setRewards] = useState({ rewards: {} });
  const [loading, setLoading] = useState(true);

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

    async function fetchData() {
      try {
        const [meRes, nodeRes, rewardsRes] = await Promise.all([
          client.get('/users/me'),
          client.get('/nodes/me').catch(() => null),
          client.get('/rewards/today'),
        ]);
        setProfile(meRes.data);
        setNode(nodeRes?.data || null);
        setRewards(rewardsRes.data);
      } catch (err) {
        localStorage.removeItem('token');
        router.push('/login');
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, [router]);

  if (loading) {
    return <p className="p-10 text-slate-400">Loading dashboard...</p>;
  }

  const uptime = node ? (node.uptime_score * 100).toFixed(2) : '0.00';
  const latency = node?.latency_ms ? `${node.latency_ms.toFixed(0)} ms` : '–';
  const rewardToday = Object.values(rewards.rewards || {}).reduce((sum, value) => sum + Number(value), 0);

  return (
    <div className="px-6 py-10 space-y-10">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6">
        <div>
          <p className="text-sm text-slate-400 uppercase">Welcome back</p>
          <h1 className="text-4xl font-heading text-neon-blue">{profile?.email}</h1>
        </div>
        <button
          onClick={() => {
            localStorage.removeItem('token');
            router.push('/login');
          }}
          className="self-start px-4 py-2 rounded-full border border-slate-600/70 hover:border-neon-pink"
        >
          Sign out
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <NeonCard title="Uptime Score" value={`${uptime}%`} footer="Last 24 hours" />
        <NeonCard title="RPC Latency" value={latency} footer="Latest probe" />
        <NeonCard title="Rewards Distributed" value={`${rewardToday.toFixed(2)} ITC`} footer="Today" />
      </div>

      <GlassContainer>
        <h2 className="text-xl font-heading text-neon-blue mb-4">Node Health</h2>
        <NodeTable nodes={node ? [node] : []} />
      </GlassContainer>
    </div>
  );
}
