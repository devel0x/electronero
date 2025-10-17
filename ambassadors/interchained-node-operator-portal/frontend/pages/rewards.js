import { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import axios from 'axios';
import GlassContainer from '../components/GlassContainer';
import RewardGraph from '../components/RewardGraph';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

export default function RewardsPage() {
  const router = useRouter();
  const [history, setHistory] = useState([]);
  const [today, setToday] = useState({ rewards: {} });
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

    async function fetchRewards() {
      try {
        const [historyRes, todayRes] = await Promise.all([
          client.get('/rewards/history'),
          client.get('/rewards/today'),
        ]);
        setHistory(historyRes.data.history);
        setToday(todayRes.data);
      } catch (err) {
        localStorage.removeItem('token');
        router.push('/login');
      } finally {
        setLoading(false);
      }
    }

    fetchRewards();
  }, [router]);

  if (loading) {
    return <p className="p-10 text-slate-400">Loading rewards...</p>;
  }

  const graphData = history.map((entry) => ({
    date: new Date(entry.date).toLocaleDateString(),
    amount: entry.amount,
  }));

  return (
    <div className="px-6 py-12 space-y-10">
      <GlassContainer>
        <h1 className="text-3xl font-heading text-neon-blue mb-4">Reward History</h1>
        <RewardGraph data={graphData} />
      </GlassContainer>

      <GlassContainer>
        <h2 className="text-2xl font-heading text-neon-blue mb-4">Today&apos;s Pool</h2>
        <div className="space-y-4">
          <div className="flex justify-between text-sm text-slate-300">
            <span>Total Pool Distributed</span>
            <span>
              {Object.values(today.rewards || {})
                .reduce((sum, amount) => sum + Number(amount), 0)
                .toFixed(4)}{' '}
              ITC
            </span>
          </div>
          <ul className="space-y-2 text-sm text-slate-300">
            {Object.entries(today.rewards || {}).map(([email, amount]) => (
              <li key={email} className="flex justify-between">
                <span>{email}</span>
                <span>{Number(amount).toFixed(4)} ITC</span>
              </li>
            ))}
          </ul>
        </div>
      </GlassContainer>
    </div>
  );
}
