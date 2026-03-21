"use client";

import { useEffect, useState } from "react";
import RoleGate from "../../components/RoleGate";
import SeasonPicker from "../../components/SeasonPicker";
import AdminModerationQueue from "../../components/AdminModerationQueue";
import Toast from "../../components/Toast";
import { apiFetch } from "../../lib/api";
import { Submission } from "../../lib/types";

export default function AdminPage() {
  const [seasonId, setSeasonId] = useState("");
  const [newSeason, setNewSeason] = useState("");
  const [status, setStatus] = useState("draft");
  const [judgeUsernames, setJudgeUsernames] = useState("");
  const [queue, setQueue] = useState<Submission[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [winners, setWinners] = useState<string[]>([]);
  const [topN, setTopN] = useState(10);

  const loadQueue = async (sid: string) => {
    if (!sid) return;
    const data = await apiFetch<Submission[]>(`/admin/season/${sid}/moderation/queue`);
    setQueue(data);
  };

  useEffect(() => {
    if (seasonId) {
      loadQueue(seasonId).catch(() => setQueue([]));
    }
  }, [seasonId]);

  const handleCreateSeason = async (event: React.FormEvent) => {
    event.preventDefault();
    setMessage(null);
    try {
      await apiFetch("/admin/season", {
        method: "POST",
        body: JSON.stringify({ sid: newSeason, status }),
      });
      setMessage("Season created.");
    } catch {
      setMessage("Season creation failed.");
    }
  };

  const handleStatusUpdate = async () => {
    if (!seasonId) return;
    await apiFetch(`/admin/season/${seasonId}/status`, {
      method: "POST",
      body: JSON.stringify({ status }),
    });
    setMessage("Season status updated.");
  };

  const handleSeedJudges = async () => {
    const usernames = judgeUsernames
      .split("\n")
      .map((name) => name.trim())
      .filter(Boolean);
    await apiFetch("/admin/seed/judges", {
      method: "POST",
      body: JSON.stringify({ usernames }),
    });
    setJudgeUsernames("");
    setMessage("Judges seeded.");
  };

  const handleFinalize = async () => {
    if (!seasonId) return;
    const data = await apiFetch<{ uid: string; sub_id: string; avg: number }[]>(
      `/admin/season/${seasonId}/finalize`,
      {
        method: "POST",
        body: JSON.stringify({ top_n: topN }),
      }
    );
    setWinners(data.map((winner) => `${winner.uid} (${winner.sub_id})`));
  };

  return (
    <RoleGate allow={["admin"]}>
      <div className="space-y-8">
        <div className="rounded-2xl border border-white/10 bg-card p-6">
          <h1 className="text-2xl font-semibold">Admin Console</h1>
          <form onSubmit={handleCreateSeason} className="mt-4 grid gap-3 md:grid-cols-3">
            <input
              value={newSeason}
              onChange={(event) => setNewSeason(event.target.value)}
              placeholder="Season ID"
              className="rounded-xl border border-white/10 bg-black/30 px-4 py-2"
            />
            <select
              value={status}
              onChange={(event) => setStatus(event.target.value)}
              className="rounded-xl border border-white/10 bg-black/30 px-4 py-2"
            >
              <option value="draft">draft</option>
              <option value="live">live</option>
              <option value="ended">ended</option>
              <option value="finalized">finalized</option>
            </select>
            <button type="submit" className="rounded-full bg-accent/20 px-4 py-2 text-sm">
              Create Season
            </button>
          </form>
          {message && (
            <div className="mt-4">
              <Toast message={message} variant={message.includes("failed") ? "error" : "success"} />
            </div>
          )}
        </div>

        <div className="rounded-2xl border border-white/10 bg-card p-6">
          <h2 className="text-xl font-semibold">Manage Season</h2>
          <div className="mt-4 max-w-sm">
            <SeasonPicker value={seasonId} onChange={setSeasonId} />
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <select
              value={status}
              onChange={(event) => setStatus(event.target.value)}
              className="rounded-xl border border-white/10 bg-black/30 px-4 py-2"
            >
              <option value="draft">draft</option>
              <option value="live">live</option>
              <option value="ended">ended</option>
              <option value="finalized">finalized</option>
            </select>
            <button onClick={handleStatusUpdate} className="rounded-full bg-accent/20 px-4 py-2 text-sm">
              Update Status
            </button>
          </div>
        </div>

        <div className="rounded-2xl border border-white/10 bg-card p-6">
          <h2 className="text-xl font-semibold">Seed Judges</h2>
          <textarea
            value={judgeUsernames}
            onChange={(event) => setJudgeUsernames(event.target.value)}
            rows={4}
            placeholder="one username per line"
            className="mt-3 w-full rounded-xl border border-white/10 bg-black/30 px-4 py-2"
          />
          <button onClick={handleSeedJudges} className="mt-3 rounded-full bg-accent/20 px-4 py-2 text-sm">
            Seed
          </button>
        </div>

        <div className="rounded-2xl border border-white/10 bg-card p-6">
          <h2 className="text-xl font-semibold">Moderation Queue</h2>
          {seasonId ? (
            <AdminModerationQueue sid={seasonId} submissions={queue} onRefresh={() => loadQueue(seasonId)} />
          ) : (
            <p className="mt-2 text-sm text-white/60">Select a season to view submissions.</p>
          )}
        </div>

        <div className="rounded-2xl border border-white/10 bg-card p-6">
          <h2 className="text-xl font-semibold">Finalize Season</h2>
          <div className="mt-4 flex items-center gap-3">
            <input
              type="number"
              min={1}
              max={100}
              value={topN}
              onChange={(event) => setTopN(Number(event.target.value))}
              className="w-24 rounded-xl border border-white/10 bg-black/30 px-3 py-2"
            />
            <button onClick={handleFinalize} className="rounded-full bg-accent/20 px-4 py-2 text-sm">
              Finalize
            </button>
          </div>
          {winners.length > 0 && (
            <ul className="mt-3 list-disc pl-5 text-sm text-white/70">
              {winners.map((winner) => (
                <li key={winner}>{winner}</li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </RoleGate>
  );
}
