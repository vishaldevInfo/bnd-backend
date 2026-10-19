"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import { inputStyles } from "@/components/ui";
import { apiPost, type CurrentUser } from "@/lib/api";
import { currentUser, HOME_FOR_ROLE, safeNextPath } from "@/lib/session";

export default function AdminLoginPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  // Already signed in as an admin: go straight to the dashboard.
  useEffect(() => {
    currentUser().then((user) => {
      if (user?.role === "admin") router.replace(HOME_FOR_ROLE.admin);
    });
  }, [router]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setSubmitting(true);
    setError(null);
    try {
      await apiPost<CurrentUser>(
        "/api/admin/login",
        { email: form.get("email"), password: form.get("password") },
        false,
      );
      router.replace(safeNextPath(HOME_FOR_ROLE.admin));
    } catch (e) {
      // The backend never says whether the email or the password was wrong.
      setError(e instanceof Error ? e.message : "Sign in failed.");
      setSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-10">
      <div className="w-full max-w-[400px]">
        <div className="mb-8 flex items-center justify-center gap-2.5">
          <span
            aria-hidden
            className="flex h-9 w-9 items-center justify-center rounded-md bg-signal text-[15px] font-bold text-white"
          >
            B
          </span>
          <span className="text-[16px] font-semibold">BND Reporting</span>
        </div>

        <form onSubmit={handleSubmit} className="rounded-lg border border-rule bg-surface p-6 sm:p-8">
          <h1 className="text-[20px] font-semibold tracking-[-0.02em]">Admin sign in</h1>
          <p className="mt-1 mb-6 text-muted">Enter your administrator email and password.</p>

          {error && (
            <p
              role="alert"
              className="mb-5 rounded-md border border-negative/25 bg-negative-tint px-3 py-2 text-[13.5px] text-negative"
            >
              {error}
            </p>
          )}

          <label htmlFor="email" className="mb-1.5 block text-[13px] font-medium text-ink-soft">
            Email
          </label>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="username"
            required
            autoFocus
            aria-invalid={Boolean(error)}
            className={`${inputStyles} mb-4 h-10 w-full`}
          />

          <label htmlFor="password" className="mb-1.5 block text-[13px] font-medium text-ink-soft">
            Password
          </label>
          <div className="relative mb-6">
            <input
              id="password"
              name="password"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              required
              aria-invalid={Boolean(error)}
              className={`${inputStyles} h-10 w-full pr-11`}
            />
            <button
              type="button"
              onClick={() => setShowPassword((v) => !v)}
              aria-label={showPassword ? "Hide password" : "Show password"}
              aria-pressed={showPassword}
              className="absolute inset-y-0 right-0 flex w-10 items-center justify-center rounded-r-md text-muted hover:text-ink"
            >
              {showPassword ? <EyeOff size={17} aria-hidden /> : <Eye size={17} aria-hidden />}
            </button>
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="flex h-10 w-full items-center justify-center gap-2 rounded-md bg-signal font-medium text-white hover:bg-signal-lift disabled:opacity-70"
          >
            {submitting && <Loader2 size={16} aria-hidden className="animate-spin" />}
            {submitting ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <p className="mt-6 text-center text-[13.5px] text-muted">
          Customer?{" "}
          <Link href="/login" className="font-medium text-ink underline-offset-2 hover:underline">
            Sign in here
          </Link>
        </p>
      </div>
    </main>
  );
}
