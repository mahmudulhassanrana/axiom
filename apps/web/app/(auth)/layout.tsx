import type { ReactNode } from "react";
import Link from "next/link";
import { AXIOM_APP_NAME } from "@axiom/shared";
import { ThemeToggle } from "@/components/theme-toggle";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <header className="flex items-center justify-between border-b border-border-subtle px-6 py-4 lg:px-10">
        <Link href="/" className="text-sm font-semibold text-slate-100 hover:text-accent">
          {AXIOM_APP_NAME}
        </Link>
        <ThemeToggle />
      </header>
      <div className="flex flex-1 items-center justify-center px-4 py-12">{children}</div>
    </div>
  );
}
