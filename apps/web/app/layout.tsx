import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { AXIOM_APP_NAME } from "@axiom/shared";
import { Providers } from "./providers";
import "./globals.css";

const geistSans = Geist({
  subsets: ["latin"],
  variable: "--font-geist-sans",
  display: "swap",
});

const geistMono = Geist_Mono({
  subsets: ["latin"],
  variable: "--font-geist-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: AXIOM_APP_NAME,
    template: `%s · ${AXIOM_APP_NAME}`,
  },
  description: "Compliant scraping and ingestion platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} min-h-screen antialiased bg-slate-950 text-slate-100`}
      >
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
