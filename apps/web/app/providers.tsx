"use client";

import { ThemeProvider } from "@/components/theme-provider";
import { ToasterClient } from "@/components/toaster-client";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      {children}
      <ToasterClient />
    </ThemeProvider>
  );
}
