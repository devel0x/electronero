"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getAuth } from "../lib/auth";

export default function RoleGate({
  allow,
  children,
}: {
  allow: string[];
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [authorized, setAuthorized] = useState(false);

  useEffect(() => {
    const auth = getAuth();
    if (!auth || !allow.includes(auth.role)) {
      router.push("/login");
      return;
    }
    setAuthorized(true);
  }, [allow, router]);

  if (!authorized) return null;
  return <>{children}</>;
}
