"use client";

import { ToasterClient } from "@/components/toaster-client";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <>
      {children}
      <ToasterClient />
    </>
  );
}
