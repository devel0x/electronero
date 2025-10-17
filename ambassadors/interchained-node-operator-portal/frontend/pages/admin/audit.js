import { useEffect, useState } from 'react';
import AdminShell from '../../components/layout/AdminShell';
import AuditTable from '../../components/tables/AuditTable';
import { useAuth } from '../../context/AuthContext';
import api from '../../lib/api';

export default function AuditLogPage() {
  const { token } = useAuth();
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!token) return;
    async function load() {
      try {
        const data = await api.auditLog(token, 200);
        setEvents(data || []);
      } catch (err) {
        setError('Unable to load audit log.');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [token]);

  return (
    <AdminShell title="Audit Trail">
      {loading ? (
        <p className="text-slate-400">Fetching compliance history…</p>
      ) : error ? (
        <p className="rounded-xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">{error}</p>
      ) : (
        <AuditTable events={events} />
      )}
    </AdminShell>
  );
}
