"use client";

import { useEffect, useState } from "react";
import RoleGate from "../../components/RoleGate";
import SeasonPicker from "../../components/SeasonPicker";
import JudgeQueue, { JudgeSubmission } from "../../components/JudgeQueue";
import { apiFetch } from "../../lib/api";

export default function JudgePage() {
  const [sid, setSid] = useState("");
  const [submissions, setSubmissions] = useState<JudgeSubmission[]>([]);

  const loadQueue = async (seasonId: string) => {
    if (!seasonId) return;
    const data = await apiFetch<JudgeSubmission[]>(`/judge/season/${seasonId}/assigned`);
    setSubmissions(data);
  };

  useEffect(() => {
    if (sid) {
      loadQueue(sid).catch(() => setSubmissions([]));
    }
  }, [sid]);

  return (
    <RoleGate allow={["judge"]}>
      <div className="space-y-6">
        <div className="rounded-2xl border border-white/10 bg-card p-6">
          <h1 className="text-2xl font-semibold">Judge Queue</h1>
          <p className="mt-2 text-white/60">Select a season to score submissions.</p>
          <div className="mt-4 max-w-sm">
            <SeasonPicker value={sid} onChange={setSid} />
          </div>
        </div>
        {sid && <JudgeQueue sid={sid} submissions={submissions} onRefresh={() => loadQueue(sid)} />}
      </div>
    </RoleGate>
  );
}
