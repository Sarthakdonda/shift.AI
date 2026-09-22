"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { ArrowRight, AtSign, LoaderCircle, MailCheck } from "lucide-react";
import { Screen } from "@/components/shell/screen";
import { Field } from "@/components/auth/field";
import { ErrorNote } from "@/components/ui/states";
import { requestPasswordReset, type ResetRequest } from "@/lib/auth";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState("");
  const [sent, setSent] = useState<ResetRequest | null>(null);
  const emailError = !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())
    ? "Enter a valid email address."
    : "";

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setSubmitted(true);
    setError("");
    if (emailError) {
      document.getElementById("reset-email")?.focus();
      return;
    }
    setBusy(true);
    try {
      setSent(await requestPasswordReset(email.trim()));
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Screen title="Reset password" back="/login">
      <div className="access" style={{ padding: 0 }}>
        <div className="access-brand">
          <div>
            <p className="eyebrow">Account recovery</p>
            <h1 style={{ marginTop: 6 }}>
              {sent ? "Check your email." : "Reset your password."}
            </h1>
            <p>
              {sent
                ? "The link works once and expires shortly, so open it soon."
                : "Enter the email on your account and we’ll send a secure reset link."}
            </p>
          </div>
        </div>

        {sent ? (
          <div className="access-card access-signed">
            <span className="access-check">
              <MailCheck size={23} aria-hidden="true" />
            </span>
            <p role="status">{sent.message}</p>
            {sent.reset_link && (
              <a
                className="link selectable"
                href={sent.reset_link}
                style={{ overflowWrap: "anywhere", fontSize: 13 }}
              >
                {sent.reset_link}
              </a>
            )}
            <Link className="btn btn-primary btn-block" href="/login">
              Back to sign in
              <ArrowRight size={17} aria-hidden="true" />
            </Link>
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => setSent(null)}
            >
              Try another address
            </button>
          </div>
        ) : (
          <div className="access-card">
            <div className="access-card-head">
              <span>Recover your account</span>
              <small>Secure email verification</small>
            </div>
            <form onSubmit={submit} noValidate aria-busy={busy}>
            <Field
              id="reset-email"
              label="Email address"
              name="email"
              type="email"
              inputMode="email"
              autoComplete="username"
              autoCapitalize="none"
              placeholder="you@example.com"
              icon={<AtSign size={17} aria-hidden="true" />}
              value={email}
              maxLength={254}
              disabled={busy}
              error={submitted ? emailError : ""}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
            {error && <ErrorNote message={error} />}
            <button className="btn btn-primary btn-block" type="submit" disabled={busy}>
              {busy ? "Sending your link…" : "Send reset link"}
              {busy ? (
                <LoaderCircle size={17} className="spin" aria-hidden="true" />
              ) : (
                <ArrowRight size={17} aria-hidden="true" />
              )}
            </button>
            <p className="access-switch">
              New to shift.AI?{" "}
              <Link className="link" href="/signup">
                Create an account
              </Link>
            </p>
            </form>
          </div>
        )}
      </div>
    </Screen>
  );
}
