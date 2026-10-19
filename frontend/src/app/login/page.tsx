"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { inputStyles } from "@/components/ui";
import { apiPost, type CurrentUser } from "@/lib/api";
import { currentUser, HOME_FOR_ROLE, safeNextPath } from "@/lib/session";

// Customer sign-in. Registration: lookup -> contact details -> code from email -> done.
// Returning customers: email -> code -> done. Step tokens come from the server and are
// only passed back, so the browser cannot choose a customer number.

type Step = "lookup" | "contact" | "code" | "login-email" | "login-code" | "done";
type Notice = { tone: "error" | "info" | "success"; text: string };

const ALREADY_REGISTERED = "An account already exists for these details. Please log in instead.";
const label = "mb-1.5 block text-[13px] font-medium text-ink-soft";
const field = "mb-4 h-10 w-full " + inputStyles;

export default function CustomerLoginPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("lookup");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [resendIn, setResendIn] = useState(0);
  const [token, setToken] = useState("");
  const [emailHint, setEmailHint] = useState("");
  const [loginEmail, setLoginEmail] = useState("");

  // Already signed in: send each role to its own home.
  useEffect(() => {
    currentUser().then((user) => {
      if (user) router.replace(user.role === "admin" ? HOME_FOR_ROLE.admin : safeNextPath(HOME_FOR_ROLE.end_user));
    });
  }, [router]);

  // Counts down the resend cooldown. The server enforces it too.
  useEffect(() => {
    if (resendIn <= 0) return;
    const timer = setTimeout(() => setResendIn((n) => n - 1), 1000);
    return () => clearTimeout(timer);
  }, [resendIn]);

  function restart(next: "lookup" | "login-email") {
    setStep(next);
    setNotice(null);
    setResendIn(0);
  }

  /** Runs one API call with a busy flag. A failure is shown as a message and returns null. */
  async function call<T>(action: () => Promise<T>): Promise<T | null> {
    setBusy(true);
    setNotice(null);
    try {
      return await action();
    } catch (e) {
      setNotice({ tone: "error", text: e instanceof Error ? e.message : "Something went wrong." });
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function submitLookup(form: FormData) {
    const result = await call(() =>
      apiPost<{ status: string; message: string; registration_token: string | null }>(
        "/api/auth/register/lookup",
        { first_name: form.get("first_name"), last_name: form.get("last_name"), ssn: form.get("ssn") },
        false,
      ),
    );
    if (!result) return;
    if (result.status === "matched" && result.registration_token) {
      setToken(result.registration_token);
      setNotice({ tone: "success", text: result.message });
      setStep("contact");
    } else {
      setNotice({ tone: result.status === "needs_review" ? "info" : "error", text: result.message });
    }
  }

  async function submitContact(form: FormData) {
    const sent = await call(() =>
      apiPost<{ verification_token: string; email_masked: string; resend_after_seconds: number }>(
        "/api/auth/register/send-code",
        { registration_token: token, email: form.get("email"), phone: form.get("phone") },
        false,
      ),
    );
    if (!sent) return;
    setToken(sent.verification_token);
    setEmailHint(sent.email_masked);
    setResendIn(sent.resend_after_seconds);
    setNotice({ tone: "info", text: "We sent a code to your email." });
    setStep("code");
  }

  async function submitRegistrationCode(form: FormData) {
    const user = await call(() =>
      apiPost<CurrentUser>("/api/auth/register/verify", { verification_token: token, code: form.get("code") }, false),
    );
    if (user) setStep("done");
  }

  async function resendRegistrationCode() {
    const result = await call(() =>
      apiPost<{ message: string; resend_after_seconds: number }>(
        "/api/auth/register/resend-code",
        { verification_token: token },
        false,
      ),
    );
    if (result) {
      setResendIn(result.resend_after_seconds);
      setNotice({ tone: "success", text: "A new code was sent to your email." });
    }
  }

  async function requestLoginCode(email: string) {
    const result = await call(() =>
      apiPost<{ login_token: string; email_masked: string; expires_in_seconds: number }>(
        "/api/auth/login/request",
        { email },
        false,
      ),
    );
    if (!result) return;
    setLoginEmail(email);
    setToken(result.login_token);
    setEmailHint(result.email_masked);
    setResendIn(60);
    setNotice({ tone: "info", text: `If an account exists, we sent a code to ${result.email_masked}.` });
    setStep("login-code");
  }

  async function submitLoginCode(form: FormData) {
    const user = await call(() =>
      apiPost<CurrentUser>("/api/auth/login/verify", { login_token: token, code: form.get("code") }, false),
    );
    if (user) router.replace(safeNextPath(HOME_FOR_ROLE.end_user));
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const actions: Partial<Record<Step, () => unknown>> = {
      lookup: () => submitLookup(form),
      contact: () => submitContact(form),
      code: () => submitRegistrationCode(form),
      "login-email": () => requestLoginCode(String(form.get("email") ?? "").trim()),
      "login-code": () => submitLoginCode(form),
    };
    actions[step]?.();
  }

  if (step === "done") {
    return (
      <Shell>
        <div className="rounded-lg border border-rule bg-surface p-6 sm:p-8">
          <h1 className="text-[20px] font-semibold tracking-[-0.02em]">You&apos;re all set</h1>
          <p className="mt-1 mb-6 text-muted">Your account is ready and you are signed in.</p>
          <Link
            href={HOME_FOR_ROLE.end_user}
            className="flex h-10 w-full items-center justify-center rounded-md bg-signal font-medium text-white hover:bg-signal-lift"
          >
            Go to my invoices
          </Link>
        </div>
      </Shell>
    );
  }

  const isRegistering = step === "lookup" || step === "contact" || step === "code";

  return (
    <Shell>
      <form onSubmit={handleSubmit} className="rounded-lg border border-rule bg-surface p-6 sm:p-8">
        <Heading step={step} emailHint={emailHint} />

        {notice && (
          <p
            role={notice.tone === "error" ? "alert" : "status"}
            className={`mb-5 rounded-md border px-3 py-2 text-[13.5px] ${
              notice.tone === "error"
                ? "border-negative/25 bg-negative-tint text-negative"
                : notice.tone === "success"
                  ? "border-positive/25 bg-positive-tint text-positive"
                  : "border-rule bg-paper text-ink-soft"
            }`}
          >
            {notice.text}
            {notice.text === ALREADY_REGISTERED && (
              <>
                {" "}
                <button type="button" onClick={() => restart("login-email")} className="font-medium underline">
                  Log in instead
                </button>
              </>
            )}
          </p>
        )}

        {step === "lookup" && <LookupFields />}
        {step === "contact" && <ContactFields />}
        {step === "code" && (
          <>
            <label htmlFor="code" className={label}>Code from email</label>
            <input id="code" name="code" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" required className={field} />
            <ResendButton disabled={busy || resendIn > 0} onClick={resendRegistrationCode} />
          </>
        )}
        {step === "login-email" && (
          <>
            <label htmlFor="email" className={label}>Email</label>
            <input id="email" name="email" type="email" autoComplete="username" required maxLength={254} className={field} />
          </>
        )}
        {step === "login-code" && (
          <>
            <label htmlFor="code" className={label}>Code from email</label>
            <input id="code" name="code" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" required className={field} />
            <ResendButton disabled={busy || resendIn > 0} onClick={() => requestLoginCode(loginEmail)} />
          </>
        )}
        {(step === "code" || step === "login-code") && resendIn > 0 && (
          <p className="mt-2 text-[13px] text-muted">You can request a new code in {resendIn} seconds.</p>
        )}

        <button
          type="submit"
          disabled={busy}
          className="mt-6 flex h-10 w-full items-center justify-center gap-2 rounded-md bg-signal font-medium text-white hover:bg-signal-lift disabled:opacity-70"
        >
          {busy && <Loader2 size={16} aria-hidden className="animate-spin" />}
          {busy ? "Please wait…" : submitLabel(step)}
        </button>

        {(step === "contact" || step === "code" || step === "login-code") && (
          <button
            type="button"
            onClick={() => restart(isRegistering ? "lookup" : "login-email")}
            className="mt-3 w-full text-center text-[13.5px] font-medium text-ink-soft hover:text-ink"
          >
            Start over
          </button>
        )}
      </form>

      <p className="mt-6 text-center text-[13.5px] text-muted">
        {isRegistering ? (
          <>
            Already registered?{" "}
            <button type="button" onClick={() => restart("login-email")} className="font-medium text-ink underline-offset-2 hover:underline">
              Log in with email
            </button>
          </>
        ) : (
          <>
            New customer?{" "}
            <button type="button" onClick={() => restart("lookup")} className="font-medium text-ink underline-offset-2 hover:underline">
              Create your account
            </button>
          </>
        )}
      </p>
      <p className="mt-3 text-center text-[13px] text-muted">
        Staff?{" "}
        <Link href="/admin" className="underline-offset-2 hover:underline">
          Admin sign in
        </Link>
      </p>
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-10">
      <div className="w-full max-w-[420px]">
        <div className="mb-8 flex items-center justify-center gap-2.5">
          <span aria-hidden className="flex h-9 w-9 items-center justify-center rounded-md bg-signal text-[15px] font-bold text-white">
            B
          </span>
          <span className="text-[16px] font-semibold">BND Reporting</span>
        </div>
        {children}
      </div>
    </main>
  );
}

function Heading({ step, emailHint }: { step: Exclude<Step, "done">; emailHint: string }) {
  const copy: Record<Exclude<Step, "done">, { title: string; subtitle: string }> = {
    lookup: { title: "Create your account", subtitle: "Enter your name and Social Security number to find your account." },
    contact: { title: "Add your contact details", subtitle: "We send a one-time code to your email. Your phone number is saved for contact." },
    code: { title: "Enter your code", subtitle: `Enter the 6-digit code sent to ${emailHint}. It expires in 10 minutes.` },
    "login-email": { title: "Log in", subtitle: "Enter the email address you registered with." },
    "login-code": { title: "Enter your code", subtitle: `Enter the 6-digit code sent to ${emailHint}. It expires in 10 minutes.` },
  };
  return (
    <>
      <h1 className="text-[20px] font-semibold tracking-[-0.02em]">{copy[step].title}</h1>
      <p className="mt-1 mb-6 text-muted">{copy[step].subtitle}</p>
    </>
  );
}

function submitLabel(step: Step) {
  switch (step) {
    case "lookup":
      return "Find my account";
    case "contact":
      return "Send code";
    case "code":
    case "login-code":
      return "Verify and continue";
    case "login-email":
      return "Send me a code";
    default:
      return "Continue";
  }
}

function LookupFields() {
  return (
    <>
      <label htmlFor="first_name" className={label}>First name</label>
      <input id="first_name" name="first_name" autoComplete="given-name" required maxLength={100} className={field} />
      <label htmlFor="last_name" className={label}>Last name</label>
      <input id="last_name" name="last_name" autoComplete="family-name" required minLength={3} maxLength={100} className={field} />
      <label htmlFor="ssn" className={label}>Social Security number</label>
      <input
        id="ssn"
        name="ssn"
        type="password"
        inputMode="numeric"
        autoComplete="off"
        required
        maxLength={20}
        placeholder="with or without hyphens"
        className={field}
      />
    </>
  );
}

function ContactFields() {
  return (
    <>
      <label htmlFor="email" className={label}>Email</label>
      <input id="email" name="email" type="email" autoComplete="email" required maxLength={254} className={field} />
      <label htmlFor="phone" className={label}>Mobile phone (saved for contact)</label>
      <input id="phone" name="phone" type="tel" autoComplete="tel" required maxLength={25} placeholder="+1 555 010 0100" className={field} />
    </>
  );
}

function ResendButton({ disabled, onClick }: { disabled: boolean; onClick: () => void }) {
  return (
    <button type="button" disabled={disabled} onClick={onClick} className="text-[13.5px] font-medium text-ink-soft underline-offset-2 hover:underline disabled:opacity-50">
      Send a new code
    </button>
  );
}
