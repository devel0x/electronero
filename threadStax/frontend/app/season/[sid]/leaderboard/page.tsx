"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import LeaderboardTable from "../../../../components/LeaderboardTable";
import { apiFetch } from "../../../../lib/api";
import { LeaderboardEntry } from "../../../../lib/types";

export default function LeaderboardPage() {
  const params = useParams<{ sid: string }>();
  const sid = params?.sid as string;
  const [tab, setTab] = useState<"judges" | "votes">("judges");
  const [entries, setEntries] = useState<LeaderboardEntry[]>([]);

  useEffect(() => {
    apiFetch<LeaderboardEntry[]>(`/season/${sid}/leaderboard/${tab}`)
      .then(setEntries)
      .catch(() => setEntries([]));
  }, [sid, tab]);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <button
          onClick={() => setTab("judges")}
          className={`rounded-full px-4 py-2 text-sm ${
            tab === "judges" ? "bg-accent/20" : "border border-white/10"
          }`}
        >
          Judges
        </button>
        <button
          onClick={() => setTab("votes")}
          className={`rounded-full px-4 py-2 text-sm ${
            tab === "votes" ? "bg-accent/20" : "border border-white/10"
          }`}
        >
          Votes
        </button>
      </div>
      <LeaderboardTable entries={entries} label={tab === "judges" ? "Score" : "Votes"} />
    </div>
  );
}
