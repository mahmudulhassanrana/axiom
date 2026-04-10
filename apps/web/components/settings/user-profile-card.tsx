"use client";

import { useCallback, useEffect, useState } from "react";
import { FormattedDate } from "@/components/formatted-date";
import { apiFetch } from "@/lib/api";

type User = {
  id: string;
  email: string;
  role: string;
  created_at: string;
};

export function UserProfileCard() {
  const [user, setUser] = useState<User | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const u = await apiFetch<User>("/auth/me");
      setUser(u);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load profile");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (error) {
    return (
      <div className="rounded-xl border border-amber-900/50 bg-amber-950/30 px-4 py-3 text-sm text-amber-200">{error}</div>
    );
  }

  if (!user) {
    return (
      <div className="rounded-xl border border-border-subtle bg-surface-raised/50 px-6 py-8 text-center text-sm text-slate-500">
        Loading profile…
      </div>
    );
  }

  return (
    <section className="rounded-xl border border-border-subtle bg-surface-raised/80 p-5 shadow-glow">
      <h2 className="text-sm font-semibold text-slate-200">Account</h2>
      <dl className="mt-4 space-y-2 text-sm">
        <div>
          <dt className="text-xs uppercase tracking-wide text-slate-500">Email</dt>
          <dd className="text-slate-200">{user.email}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-slate-500">Role</dt>
          <dd className="text-slate-200">{user.role}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-slate-500">Member since</dt>
          <dd className="text-slate-400">
            <FormattedDate iso={user.created_at} />
          </dd>
        </div>
      </dl>
    </section>
  );
}
