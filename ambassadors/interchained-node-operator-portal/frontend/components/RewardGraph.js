import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

export default function RewardGraph({ data }) {
  if (!data?.length) {
    return <p className="text-sm text-slate-400">No rewards distributed yet.</p>;
  }

  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="rewardGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#f472b6" stopOpacity={0.9} />
              <stop offset="100%" stopColor="#0f172a" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
          <XAxis dataKey="date" stroke="#64748b" />
          <YAxis stroke="#64748b" tickFormatter={(value) => `${value.toFixed(2)} ITC`} />
          <Tooltip
            contentStyle={{ backgroundColor: 'rgba(15,23,42,0.9)', borderColor: '#334155', borderRadius: '0.75rem' }}
            labelStyle={{ color: '#e2e8f0' }}
            formatter={(value) => [`${Number(value).toFixed(4)} ITC`, 'Reward Pool']}
          />
          <Area type="monotone" dataKey="amount" stroke="#f472b6" fill="url(#rewardGradient)" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
