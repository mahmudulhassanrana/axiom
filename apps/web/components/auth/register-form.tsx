"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { apiFetch, setApiToken } from "@/lib/api";

type RegisterResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: { email: string };
};

export function RegisterForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const data = await apiFetch<RegisterResponse>("/auth/register", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      setApiToken(data.access_token);
      toast.success("Account created");
      router.push("/");
      router.refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Registration failed");
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
        <span className="mb-1 block text-xs font-medium text-slate-400">Password (min 8 characters)</span>
        <input
          type="password"
          autoComplete="new-password"
          required
          minLength={8}
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
        {loading ? "Creating…" : "Create account"}
      </button>
      <p className="text-center text-xs text-slate-500">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-accent hover:underline">
          Sign in
        </Link>
      </p>
    </form>
  );
}
