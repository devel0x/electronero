"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "../../lib/api";
import { setAuth } from "../../lib/auth";
import Toast from "../../components/Toast";
import { Role } from "../../lib/types";

const roles: Role[] = [
  "admin",
  "judge",
  "participant",
  "voter",
  "moderator",
  "auditor",
  "sponsor",
];

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [role, setRole] = useState<Role>("participant");
  const [error, setError] = useState("");

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    try {
      const data = await apiFetch<{ uid: string; token: string; role: Role }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, role }),
      });
      setAuth({ uid: data.uid, token: data.token, role: data.role });
      router.push("/");
    } catch (err) {
      setError("Login failed. Try again.");
    }
  };

  return (
    <div className="mx-auto max-w-md rounded-2xl border border-white/10 bg-card p-8">
      <h1 className="text-2xl font-semibold">Login</h1>
      <p className="mt-2 text-sm text-white/60">Enter a username and pick your role.</p>
      <form onSubmit={handleSubmit} className="mt-6 space-y-4">
        <input
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          placeholder="Username"
          className="w-full rounded-xl border border-white/10 bg-black/30 px-4 py-2"
          required
        />
        <select
          value={role}
          onChange={(event) => setRole(event.target.value as Role)}
          className="w-full rounded-xl border border-white/10 bg-black/30 px-4 py-2"
        >
          {roles.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
        <button type="submit" className="w-full rounded-full bg-accent/20 px-4 py-2">
          Continue
        </button>
      </form>
      {error && <div className="mt-4"><Toast message={error} variant="error" /></div>}
    </div>
  );
}
