import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

export default function UptimeTrend({ data }) {
  if (!data?.length) {
    return <p className="text-sm text-slate-400">No uptime data available.</p>;
  }

  const formatted = data.map((point) => ({
    date: new Date(point.timestamp).toLocaleDateString(),
    value: Math.round(point.value * 100) / 100,
  }));

  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={formatted} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="uptimeGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#38bdf8" stopOpacity={0.8} />
              <stop offset="100%" stopColor="#0f172a" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis dataKey="date" stroke="#64748b" />
          <YAxis stroke="#64748b" domain={[0, 100]} tickFormatter={(value) => `${value}%`} />
          <Tooltip
            contentStyle={{ backgroundColor: 'rgba(15,23,42,0.95)', borderColor: '#1e293b', borderRadius: '0.75rem' }}
            labelStyle={{ color: '#cbd5f5' }}
            formatter={(value) => [`${value}%`, 'Average Uptime']}
          />
          <Area type="monotone" dataKey="value" stroke="#38bdf8" fill="url(#uptimeGradient)" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
