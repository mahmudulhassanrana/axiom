"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ThemeToggle } from "@/components/theme-toggle";
import { apiFetch, getApiToken, setApiToken } from "@/lib/api";

type Me = {
  email: string;
  role: string;
};

type HeaderProps = {
  title: string;
  description?: string;
};

export function Header({ title, description }: HeaderProps) {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);

  const load = useCallback(async () => {
    if (!getApiToken()) return;
    try {
      const u = await apiFetch<Me>("/auth/me");
      setMe(u);
    } catch {
      setMe(null);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  function logout() {
    setApiToken(null);
    setMe(null);
    router.replace("/login");
    router.refresh();
  }

  return (
    <header className="sticky top-0 z-10 flex h-14 shrink-0 items-center justify-between gap-4 border-b border-border-subtle bg-surface/90 px-6 backdrop-blur-md lg:px-10">
      <div className="flex min-w-0 flex-col gap-0.5">
        <span className="truncate text-sm font-semibold tracking-tight text-slate-100">{title}</span>
        {description ? (
          <span className="hidden text-xs text-slate-500 sm:inline">{description}</span>
        ) : null}
      </div>
      <div className="flex shrink-0 items-center gap-3">
        <ThemeToggle />
        {me ? (
          <span className="hidden max-w-[200px] truncate text-xs text-slate-500 sm:inline" title={me.email}>
            {me.email}
          </span>
        ) : null}
        <button
          type="button"
          onClick={logout}
          className="rounded-lg border border-border-subtle px-3 py-1.5 text-xs font-medium text-slate-300 transition hover:border-border hover:text-slate-100"
        >
          Log out
        </button>
      </div>
    </header>
  );
}
