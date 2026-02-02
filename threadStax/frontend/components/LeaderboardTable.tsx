import { LeaderboardEntry } from "../lib/types";

export default function LeaderboardTable({
  entries,
  label,
}: {
  entries: LeaderboardEntry[];
  label: string;
}) {
  return (
    <div className="overflow-hidden rounded-2xl border border-white/10">
      <table className="w-full text-left text-sm">
        <thead className="bg-white/5 text-xs uppercase text-white/50">
          <tr>
            <th className="px-4 py-3">Rank</th>
            <th className="px-4 py-3">Participant</th>
            <th className="px-4 py-3">{label}</th>
            <th className="px-4 py-3">Threads URL</th>
            <th className="px-4 py-3">Status</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry, index) => (
            <tr key={entry.sub_id} className="border-t border-white/10">
              <td className="px-4 py-3">#{index + 1}</td>
              <td className="px-4 py-3">{entry.username || entry.uid}</td>
              <td className="px-4 py-3">{entry.score}</td>
              <td className="px-4 py-3">
                <a href={entry.threads_url} target="_blank" className="text-accent">
                  View
                </a>
              </td>
              <td className="px-4 py-3">{entry.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
