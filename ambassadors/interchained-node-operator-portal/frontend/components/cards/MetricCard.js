export default function MetricCard({ label, value, helper, tone = 'emerald' }) {
  const tones = {
    emerald: 'from-emerald-500/30 to-cyan-500/10 text-emerald-100',
    amber: 'from-amber-500/30 to-rose-500/10 text-amber-100',
    slate: 'from-slate-500/40 to-slate-700/10 text-slate-100',
    fuchsia: 'from-fuchsia-500/40 to-indigo-500/10 text-fuchsia-100',
  };

  return (
    <div className={`rounded-2xl border border-slate-900/60 bg-slate-950/60 p-6 shadow-lg shadow-black/30`}> 
      <p className="text-xs uppercase tracking-[0.35em] text-slate-500">{label}</p>
      <div className={`mt-3 bg-gradient-to-r ${tones[tone] || tones.emerald} bg-clip-text text-4xl font-semibold text-transparent`}>
        {value}
      </div>
      {helper && <p className="mt-3 text-xs text-slate-400">{helper}</p>}
    </div>
  );
}
