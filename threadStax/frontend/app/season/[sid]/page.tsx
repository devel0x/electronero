"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { apiFetch } from "../../../lib/api";
import { Season } from "../../../lib/types";

export default function SeasonPage() {
  const params = useParams<{ sid: string }>();
  const sid = params?.sid as string;
  const [season, setSeason] = useState<Season | null>(null);

  useEffect(() => {
    apiFetch<Season>(`/season/${sid}`)
      .then(setSeason)
      .catch(() => setSeason(null));
  }, [sid]);

  if (!season) {
    return <p className="text-white/60">Loading season...</p>;
  }

  return (
    <div className="rounded-2xl border border-white/10 bg-card p-6">
      <h1 className="text-2xl font-semibold">Season {season.sid}</h1>
      <p className="mt-2 text-white/60">Status: {season.status}</p>
      <p className="mt-2 text-white/60">Created: {season.created_at}</p>
    </div>
  );
}
