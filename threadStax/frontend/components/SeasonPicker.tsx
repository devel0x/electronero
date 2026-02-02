"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "../lib/api";
import { Season } from "../lib/types";

export default function SeasonPicker({
  value,
  onChange,
}: {
  value?: string;
  onChange: (sid: string) => void;
}) {
  const [seasons, setSeasons] = useState<Season[]>([]);

  useEffect(() => {
    apiFetch<Season[]>("/season")
      .then(setSeasons)
      .catch(() => setSeasons([]));
  }, []);

  return (
    <select
      value={value}
      onChange={(event) => onChange(event.target.value)}
      className="w-full rounded-xl border border-white/10 bg-card px-4 py-2 text-white"
    >
      <option value="">Select season</option>
      {seasons.map((season) => (
        <option key={season.sid} value={season.sid}>
          {season.sid} ({season.status})
        </option>
      ))}
    </select>
  );
}
