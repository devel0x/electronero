import StatusBadge from './StatusBadge';

export default function NodeTable({ nodes }) {
  if (!nodes?.length) {
    return <p className="text-sm text-slate-400">No nodes registered yet.</p>;
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-700/40">
      <table className="min-w-full divide-y divide-slate-800/80">
        <thead className="bg-slate-900/60">
          <tr className="text-left text-xs uppercase tracking-widest text-slate-400">
            <th className="px-4 py-3">Node</th>
            <th className="px-4 py-3">RPC URL</th>
            <th className="px-4 py-3">Latency</th>
            <th className="px-4 py-3">Block Height</th>
            <th className="px-4 py-3">Uptime</th>
            <th className="px-4 py-3">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800/80 text-sm">
          {nodes.map((node) => (
            <tr key={node.email} className="hover:bg-slate-900/40">
              <td className="px-4 py-3">
                <div className="font-medium text-slate-100">{node.p2p_address}</div>
                <div className="text-xs text-slate-500">{node.email}</div>
              </td>
              <td className="px-4 py-3 text-slate-300">{node.rpc_url}</td>
              <td className="px-4 py-3">{node.latency_ms ? `${node.latency_ms.toFixed(0)} ms` : '–'}</td>
              <td className="px-4 py-3">{node.block_height || '–'}</td>
              <td className="px-4 py-3">{(node.uptime_score * 100).toFixed(1)}%</td>
              <td className="px-4 py-3">
                <StatusBadge
                  status={node.uptime_score > 0.9 ? 'Online' : node.uptime_score > 0.5 ? 'Degraded' : 'Offline'}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
