"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getApiToken } from "@/lib/api";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const token = getApiToken();
    if (!token) {
      const next = `${pathname}${typeof window !== "undefined" ? window.location.search : ""}`;
      router.replace(`/login?next=${encodeURIComponent(next)}`);
      return;
    }
    setReady(true);
  }, [router, pathname]);

  if (!ready) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center text-sm text-slate-500">
        <div className="flex flex-col items-center gap-2">
          <span className="h-8 w-8 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" aria-hidden />
          <span>Checking session…</span>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
