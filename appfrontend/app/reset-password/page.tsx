"use client";

import Link from "next/link";
import { Suspense, useEffect, useState, type FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowRight, LoaderCircle, Lock } from "lucide-react";
import { Screen } from "@/components/shell/screen";
import { Field } from "@/components/auth/field";
import { useToast } from "@/components/providers";
import { ErrorNote, Splash } from "@/components/ui/states";
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
    password.length < 12 ? "Use at least 12 characters." : "";
  const confirmationError =
    !confirmation || confirmation !== password
      ? "Enter matching passwords."
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
    const invalid = (
      [
        [passwordError, "new-password"],
        [confirmationError, "confirm-new-password"],
      ] as const
    ).find(([message]) => message);
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

  const locked = busy || state === "checking";

  return (
    <Screen title="New password" back="/login">
      <div className="access" style={{ padding: 0 }}>
        <div className="access-brand">
          <div>
            <p className="eyebrow">Account recovery</p>
            <h1 style={{ marginTop: 6 }}>
              {state === "invalid" ? "This link has expired." : "Choose a new password."}
            </h1>
            <p>
              {state === "invalid"
                ? "Reset links work once and expire quickly. Request a fresh one to continue."
                : "Your new password replaces the old one and signs out other devices."}
            </p>
          </div>
        </div>

        {state === "invalid" ? (
          <div className="stack">
            {error && <ErrorNote message={error} />}
            <Link className="btn btn-primary btn-block" href="/forgot-password">
              Request a new link
              <ArrowRight size={17} aria-hidden="true" />
            </Link>
            <Link className="btn btn-secondary btn-block" href="/login">
              Back to sign in
            </Link>
          </div>
        ) : (
          <form onSubmit={submit} noValidate aria-busy={locked}>
            <Field
              id="new-password"
              label="New password"
              name="password"
              type="password"
              autoComplete="new-password"
              placeholder="Create a password"
              icon={<Lock size={17} aria-hidden="true" />}
              value={password}
              maxLength={128}
              disabled={locked}
              hint="At least 12 characters. A memorable passphrase works well."
              error={submitted ? passwordError : ""}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
            <Field
              id="confirm-new-password"
              label="Confirm new password"
              name="confirmPassword"
              type="password"
              autoComplete="new-password"
              placeholder="Enter your password again"
              icon={<Lock size={17} aria-hidden="true" />}
              value={confirmation}
              maxLength={128}
              disabled={locked}
              error={submitted ? confirmationError : ""}
              onChange={(event) => setConfirmation(event.target.value)}
              required
            />
            {error && <ErrorNote message={error} />}
            <button className="btn btn-primary btn-block" type="submit" disabled={locked}>
              {state === "checking"
                ? "Checking your link…"
                : busy
                  ? "Updating your password…"
                  : "Update password"}
              {locked ? (
                <LoaderCircle size={17} className="spin" aria-hidden="true" />
              ) : (
                <ArrowRight size={17} aria-hidden="true" />
              )}
            </button>
          </form>
        )}
      </div>
    </Screen>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<Splash message="Checking your reset link…" />}>
      <ResetPassword />
    </Suspense>
  );
}
