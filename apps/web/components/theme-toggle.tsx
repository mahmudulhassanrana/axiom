"use client";

import { useTheme } from "@/components/theme-provider";

type Props = {
  className?: string;
};

export function ThemeToggle({ className = "" }: Props) {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === "dark";

  return (
    <button
      type="button"
      onClick={toggleTheme}
      className={`rounded-lg border border-border-subtle bg-surface px-3 py-1.5 text-xs font-medium text-slate-300 transition hover:border-accent hover:text-accent ${className}`}
      aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
      title={isDark ? "Light mode" : "Dark mode"}
    >
      {isDark ? "Light mode" : "Dark mode"}
    </button>
  );
}
