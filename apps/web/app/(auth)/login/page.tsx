import type { Metadata } from "next";
import { LoginForm } from "@/components/auth/login-form";

export const metadata: Metadata = {
  title: "Sign in",
};

export default function LoginPage() {
  return (
    <div className="w-full max-w-md space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-100">Sign in</h1>
        <p className="mt-2 text-sm text-slate-500">Use your Axiom account to access the dashboard.</p>
      </div>
      <LoginForm />
    </div>
  );
}
