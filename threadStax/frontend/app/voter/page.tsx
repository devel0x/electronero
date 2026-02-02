"use client";

import { useEffect, useState } from "react";
import RoleGate from "../../components/RoleGate";
import SeasonPicker from "../../components/SeasonPicker";
import Toast from "../../components/Toast";
import { apiFetch } from "../../lib/api";
import { LeaderboardEntry } from "../../lib/types";

export default function VoterPage() {
  const [sid, setSid] = useState("");
  const [entries, setEntries] = useState<LeaderboardEntry[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [voted, setVoted] = useState<Record<string, boolean>>({});

  const loadEntries = async (seasonId: string) => {
    if (!seasonId) return;
    const data = await apiFetch<LeaderboardEntry[]>(`/season/${seasonId}/leaderboard/votes`);
    setEntries(data);
  };

  useEffect(() => {
    if (sid) {
      loadEntries(sid).catch(() => setEntries([]));
    }
  }, [sid]);

  const handleVote = async (subId: string) => {
    setMessage(null);
    try {
      await apiFetch(`/season/${sid}/vote/${subId}`, { method: "POST" });
      setVoted((prev) => ({ ...prev, [subId]: true }));
      setMessage("Vote submitted.");
      loadEntries(sid);
    } catch {
      setMessage("Vote failed or already submitted.");
      setVoted((prev) => ({ ...prev, [subId]: true }));
    }
  };

  return (
    <RoleGate allow={["voter"]}>
      <div className="space-y-6">
        <div className="rounded-2xl border border-white/10 bg-card p-6">
          <h1 className="text-2xl font-semibold">Vote</h1>
          <div className="mt-4 max-w-sm">
            <SeasonPicker value={sid} onChange={setSid} />
          </div>
        </div>

        <div className="space-y-3">
          {entries.map((entry) => (
            <div key={entry.sub_id} className="rounded-2xl border border-white/10 bg-card p-4">
              <p className="text-sm text-white/60">{entry.username || entry.uid}</p>
              <a href={entry.threads_url} target="_blank" className="text-accent">
                {entry.threads_url}
              </a>
              <div className="mt-3 flex items-center justify-between">
                <span className="text-sm text-white/60">Votes: {entry.score}</span>
                <button
                  onClick={() => handleVote(entry.sub_id)}
                  disabled={voted[entry.sub_id]}
                  className="rounded-full border border-white/10 px-4 py-2 text-sm"
                >
                  {voted[entry.sub_id] ? "Voted" : "Vote"}
                </button>
              </div>
            </div>
          ))}
        </div>
        {message && <Toast message={message} variant={message.includes("failed") ? "error" : "success"} />}
      </div>
    </RoleGate>
  );
}
