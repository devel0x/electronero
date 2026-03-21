"use client";

import { useState } from "react";
import { apiFetch } from "../lib/api";
import { Submission } from "../lib/types";

export type JudgeSubmission = Submission & {
  judge_score?: number;
  judge_notes?: string;
};

export default function JudgeQueue({
  sid,
  submissions,
  onRefresh,
}: {
  sid: string;
  submissions: JudgeSubmission[];
  onRefresh: () => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);

  const submitScore = async (sid: string, subId: string, score: number, notes: string) => {
    setBusy(subId);
    try {
      await apiFetch(`/judge/season/${sid}/score/${subId}`, {
        method: "POST",
        body: JSON.stringify({ score, notes }),
      });
      onRefresh();
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-4">
      {submissions.map((submission) => (
        <div key={submission.sub_id} className="rounded-2xl border border-white/10 bg-card p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-white/60">Participant: {submission.uid}</p>
              <a href={submission.threads_url} target="_blank" className="text-accent">
                {submission.threads_url}
              </a>
            </div>
            <span className="rounded-full bg-white/10 px-3 py-1 text-xs">{submission.status}</span>
          </div>
          <div className="mt-4 grid gap-2 md:grid-cols-3">
            <input
              type="number"
              min={0}
              max={100}
              defaultValue={submission.judge_score ?? ""}
              placeholder="Score 0-100"
              className="rounded-lg border border-white/10 bg-black/30 px-3 py-2"
              id={`score-${submission.sub_id}`}
            />
            <input
              type="text"
              defaultValue={submission.judge_notes ?? ""}
              placeholder="Notes"
              className="rounded-lg border border-white/10 bg-black/30 px-3 py-2 md:col-span-2"
              id={`notes-${submission.sub_id}`}
            />
          </div>
          <button
            onClick={() => {
              const scoreInput = document.getElementById(
                `score-${submission.sub_id}`
              ) as HTMLInputElement;
              const notesInput = document.getElementById(
                `notes-${submission.sub_id}`
              ) as HTMLInputElement;
              submitScore(sid, submission.sub_id, Number(scoreInput.value), notesInput.value);
            }}
            className="mt-3 rounded-full border border-white/10 px-4 py-2 text-sm"
            disabled={busy === submission.sub_id}
          >
            {busy === submission.sub_id ? "Saving..." : "Submit Score"}
          </button>
        </div>
      ))}
    </div>
  );
}
