"use client";

import dynamic from "next/dynamic";

/** Sonner injects portal/DOM that differs between SSR and the browser — load only on the client. */
const Toaster = dynamic(() => import("sonner").then((mod) => mod.Toaster), {
  ssr: false,
});

export function ToasterClient() {
  return <Toaster richColors position="top-right" closeButton />;
}
