import type { Metadata } from "next";
import { RegisterForm } from "@/components/auth/register-form";

export const metadata: Metadata = {
  title: "Create account",
};

export default function RegisterPage() {
  return (
    <div className="w-full max-w-md space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-100">Create account</h1>
        <p className="mt-2 text-sm text-slate-500">Register your organization and start scraping.</p>
      </div>
      <RegisterForm />
    </div>
  );
}
