import Head from 'next/head';
import { useRouter } from 'next/router';
import { useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import SidebarNav from '../navigation/SidebarNav';

export default function AdminShell({ title, children }) {
  const { user, loading, logout } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.replace('/login');
    }
  }, [user, loading, router]);

  if (loading || !user) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-950 text-slate-400">
        <span className="animate-pulse">Loading control plane…</span>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-slate-950 text-slate-100">
      <Head>
        <title>{title ? `${title} · Interchained Control Plane` : 'Interchained Control Plane'}</title>
      </Head>
      <SidebarNav role={user.role} />
      <div className="flex flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-slate-900/60 bg-slate-950/90 px-10 py-5 backdrop-blur">
          <div>
            <h1 className="text-2xl font-semibold text-slate-100">{title}</h1>
            <p className="text-sm text-slate-400">{user.organization_id}</p>
          </div>
          <div className="flex items-center gap-4">
            <div className="text-right">
              <p className="text-sm font-semibold text-slate-100">{user.full_name || user.email}</p>
              <p className="text-xs uppercase tracking-wide text-slate-500">{user.role.replace('_', ' ')}</p>
            </div>
            <button
              onClick={() => {
                logout();
                router.push('/login');
              }}
              className="rounded-lg border border-slate-800 px-4 py-2 text-xs font-medium uppercase tracking-wide text-slate-300 transition hover:border-rose-500/40 hover:text-rose-300"
            >
              Logout
            </button>
          </div>
        </header>
        <main className="flex-1 bg-slate-950/80 px-10 py-8">{children}</main>
      </div>
    </div>
  );
}
