"use client";

type Props = {
  iso: string | null | undefined;
  fallback?: string;
  className?: string;
};

/** Locale-formatted date; ``suppressHydrationWarning`` avoids SSR/client locale/timezone mismatches. */
export function FormattedDate({ iso, fallback = "—", className }: Props) {
  if (iso == null || iso === "") {
    return <span className={className}>{fallback}</span>;
  }
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) {
    return <span className={className}>{fallback}</span>;
  }
  return (
    <span className={className} suppressHydrationWarning>
      {d.toLocaleString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })}
    </span>
  );
}
