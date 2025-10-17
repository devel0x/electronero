export default function OrganizationTable({ organizations }) {
  if (!organizations?.length) {
    return <p className="text-sm text-slate-400">No organizations found.</p>;
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-900/60">
      <table className="min-w-full divide-y divide-slate-900/80">
        <thead className="bg-slate-950/80 text-left text-xs uppercase tracking-widest text-slate-500">
          <tr>
            <th className="px-4 py-3">Name</th>
            <th className="px-4 py-3">Plan</th>
            <th className="px-4 py-3">Billing Email</th>
            <th className="px-4 py-3">Members</th>
            <th className="px-4 py-3">Created</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-900/80 text-sm text-slate-300">
          {organizations.map((org) => (
            <tr key={org.id} className="hover:bg-slate-900/50">
              <td className="px-4 py-3">
                <div className="font-semibold text-slate-100">{org.name}</div>
                <div className="text-xs uppercase tracking-widest text-slate-500">{org.slug}</div>
              </td>
              <td className="px-4 py-3 text-slate-300">{org.plan}</td>
              <td className="px-4 py-3 text-slate-400">{org.billing_email}</td>
              <td className="px-4 py-3 text-slate-400">{org.member_count ?? '—'}</td>
              <td className="px-4 py-3 text-slate-400">{new Date(org.created_at).toLocaleDateString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
