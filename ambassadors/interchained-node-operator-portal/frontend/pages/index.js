import Link from 'next/link';

export default function Landing() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center space-y-12 bg-slate-950 px-6 py-20 text-slate-100">
      <div className="max-w-3xl space-y-6 text-center">
        <div className="text-sm uppercase tracking-[0.4em] text-slate-500">Interchained Infrastructure</div>
        <h1 className="text-5xl font-semibold md:text-6xl">
          Enterprise Control Plane for Node Operators
        </h1>
        <p className="text-lg text-slate-300">
          Operate mission-critical Interchained infrastructure with SLO-driven monitoring, weighted reward distribution, and
          enterprise-grade access controls.
        </p>
        <div className="flex flex-col items-center justify-center gap-4 sm:flex-row">
          <Link
            href="/login"
            className="rounded-full bg-gradient-to-r from-emerald-500 to-cyan-500 px-8 py-3 text-sm font-semibold uppercase tracking-[0.3em] text-slate-950 transition hover:from-emerald-400 hover:to-cyan-400"
          >
            Launch Admin Portal
          </Link>
          <Link
            href="/rewards"
            className="rounded-full border border-slate-700 px-8 py-3 text-sm uppercase tracking-[0.3em] text-slate-300 transition hover:border-emerald-500/60 hover:text-emerald-200"
          >
            Explore Rewards
          </Link>
        </div>
      </div>
      <div className="grid max-w-5xl grid-cols-1 gap-6 md:grid-cols-3">
        {[ 
          {
            title: 'Zero-Touch Telemetry',
            body: 'FastAPI orchestrators probe fleet health every 60 seconds with Redis-backed SLA dashboards.',
          },
          {
            title: 'Role-Based Control',
            body: 'Multi-tenant RBAC with invite workflows, audit trails, and per-organization analytics.',
          },
          {
            title: 'Reward Intelligence',
            body: 'Weighted payouts, billing summaries, and trend analytics keep operators incentivised.',
          },
        ].map((item) => (
          <div key={item.title} className="rounded-2xl border border-slate-900 bg-slate-900/60 p-6 text-left shadow-lg shadow-black/30">
            <h3 className="text-xl font-semibold text-emerald-300">{item.title}</h3>
            <p className="mt-3 text-sm text-slate-400">{item.body}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
