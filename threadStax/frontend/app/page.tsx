"use client";

import Link from "next/link";
import { useState } from "react";
import SeasonPicker from "../components/SeasonPicker";

export default function Home() {
  const [sid, setSid] = useState("");

  return (
    <div className="space-y-10">
      <section className="rounded-3xl border border-white/10 bg-gradient-to-br from-[#0a1224] to-[#05070f] p-10 shadow-glow">
        <p className="text-sm uppercase text-accent/70">Threads Contest Engine</p>
        <h1 className="mt-4 text-4xl font-semibold">Launch your best Threads idea.</h1>
        <p className="mt-4 max-w-2xl text-white/70">
          Judge-driven challenges, community voting, and instant leaderboard updates. Build your
          entry, submit your code phrase, and climb to the top.
        </p>
        <div className="mt-6 flex flex-wrap gap-4">
          <Link href="/login" className="rounded-full bg-accent/20 px-5 py-2 text-sm">
            Login
          </Link>
          {sid && (
            <Link
              href={`/season/${sid}/leaderboard`}
              className="rounded-full border border-white/20 px-5 py-2 text-sm"
            >
              View Leaderboard
            </Link>
          )}
          {sid && (
            <Link
              href={`/submit?sid=${sid}`}
              className="rounded-full border border-white/20 px-5 py-2 text-sm"
            >
              Submit Entry
            </Link>
          )}
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        {[
          { title: "USDT Prize Pool", value: "$25,000" },
          { title: "ITC Rewards", value: "50,000 ITC" },
          { title: "Sponsor Bonuses", value: "Exclusive perks" },
        ].map((card) => (
          <div key={card.title} className="rounded-2xl border border-white/10 bg-card p-6">
            <p className="text-sm text-white/60">{card.title}</p>
            <h3 className="mt-2 text-2xl font-semibold">{card.value}</h3>
          </div>
        ))}
      </section>

      <section className="rounded-2xl border border-white/10 bg-card p-6">
        <h2 className="text-xl font-semibold">Pick a season</h2>
        <p className="mt-2 text-sm text-white/60">Select an active season to explore.</p>
        <div className="mt-4 max-w-sm">
          <SeasonPicker value={sid} onChange={setSid} />
        </div>
      </section>
    </div>
  );
}
