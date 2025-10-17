import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

export default function RewardGraph({ data }) {
  if (!data?.length) {
    return <p className="text-sm text-slate-400">No rewards distributed yet.</p>;
  }

  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data}>
          <defs>
            <linearGradient id="rewardGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#35d3ff" stopOpacity={0.8} />
              <stop offset="95%" stopColor="#ff2d95" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
          <XAxis dataKey="date" stroke="#64748b" />
          <YAxis stroke="#64748b" />
          <Tooltip
            contentStyle={{ backgroundColor: 'rgba(15,23,42,0.9)', borderColor: '#334155' }}
            labelStyle={{ color: '#e2e8f0' }}
          />
          <Area type="monotone" dataKey="amount" stroke="#35d3ff" fill="url(#rewardGradient)" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
