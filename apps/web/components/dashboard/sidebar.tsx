"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { AXIOM_APP_NAME, AXIOM_VERSION } from "@axiom/shared";
import { ThemeToggle } from "@/components/theme-toggle";

const NAV = [
  { href: "/", label: "Overview" },
  { href: "/scrape", label: "Scrape" },
  { href: "/jobs", label: "Jobs" },
  { href: "/search", label: "Advanced Search" },
  { href: "/schedules", label: "Schedules" },
  { href: "/sources", label: "Sources" },
  { href: "/settings", label: "Settings" },
] as const;

function linkClass(pathname: string, href: string) {
  const active = href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
  return active
    ? "block rounded-lg bg-indigo-100 px-3 py-2 text-sm font-medium text-indigo-900 ring-1 ring-indigo-300 dark:bg-indigo-950/80 dark:text-indigo-200 dark:ring-indigo-800/60"
    : "block rounded-lg px-3 py-2 text-sm font-medium text-slate-600 transition hover:bg-surface-overlay hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200";
}

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside
      className="sticky top-0 flex h-screen w-60 shrink-0 flex-col border-r border-border-subtle bg-surface py-5"
      aria-label="Main navigation"
    >
      <div className="border-b border-border-subtle px-4 pb-4">
        <div className="text-sm font-semibold tracking-tight text-slate-100">{AXIOM_APP_NAME}</div>
        <div className="mt-0.5 text-[11px] font-medium uppercase tracking-wider text-slate-500">Dashboard</div>
      </div>
      <nav className="flex flex-1 flex-col gap-0.5 px-2 pt-4">
        {NAV.map((item) => (
          <Link key={item.href} href={item.href} className={linkClass(pathname, item.href)}>
            {item.label}
          </Link>
        ))}
      </nav>
      <div className="space-y-3 border-t border-border-subtle px-4 pt-4">
        <ThemeToggle className="w-full" />
        <div className="font-mono text-[11px] text-slate-500">v{AXIOM_VERSION}</div>
      </div>
    </aside>
  );
}
