"use client";

import Link from "next/link";
import { Suspense, useEffect, useState, type FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowRight, LoaderCircle } from "lucide-react";
import { T } from "@/components/locale";
import {
  AccessFrame,
  accessStyles as styles,
} from "@/components/auth/access-frame";
import { Field } from "@/components/auth/field";
import { useToast } from "@/components/ui/feedback";
import { checkResetToken, completePasswordReset } from "@/lib/auth";

function ResetPassword() {
  const token = (useSearchParams().get("token") || "").trim();
  const router = useRouter();
  const toast = useToast();
  const [state, setState] = useState<"checking" | "ready" | "invalid">(
    token ? "checking" : "invalid",
  );
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const passwordError =
    password.length < 12 ? "Use at least 12 characters for your password." : "";
  const confirmationError =
    !confirmation || confirmation !== password
      ? "Enter matching passwords to continue."
      : "";

  useEffect(() => {
    if (!token) return;
    let active = true;
    checkResetToken(token)
      .then(() => active && setState("ready"))
      .catch((problem: Error) => {
        if (!active) return;
        setState("invalid");
        setError(problem.message);
      });
    return () => {
      active = false;
    };
  }, [token]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setSubmitted(true);
    setError("");
    const invalid = [
      [passwordError, "new-password"],
      [confirmationError, "confirm-new-password"],
    ].find(([message]) => message);
    if (invalid) {
      document.getElementById(invalid[1])?.focus();
      return;
    }
    setBusy(true);
    try {
      await completePasswordReset(token, password);
      toast("Your password is updated. Sign in with it now.");
      router.replace("/login");
    } catch (problem) {
      setError((problem as Error).message);
      setBusy(false);
    }
  }

  return (
    <AccessFrame
      eyebrow="ACCOUNT RECOVERY"
      title={
        state === "invalid"
          ? "This link has expired."
          : "Choose a new password."
      }
      description={
        state === "invalid"
          ? "Reset links work once and expire quickly. Request a fresh one to continue."
          : "Your new password replaces the old one and signs out other devices."
      }
      switchPrompt="Know your password?"
      switchLabel="Sign in"
      switchHref="/login"
    >
      {state === "invalid" ? (
        <div className={styles.sentPanel}>
          {error && (
            <p className={styles.error} role="alert">
              {error}
            </p>
          )}
          <Link href="/forgot-password" className={styles.submit}>
            <T text="Request a new link" />
            <ArrowRight size={17} aria-hidden="true" />
          </Link>
          <p className={styles.linkRow}>
            <Link href="/login">
              <T text="Back to sign in" />
            </Link>
          </p>
        </div>
      ) : (
        <form
          className={styles.form}
          onSubmit={submit}
          noValidate
          aria-busy={busy || state === "checking"}
        >
          <Field
            id="new-password"
            name="password"
            label="New password"
            type="password"
            autoComplete="new-password"
            placeholder="Create a password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            maxLength={128}
            disabled={busy || state === "checking"}
            error={submitted ? passwordError : ""}
            hint="At least 12 characters. Try a memorable passphrase."
            required
          />
          <Field
            id="confirm-new-password"
            name="confirmPassword"
            label="Confirm new password"
            type="password"
            autoComplete="new-password"
            placeholder="Enter your password again"
            value={confirmation}
            onChange={(e) => setConfirmation(e.target.value)}
            maxLength={128}
            disabled={busy || state === "checking"}
            error={submitted ? confirmationError : ""}
            required
          />
          {error && (
            <p className={styles.error} role="alert">
              {error}
            </p>
          )}
          <button
            className={styles.submit}
            type="submit"
            disabled={busy || state === "checking"}
          >
            <T
              text={
                state === "checking"
                  ? "Checking your link…"
                  : busy
                    ? "Updating your password…"
                    : "Update password"
              }
            />
            {busy || state === "checking" ? (
              <LoaderCircle size={17} className="spin" aria-hidden="true" />
            ) : (
              <ArrowRight size={17} aria-hidden="true" />
            )}
          </button>
        </form>
      )}
    </AccessFrame>
  );
}

export default function Page() {
  return (
    <Suspense fallback={null}>
      <ResetPassword />
    </Suspense>
  );
}
