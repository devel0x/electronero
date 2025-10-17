import StatusBadge from './StatusBadge';

export default function NodeTable({ nodes }) {
  if (!nodes?.length) {
    return <p className="text-sm text-slate-400">No nodes registered yet.</p>;
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-800/60 bg-slate-950/40">
      <table className="min-w-full divide-y divide-slate-900/70">
        <thead className="bg-slate-950/80">
          <tr className="text-left text-xs uppercase tracking-widest text-slate-500">
            <th className="px-4 py-3">Node</th>
            <th className="px-4 py-3">RPC URL</th>
            <th className="px-4 py-3">Latency</th>
            <th className="px-4 py-3">Block Height</th>
            <th className="px-4 py-3">Uptime</th>
            <th className="px-4 py-3">Tags</th>
            <th className="px-4 py-3">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-900/80 text-sm">
          {nodes.map((node) => {
            const uptime = (node.uptime_score || 0) * 100;
            const status = (() => {
              if (node.is_flagged) return 'Flagged';
              if (node.p2p_online && !node.rpc_responding) return 'Seed Online';
              if (node.p2p_online && node.rpc_responding) return 'Online';
              if (uptime > 70) return 'Degraded';
              if (uptime > 0) return 'Degraded';
              return 'Offline';
            })();
            const interfaceLabel = node.p2p_online
              ? node.rpc_responding
                ? 'P2P + RPC'
                : 'P2P only'
              : 'No signal';
            return (
              <tr key={node.id} className="hover:bg-slate-900/50">
                <td className="px-4 py-3">
                  <div className="font-semibold text-slate-100">{node.name}</div>
                  <div className="text-xs text-slate-500">{node.p2p_address}</div>
                  <div className="text-[10px] uppercase tracking-widest text-slate-600">{node.owner_email || 'Unassigned'}</div>
                </td>
                <td className="px-4 py-3 text-slate-300">{node.rpc_url}</td>
                <td className="px-4 py-3">{node.latency_ms ? `${node.latency_ms.toFixed(0)} ms` : '–'}</td>
                <td className="px-4 py-3">{node.block_height || '–'}</td>
                <td className="px-4 py-3">{uptime.toFixed(1)}%</td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-2 text-[10px] uppercase tracking-wide text-emerald-300/80">
                    {node.tags?.length ? node.tags.map((tag) => <span key={tag}>#{tag}</span>) : <span className="text-slate-500">—</span>}
                  </div>
                </td>
                <td className="px-4 py-3">
                  <StatusBadge status={status} />
                  <div className="mt-1 text-[10px] uppercase tracking-widest text-slate-600">{interfaceLabel}</div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
