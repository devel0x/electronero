export default function AuditTable({ events }) {
  if (!events?.length) {
    return <p className="text-sm text-slate-400">No audit events captured yet.</p>;
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-900/60">
      <table className="min-w-full divide-y divide-slate-900/70">
        <thead className="bg-slate-950/80 text-left text-xs uppercase tracking-widest text-slate-500">
          <tr>
            <th className="px-4 py-3">Timestamp</th>
            <th className="px-4 py-3">Actor</th>
            <th className="px-4 py-3">Action</th>
            <th className="px-4 py-3">Target</th>
            <th className="px-4 py-3">Metadata</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-900/80 text-sm text-slate-300">
          {events.map((event) => (
            <tr key={event.id} className="hover:bg-slate-900/50">
              <td className="px-4 py-3 text-slate-400">{new Date(event.created_at).toLocaleString()}</td>
              <td className="px-4 py-3 font-medium text-slate-200">{event.actor_email}</td>
              <td className="px-4 py-3 uppercase tracking-wide text-slate-400">{event.action}</td>
              <td className="px-4 py-3 text-slate-400">{event.target || '—'}</td>
              <td className="px-4 py-3 text-xs text-slate-500">
                {Object.keys(event.metadata || {}).length ? (
                  <pre className="whitespace-pre-wrap break-words">{JSON.stringify(event.metadata, null, 2)}</pre>
                ) : (
                  '—'
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
