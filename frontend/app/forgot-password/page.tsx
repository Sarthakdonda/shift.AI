"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { ArrowRight, LoaderCircle, MailCheck } from "lucide-react";
import { T } from "@/components/locale";
import {
  AccessFrame,
  accessStyles as styles,
} from "@/components/auth/access-frame";
import { Field } from "@/components/auth/field";
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
    } catch (error) {
      setError((error as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AccessFrame
      eyebrow="ACCOUNT RECOVERY"
      title={sent ? "Check your email." : "Reset your password."}
      description={
        sent
          ? "The link works once and expires shortly, so open it soon."
          : "Enter the email address on your account and we will send a secure reset link."
      }
      switchPrompt="Remembered it?"
      switchLabel="Sign in"
      switchHref="/login"
    >
      {sent ? (
        <div className={styles.sentPanel}>
          <span className={styles.check}>
            <MailCheck size={22} aria-hidden="true" />
          </span>
          <p role="status">{sent.message}</p>
          {sent.reset_link && (
            <a className={styles.localLink} href={sent.reset_link}>
              {sent.reset_link}
            </a>
          )}
          <Link href="/login" className={styles.submit}>
            <T text="Back to sign in" />
            <ArrowRight size={17} aria-hidden="true" />
          </Link>
          <p className={styles.linkRow}>
            <T text="No email yet?" />{" "}
            <button
              type="button"
              className={styles.fieldAction}
              onClick={() => setSent(null)}
            >
              <T text="Try another address" />
            </button>
          </p>
        </div>
      ) : (
        <form
          className={styles.form}
          onSubmit={submit}
          noValidate
          aria-busy={busy}
        >
          <Field
            id="reset-email"
            name="email"
            label="Email address"
            type="email"
            autoComplete="username"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            maxLength={254}
            disabled={busy}
            error={submitted ? emailError : ""}
            required
          />
          {error && (
            <p className={styles.error} role="alert">
              {error}
            </p>
          )}
          <button className={styles.submit} type="submit" disabled={busy}>
            <T text={busy ? "Sending your link…" : "Send reset link"} />
            {busy ? (
              <LoaderCircle size={17} className="spin" aria-hidden="true" />
            ) : (
              <ArrowRight size={17} aria-hidden="true" />
            )}
          </button>
          <p className={styles.linkRow}>
            <T text="New to shift.AI?" />{" "}
            <Link href="/signup">
              <T text="Create an account" />
            </Link>
          </p>
        </form>
      )}
    </AccessFrame>
  );
}
