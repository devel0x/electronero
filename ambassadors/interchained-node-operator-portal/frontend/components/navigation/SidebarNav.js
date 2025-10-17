import Link from 'next/link';
import { useRouter } from 'next/router';
import clsx from 'clsx';

const NAV_ITEMS = [
  { href: '/dashboard', label: 'Overview', roles: ['super_admin', 'org_admin', 'operator', 'auditor'] },
  { href: '/nodes', label: 'Nodes', roles: ['super_admin', 'org_admin', 'operator'] },
  { href: '/rewards', label: 'Rewards', roles: ['super_admin', 'org_admin', 'operator', 'auditor'] },
  { href: '/admin/users', label: 'Team Access', roles: ['super_admin', 'org_admin'] },
  { href: '/admin/organizations', label: 'Organizations', roles: ['super_admin'] },
  { href: '/admin/billing', label: 'Billing', roles: ['super_admin', 'org_admin'] },
  { href: '/admin/audit', label: 'Audit Log', roles: ['super_admin', 'org_admin'] },
];

export default function SidebarNav({ role }) {
  const router = useRouter();
  const items = NAV_ITEMS.filter((item) => item.roles.includes(role));

  return (
    <aside className="w-64 border-r border-slate-900/70 bg-slate-950/95 px-6 py-8">
      <div className="mb-8">
        <div className="text-xs uppercase tracking-[0.4em] text-slate-500">Interchained</div>
        <div className="mt-2 text-lg font-semibold text-slate-100">Operator Control Plane</div>
      </div>
      <nav className="space-y-2">
        {items.map((item) => (
          <Link key={item.href} href={item.href} legacyBehavior>
            <a
              className={clsx(
                'flex items-center justify-between rounded-xl px-3 py-2 text-sm font-medium transition',
                router.pathname === item.href
                  ? 'bg-gradient-to-r from-emerald-500/20 to-cyan-500/10 text-emerald-200'
                  : 'text-slate-400 hover:bg-slate-900/60 hover:text-slate-200'
              )}
            >
              <span>{item.label}</span>
              <span className="text-[10px] uppercase tracking-widest text-slate-600">{item.roles.includes('super_admin') ? 'Admin' : ''}</span>
            </a>
          </Link>
        ))}
      </nav>
    </aside>
  );
}
