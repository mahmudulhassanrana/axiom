"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { apiFetch, setApiToken } from "@/lib/api";

type TokenResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
};

export function LoginForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [nextPath, setNextPath] = useState("/");

  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    const n = q.get("next");
    if (n && n.startsWith("/")) setNextPath(n);
  }, []);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const data = await apiFetch<TokenResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      setApiToken(data.access_token);
      toast.success("Signed in");
      router.push(nextPath);
      router.refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Sign in failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form
      onSubmit={onSubmit}
      className="space-y-4 rounded-xl border border-border-subtle bg-surface-raised/80 p-6 shadow-glow"
    >
      <label className="block">
        <span className="mb-1 block text-xs font-medium text-slate-400">Email</span>
        <input
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full rounded-lg border border-border-subtle bg-surface px-3 py-2 text-sm text-slate-100 focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
        />
      </label>
      <label className="block">
        <span className="mb-1 block text-xs font-medium text-slate-400">Password</span>
        <input
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full rounded-lg border border-border-subtle bg-surface px-3 py-2 text-sm text-slate-100 focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
        />
      </label>
      <button
        type="submit"
        disabled={loading}
        className="w-full rounded-lg bg-accent py-2.5 text-sm font-medium text-white shadow-lg shadow-indigo-950/50 hover:bg-accent-hover disabled:opacity-50"
      >
        {loading ? "Signing in…" : "Sign in"}
      </button>
      <p className="text-center text-xs text-slate-500">
        No account?{" "}
        <Link href="/register" className="font-medium text-accent hover:underline">
          Register
        </Link>
      </p>
    </form>
  );
}
