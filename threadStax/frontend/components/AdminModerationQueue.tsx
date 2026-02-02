"use client";

import { useState } from "react";
import { apiFetch } from "../lib/api";
import { Submission } from "../lib/types";

export default function AdminModerationQueue({
  sid,
  submissions,
  onRefresh,
}: {
  sid: string;
  submissions: Submission[];
  onRefresh: () => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);

  const handleApprove = async (subId: string) => {
    setBusy(subId);
    try {
      await apiFetch(`/admin/season/${sid}/submissions/${subId}/approve`, {
        method: "POST",
      });
      onRefresh();
    } finally {
      setBusy(null);
    }
  };

  const handleReject = async (subId: string) => {
    const reason = prompt("Reason for rejection?") || "";
    setBusy(subId);
    try {
      await apiFetch(`/admin/season/${sid}/submissions/${subId}/reject`, {
        method: "POST",
        body: JSON.stringify({ reason }),
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
          <p className="text-sm text-white/60">{submission.uid}</p>
          <a href={submission.threads_url} target="_blank" className="text-accent">
            {submission.threads_url}
          </a>
          <div className="mt-3 flex gap-2">
            <button
              onClick={() => handleApprove(submission.sub_id)}
              className="rounded-full border border-white/10 px-4 py-2 text-sm"
              disabled={busy === submission.sub_id}
            >
              Approve
            </button>
            <button
              onClick={() => handleReject(submission.sub_id)}
              className="rounded-full border border-red-400/50 px-4 py-2 text-sm text-red-200"
              disabled={busy === submission.sub_id}
            >
              Reject
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
