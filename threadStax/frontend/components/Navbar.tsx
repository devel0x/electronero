"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiFetch } from "../lib/api";
import { clearAuth, getAuth } from "../lib/auth";

const NAV_BY_ROLE: Record<string, { href: string; label: string }[]> = {
  admin: [
    { href: "/admin", label: "Admin" },
    { href: "/judge", label: "Judge" },
    { href: "/submit", label: "Submit" },
    { href: "/voter", label: "Vote" },
  ],
  judge: [{ href: "/judge", label: "Judge" }],
  participant: [{ href: "/submit", label: "Submit" }],
  voter: [{ href: "/voter", label: "Vote" }],
  moderator: [{ href: "/admin", label: "Moderation" }],
  auditor: [{ href: "/season/season-1/leaderboard", label: "Leaderboard" }],
  sponsor: [{ href: "/season/season-1/leaderboard", label: "Leaderboard" }],
};

export default function Navbar() {
  const [role, setRole] = useState<string | null>(null);

  useEffect(() => {
    const auth = getAuth();
    setRole(auth?.role ?? null);
  }, []);

  const handleLogout = async () => {
    try {
      await apiFetch("/auth/logout", { method: "POST" });
    } catch {
      // ignore
    }
    clearAuth();
    setRole(null);
  };

  const links = role ? NAV_BY_ROLE[role] || [] : [];

  return (
    <nav className="flex items-center justify-between border-b border-white/10 bg-[#05070f]/80 px-6 py-4">
      <Link href="/" className="text-lg font-semibold text-white">
        Threads Contest Engine
      </Link>
      <div className="flex items-center gap-4">
        {links.map((link) => (
          <Link key={link.href} href={link.href} className="text-sm text-white/80 hover:text-white">
            {link.label}
          </Link>
        ))}
        {!role && (
          <Link href="/login" className="rounded-full border border-white/20 px-4 py-2 text-sm">
            Login
          </Link>
        )}
        {role && (
          <button
            onClick={handleLogout}
            className="rounded-full border border-white/20 px-4 py-2 text-sm"
          >
            Logout
          </button>
        )}
      </div>
    </nav>
  );
}
