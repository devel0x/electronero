export default function NeonCard({ title, value, footer }) {
  return (
    <div className="glass-panel p-6 space-y-2">
      <p className="text-xs uppercase tracking-widest text-slate-400">{title}</p>
      <p className="text-3xl font-heading text-neon-blue">{value}</p>
      {footer && <p className="text-xs text-slate-400">{footer}</p>}
    </div>
  );
}
