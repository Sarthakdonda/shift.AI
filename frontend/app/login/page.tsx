"use client";

import Link from "next/link";
import { useCallback, useState, type FormEvent } from "react";
import { usePathname, useRouter } from "next/navigation";
import { ArrowRight, Check, LoaderCircle, LockKeyhole } from "lucide-react";
import { T } from "@/components/locale";
import {
  AccessFrame,
  accessStyles as styles,
} from "@/components/auth/access-frame";
import { Field } from "@/components/auth/field";
import { GoogleAccess } from "@/components/auth/google-access";
import { useSession } from "@/components/providers";
import { useToast } from "@/components/ui/feedback";
import { signInWithEmail, signUpWithEmail } from "@/lib/auth";

export default function Login() {
  const signup = usePathname() === "/signup";
  const router = useRouter();
  const { user, loading, refresh } = useSession();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const showError = useCallback((message: string) => setError(message), []);
  const changeBusy = useCallback((value: boolean) => setBusy(value), []);
  const nameError =
    signup && name.trim().length < 2
      ? "Enter your full name (at least 2 characters)."
      : "";
  const emailError = !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())
    ? "Enter a valid email address."
    : "";
  const passwordError = !password
    ? "Enter your password."
    : signup && password.length < 12
      ? "Use at least 12 characters for your password."
      : "";
  const confirmationError =
    signup && (!confirmation || confirmation !== password)
      ? "Enter matching passwords to continue."
      : "";

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setSubmitted(true);
    setError("");
    const invalid = [
      [nameError, "signup-name"],
      [emailError, "login-email"],
      [passwordError, "login-password"],
      [confirmationError, "confirm-password"],
    ].find(([message]) => message);
    if (invalid) {
      document.getElementById(invalid[1])?.focus();
      return;
    }
    setBusy(true);
    try {
      if (signup) await signUpWithEmail(name.trim(), email.trim(), password);
      else await signInWithEmail(email.trim(), password);
      await refresh();
      setPassword("");
      setConfirmation("");
      toast(
        signup
          ? "Your account is ready. Welcome to shift.AI."
          : "Welcome back to shift.AI.",
      );
      router.replace("/dashboard");
    } catch (error) {
      setError((error as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AccessFrame
      title={signup ? "Create your account." : "Welcome back."}
      description={
        signup
          ? "A fresh perspective starts here."
          : "Sign in and pick up where you left off."
      }
      switchPrompt={signup ? "Already have an account?" : "New to shift.AI?"}
      switchLabel={signup ? "Sign in" : "Sign up"}
      switchHref={signup ? "/login" : "/signup"}
    >
      {user && !user.local ? (
        <div className={styles.signedIn}>
          <span className={styles.check}>
            <Check size={22} />
          </span>
          <p>
            <T text="Signed in as" /> <strong>{user.name}</strong>
          </p>
          <Link href="/dashboard" className={styles.submit}>
            <T text="Go to your projects" />
            <ArrowRight size={17} aria-hidden="true" />
          </Link>
        </div>
      ) : (
        <>
          <form
            className={styles.form}
            onSubmit={submit}
            noValidate
            aria-busy={busy}
          >
            {signup && (
              <Field
                id="signup-name"
                name="name"
                label="Full name"
                autoComplete="name"
                placeholder="Your full name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                maxLength={100}
                disabled={busy}
                error={submitted ? nameError : ""}
                required
              />
            )}
            <Field
              id="login-email"
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
            <Field
              id="login-password"
              name="password"
              label="Password"
              type="password"
              autoComplete={signup ? "new-password" : "current-password"}
              placeholder={signup ? "Create a password" : "Enter your password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              maxLength={128}
              disabled={busy}
              error={submitted ? passwordError : ""}
              hint={
                signup
                  ? "At least 12 characters. Try a memorable passphrase."
                  : undefined
              }
              action={
                signup ? undefined : (
                  <Link href="/forgot-password" className={styles.fieldAction}>
                    <T text="Forgot password?" />
                  </Link>
                )
              }
              required
            />
            {signup && (
              <Field
                id="confirm-password"
                name="confirmPassword"
                label="Confirm password"
                type="password"
                autoComplete="new-password"
                placeholder="Enter your password again"
                value={confirmation}
                onChange={(e) => setConfirmation(e.target.value)}
                maxLength={128}
                disabled={busy}
                error={submitted ? confirmationError : ""}
                required
              />
            )}
            {error && (
              <p className={styles.error} role="alert">
                {error}
              </p>
            )}
            <button
              className={styles.submit}
              type="submit"
              disabled={busy || loading}
            >
              <T
                text={
                  busy
                    ? signup
                      ? "Creating your account…"
                      : "Signing in…"
                    : signup
                      ? "Create account"
                      : "Sign in"
                }
              />
              {busy ? (
                <LoaderCircle size={17} className="spin" aria-hidden="true" />
              ) : (
                <ArrowRight size={17} aria-hidden="true" />
              )}
            </button>
          </form>
          <div className={styles.divider}>
            <span />
            <T text="or" />
            <span />
          </div>
          <GoogleAccess
            mode={signup ? "signup" : "signin"}
            disabled={busy}
            onError={showError}
            onBusyChange={changeBusy}
          />
          <p className={styles.privateNote}>
            <LockKeyhole size={13} aria-hidden="true" />
            <T text="Your own account. Your own space to think." />
          </p>
        </>
      )}
    </AccessFrame>
  );
}
