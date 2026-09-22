"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import {
  ArrowRight,
  AtSign,
  Check,
  LoaderCircle,
  Lock,
  ShieldCheck,
  Sparkles,
  UserRound,
} from "lucide-react";
import { Screen } from "@/components/shell/screen";
import { Field } from "@/components/auth/field";
import { useSession, useToast } from "@/components/providers";
import { BrandMark, ErrorNote } from "@/components/ui/states";
import { signInWithEmail, signUpWithEmail } from "@/lib/auth";

export function AccessScreen({ mode }: { mode: "signin" | "signup" }) {
  const signup = mode === "signup";
  const router = useRouter();
  const { user, refresh } = useSession();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [waiting, setWaiting] = useState(false);
  const [error, setError] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");

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
      ? "Use at least 12 characters."
      : "";
  const confirmationError =
    signup && (!confirmation || confirmation !== password)
      ? "Enter matching passwords."
      : "";

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setSubmitted(true);
    setError("");
    const invalid = (
      [
        [nameError, "signup-name"],
        [emailError, "access-email"],
        [passwordError, "access-password"],
        [confirmationError, "confirm-password"],
      ] as const
    ).find(([message]) => message);
    if (invalid) {
      document.getElementById(invalid[1])?.focus();
      return;
    }
    setBusy(true);
    try {
      if (signup)
        await signUpWithEmail(name.trim(), email.trim(), password, setWaiting);
      else await signInWithEmail(email.trim(), password, setWaiting);
      await refresh();
      setPassword("");
      setConfirmation("");
      toast(signup ? "Your account is ready." : "Welcome back.");
      router.replace("/chats");
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy(false);
      setWaiting(false);
    }
  }

  const signedIn = user && !user.local;

  return (
    <Screen depth="root" title={signup ? "Create account" : "Sign in"}>
      <div className="access" style={{ padding: 0 }}>
        <div className="access-brand">
          <div className="access-brand-row">
            <BrandMark large />
            <span className="access-edition">Strategy workspace</span>
          </div>
          <div className="access-copy">
            <h1>{signup ? "Create your account." : "Welcome back."}</h1>
            <p>
              {signup
                ? "A fresh perspective on your business starts here."
                : "Sign in and pick up exactly where you left off."}
            </p>
          </div>
          <div className="access-benefits" aria-label="Product benefits">
            <span><Sparkles size={14} /> Guided discovery</span>
            <span><ShieldCheck size={14} /> Private workspace</span>
          </div>
        </div>

        {signedIn ? (
          <div className="access-signed">
            <span className="access-check">
              <Check size={24} aria-hidden="true" />
            </span>
            <p>
              Signed in as <strong>{user.name}</strong>
            </p>
            <Link className="btn btn-primary btn-block" href="/chats">
              Go to your projects
              <ArrowRight size={17} aria-hidden="true" />
            </Link>
          </div>
        ) : (
          <div className="access-card">
            <div className="access-card-head">
              <span>{signup ? "Set up your workspace" : "Continue your work"}</span>
              <small>{signup ? "Takes less than a minute" : "Secure account access"}</small>
            </div>
            <form onSubmit={submit} noValidate aria-busy={busy}>
              {signup && (
                <Field
                  id="signup-name"
                  label="Full name"
                  name="name"
                  autoComplete="name"
                  placeholder="Your full name"
                  icon={<UserRound size={17} aria-hidden="true" />}
                  value={name}
                  maxLength={100}
                  disabled={busy}
                  error={submitted ? nameError : ""}
                  onChange={(event) => setName(event.target.value)}
                  required
                />
              )}
              <Field
                id="access-email"
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
              <Field
                id="access-password"
                label="Password"
                name="password"
                type="password"
                autoComplete={signup ? "new-password" : "current-password"}
                placeholder={signup ? "Create a password" : "Enter your password"}
                icon={<Lock size={17} aria-hidden="true" />}
                value={password}
                maxLength={128}
                disabled={busy}
                hint={signup ? "At least 12 characters." : undefined}
                error={submitted ? passwordError : ""}
                onChange={(event) => setPassword(event.target.value)}
                action={
                  signup ? undefined : (
                    <Link className="link" href="/forgot-password">
                      Forgot password?
                    </Link>
                  )
                }
                required
              />
              {signup && (
                <Field
                  id="confirm-password"
                  label="Confirm password"
                  name="confirmPassword"
                  type="password"
                  autoComplete="new-password"
                  placeholder="Enter your password again"
                  icon={<Lock size={17} aria-hidden="true" />}
                  value={confirmation}
                  maxLength={128}
                  disabled={busy}
                  error={submitted ? confirmationError : ""}
                  onChange={(event) => setConfirmation(event.target.value)}
                  required
                />
              )}
              {error && <ErrorNote message={error} />}
              {waiting && (
                <p className="note" role="status">
                  Your workspace is starting. This can take up to two minutes and
                  continues automatically.
                </p>
              )}
              <button
                className="btn btn-primary btn-block"
                type="submit"
                disabled={busy}
              >
                {busy
                  ? signup
                    ? "Creating your account…"
                    : "Signing in…"
                  : signup
                    ? "Create account"
                    : "Sign in"}
                {busy ? (
                  <LoaderCircle size={17} className="spin" aria-hidden="true" />
                ) : (
                  <ArrowRight size={17} aria-hidden="true" />
                )}
              </button>
            </form>
            <p className="access-switch">
              {signup ? "Already have an account? " : "New to shift.AI? "}
              <Link className="link" href={signup ? "/login" : "/signup"}>
                {signup ? "Sign in" : "Create one"}
              </Link>
            </p>
            <p className="access-browser-note">
              Google sign-in needs a full browser. Open the website in Chrome to
              use it, then sign in here with your email.
            </p>
          </div>
        )}
      </div>
    </Screen>
  );
}
