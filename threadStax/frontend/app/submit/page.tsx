"use client";

import { useEffect, useState } from "react";
import RoleGate from "../../components/RoleGate";
import SeasonPicker from "../../components/SeasonPicker";
import SubmissionCard from "../../components/SubmissionCard";
import Toast from "../../components/Toast";
import { apiFetch } from "../../lib/api";
import { Submission } from "../../lib/types";

export default function SubmitPage() {
  const [sid, setSid] = useState("");
  const [threadsUrl, setThreadsUrl] = useState("");
  const [codePhrase, setCodePhrase] = useState("");
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [message, setMessage] = useState<string | null>(null);

  const loadSubmissions = async (seasonId: string) => {
    if (!seasonId) return;
    const data = await apiFetch<Submission[]>(`/season/${seasonId}/submissions/mine`);
    setSubmissions(data);
  };

  useEffect(() => {
    if (sid) {
      loadSubmissions(sid).catch(() => setSubmissions([]));
    }
  }, [sid]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setMessage(null);
    try {
      await apiFetch(`/season/${sid}/submit`, {
        method: "POST",
        body: JSON.stringify({ threads_url: threadsUrl, code_phrase: codePhrase }),
      });
      setThreadsUrl("");
      setCodePhrase("");
      setMessage("Submission received!");
      loadSubmissions(sid);
    } catch {
      setMessage("Submission failed.");
    }
  };

  return (
    <RoleGate allow={["participant"]}>
      <div className="space-y-8">
        <div className="rounded-2xl border border-white/10 bg-card p-6">
          <h1 className="text-2xl font-semibold">Submit your entry</h1>
          <form onSubmit={handleSubmit} className="mt-4 space-y-4">
            <SeasonPicker value={sid} onChange={setSid} />
            <input
              value={threadsUrl}
              onChange={(event) => setThreadsUrl(event.target.value)}
              placeholder="Threads URL"
              className="w-full rounded-xl border border-white/10 bg-black/30 px-4 py-2"
              required
            />
            <input
              value={codePhrase}
              onChange={(event) => setCodePhrase(event.target.value)}
              placeholder="Code phrase"
              className="w-full rounded-xl border border-white/10 bg-black/30 px-4 py-2"
              required
            />
            <button type="submit" className="rounded-full bg-accent/20 px-5 py-2 text-sm">
              Submit
            </button>
          </form>
          {message && (
            <div className="mt-4">
              <Toast message={message} variant={message.includes("failed") ? "error" : "success"} />
            </div>
          )}
        </div>
        <div className="space-y-4">
          <h2 className="text-xl font-semibold">My submissions</h2>
          <div className="grid gap-4 md:grid-cols-2">
            {submissions.map((submission) => (
              <SubmissionCard key={submission.sub_id} submission={submission} />
            ))}
          </div>
        </div>
      </div>
    </RoleGate>
  );
}
