import type { Metadata } from "next";
import { ApiTokenForm } from "@/components/settings/api-token-form";
import { UserProfileCard } from "@/components/settings/user-profile-card";

export const metadata: Metadata = {
  title: "Settings",
};

export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <p className="max-w-2xl text-sm leading-relaxed text-slate-400">
        Session uses a JWT stored in the browser. You can paste a token manually for debugging or switch accounts. If
        the dashboard shows <span className="text-slate-300">401 Unauthorized</span>, open Settings here and save a
        valid Bearer token (JWT from login or an API key your server accepts as Bearer).
      </p>
      <UserProfileCard />
      <ApiTokenForm />
    </div>
  );
}
