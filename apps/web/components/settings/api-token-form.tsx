"use client";

import { useEffect, useState } from "react";
import { getApiToken, setApiToken, STORAGE_TOKEN_KEY } from "@/lib/api";

export function ApiTokenForm() {
  const [token, setToken] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setToken(getApiToken() ?? "");
  }, []);

  function save(e: React.FormEvent) {
    e.preventDefault();
    setApiToken(token.trim() || null);
    setSaved(true);
    window.setTimeout(() => setSaved(false), 2000);
  }

  function clear() {
    setToken("");
    setApiToken(null);
  }

  return (
    <form
      onSubmit={save}
      className="rounded-xl border border-border-subtle bg-surface-raised/80 p-5 shadow-glow"
    >
      <h2 className="text-sm font-semibold text-slate-200">API token</h2>
      <p className="mt-1 text-xs leading-relaxed text-slate-500">
        If API requests return <span className="font-medium text-slate-400">401</span>, paste a JWT from{" "}
        <code className="rounded bg-surface px-1 py-0.5 font-mono text-[11px] text-slate-400">POST /auth/login</code>{" "}
        or use an API key as the Bearer value (when your deployment supports it), then save. Stored only in this
        browser (<code className="font-mono text-[11px]">{STORAGE_TOKEN_KEY}</code>).
      </p>
      <textarea
        value={token}
        onChange={(e) => setToken(e.target.value)}
        rows={3}
        placeholder="eyJ…"
        className="mt-4 w-full resize-y rounded-lg border border-border-subtle bg-surface px-3 py-2 font-mono text-xs text-slate-200 placeholder:text-slate-600 focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
        autoComplete="off"
      />
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <button
          type="submit"
          className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover"
        >
          Save token
        </button>
        <button
          type="button"
          onClick={clear}
          className="rounded-lg border border-border-subtle px-4 py-2 text-sm text-slate-400 hover:border-slate-500 hover:text-slate-200"
        >
          Clear
        </button>
        {saved ? <span className="text-xs text-emerald-400">Saved.</span> : null}
      </div>
    </form>
  );
}
