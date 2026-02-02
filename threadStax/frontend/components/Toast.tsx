"use client";

import { cx } from "../lib/utils";

export default function Toast({
  message,
  variant = "success",
}: {
  message: string;
  variant?: "success" | "error";
}) {
  return (
    <div
      className={cx(
        "rounded-xl border px-4 py-2 text-sm",
        variant === "success"
          ? "border-emerald-400/40 bg-emerald-500/10 text-emerald-100"
          : "border-red-400/40 bg-red-500/10 text-red-100"
      )}
    >
      {message}
    </div>
  );
}
