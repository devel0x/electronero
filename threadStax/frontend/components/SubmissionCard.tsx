import { Submission } from "../lib/types";

export default function SubmissionCard({ submission }: { submission: Submission }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-card p-4 shadow-glow">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Submission {submission.sub_id.slice(0, 6)}</h3>
        <span className="rounded-full bg-white/10 px-3 py-1 text-xs uppercase">
          {submission.status}
        </span>
      </div>
      <p className="mt-2 text-sm text-white/70">{submission.threads_url}</p>
      <p className="mt-2 text-xs text-white/60">Code phrase: {submission.code_phrase}</p>
      {submission.agg_score !== undefined && (
        <p className="mt-2 text-sm">Avg Score: {submission.agg_score.toFixed(2)}</p>
      )}
    </div>
  );
}
