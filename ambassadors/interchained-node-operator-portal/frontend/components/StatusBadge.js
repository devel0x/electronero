const colors = {
  online: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/50',
  offline: 'bg-rose-500/20 text-rose-300 border-rose-500/50',
  degraded: 'bg-amber-500/20 text-amber-300 border-amber-500/50',
};

export default function StatusBadge({ status }) {
  const key = status?.toLowerCase();
  const style = colors[key] || colors.degraded;
  return (
    <span className={`px-3 py-1 rounded-full border text-xs uppercase tracking-widest ${style}`}>
      {status}
    </span>
  );
}
