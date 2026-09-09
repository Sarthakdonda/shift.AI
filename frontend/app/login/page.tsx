"use client";
import { T } from "@/components/locale";

import Link from "next/link";
import Script from "next/script";
import { useEffect, useRef, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import {
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  Check,
  Eye,
  EyeOff,
  FileCheck2,
  LoaderCircle,
  LockKeyhole,
  Mail,
  ScanLine,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { Logo } from "@/components/layout/logo";
import { LanguagePicker } from "@/components/locale";
import { useSession } from "@/components/providers";
import { useToast } from "@/components/ui/feedback";
import { api, post } from "@/lib/api";
import { signUpWithEmail, signInWithEmail, verifySession } from "@/lib/auth";

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (o: {
            client_id: string;
            nonce: string;
            callback: (r: { credential: string }) => void;
          }) => void;
          renderButton: (el: HTMLElement, o: object) => void;
        };
      };
    };
  }
}
export default function Login() {
  const { user, health, loading, refresh } = useSession();
  const router = useRouter();
  const signup = usePathname() === "/signup";
  const [name, setName] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const toast = useToast();
  const ref = useRef<HTMLDivElement>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const clientId =
    process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || health?.google_client_id;
  const googleEnabled = !!health?.google_configured && !!clientId;
  const emailError =
    submitted && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())
      ? "Enter a valid email address."
      : "";
  const passwordError = submitted && !password ? "Enter your password." : "";
  useEffect(() => {
    if (!ready || !googleEnabled || !clientId || !ref.current || !window.google)
      return;
    let active = true;
    api<{ nonce: string }>("/auth/nonce", {
      signal: AbortSignal.timeout(15000),
    })
      .then(({ nonce }) => {
        if (!active || !ref.current) return;
        window.google?.accounts.id.initialize({
          client_id: clientId,
          nonce,
          callback: async ({ credential }) => {
            setBusy(true);
            setError("");
            try {
              await post("/auth/google", { credential });
              await verifySession();
              await refresh();
              toast("You’re signed in. Welcome to your workspace.");
              router.replace("/dashboard");
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setBusy(false);
            }
          },
        });
        window.google?.accounts.id.renderButton(ref.current, {
          theme: "outline",
          size: "large",
          width: Math.min(ref.current.clientWidth, 400),
          text: "continue_with",
          shape: "rectangular",
        });
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [ready, googleEnabled, clientId, refresh, router, toast]);

  return (
    <div className="auth-page">
      <aside className="auth-story">
        <Logo light />
        <div className="auth-story-copy">
          <span className="eyebrow">
            <T text={"GOOD THINKING STARTS HERE"} />
          </span>
          <h1>
            <T text={"A fresh perspective."} /> <br />
            <T text={"A clearer "} />
            <span>
              <T text={"way forward."} />
            </span>
          </h1>
          <p>
            <T text={"One space to explore your challenges,"} />
            <br />
            <T text={"connect the dots, and make your next move."} />
          </p>
        </div>
        <div
          className="auth-illustration"
          aria-label="From your challenge to a reviewed blueprint"
        >
          <div className="auth-orbit" aria-hidden />
          <div className="auth-floating auth-question">
            <span className="auth-illustration-icon">
              <Sparkles size={20} />
            </span>
            <div>
              <small>
                <T text={"START WITH A QUESTION"} />
              </small>
              <strong>
                <T text={"What could work better?"} />
              </strong>
            </div>
            <span className="auth-card-dot" />
          </div>
          <div className="auth-flow-line" aria-hidden />
          <div className="auth-floating auth-insight">
            <span className="auth-illustration-icon">
              <ScanLine size={20} />
            </span>
            <div>
              <small>
                <T text={"FIND YOUR CLARITY"} />
              </small>
              <strong>
                <T text={"See the bigger picture."} />
              </strong>
              <div className="auth-mini-bars" aria-hidden>
                <i />
                <i />
                <i />
                <i />
                <i />
                <i />
                <i />
              </div>
            </div>
          </div>
          <div className="auth-flow-line second" aria-hidden />
          <div className="auth-floating auth-plan">
            <span className="auth-illustration-icon">
              <FileCheck2 size={20} />
            </span>
            <div>
              <small>
                <T text={"MAKE YOUR NEXT MOVE"} />
              </small>
              <strong>
                <T text={"A plan you can build on."} />
              </strong>
            </div>
            <Check size={16} />
          </div>
        </div>
        <div className="auth-story-footer">
          <span className="tiny-orange" />
          <T text={" Problem first. Possibility next."} />
          <span>
            <T text={"shift.AI"} />
          </span>
        </div>
      </aside>
      <main className="auth-main" id="main">
        <div className="auth-top">
          <LanguagePicker />
          <Link href="/" className="auth-back">
            <ArrowLeft size={15} />
            <T text={" Back to home"} />
          </Link>
          <span>
            <T text={"YOUR STRATEGY WORKSPACE"} />
          </span>
        </div>
        <div className="auth-card enter">
          <span className="auth-form-icon">
            <LockKeyhole size={23} strokeWidth={1.6} />
          </span>
          <h2>
            <T text={signup ? "Create your workspace." : "Welcome back."} />
          </h2>
          <p className="auth-description">
            <T text={"A little clarity is just a sign-in away."} />
          </p>
          {user && !user.local ? (
            <div className="auth-signed-in">
              <span className="account-avatar">
                {user.name?.charAt(0) || "S"}
              </span>
              <p>
                <T text={"Signed in as "} />
                <strong>{user.name}</strong>
              </p>
              <Link href="/dashboard" className="button button-primary">
                <T text={"Continue to workspace "} />
                <ArrowRight size={16} />
              </Link>
            </div>
          ) : (
            <>
              {googleEnabled ? (
                <>
                  <Script
                    src="https://accounts.google.com/gsi/client"
                    onReady={() => setReady(true)}
                    onError={() =>
                      setError(
                        "Google sign-in couldn’t load. Please refresh the page to try again.",
                      )
                    }
                  />
                  <div
                    className={`auth-google ${busy ? "is-busy" : ""}`}
                    ref={ref}
                  />
                  {!ready && (
                    <div className="auth-google-loading">
                      <LoaderCircle size={16} className="spin" />
                      <T text={" Loading Google sign-in…"} />
                    </div>
                  )}
                </>
              ) : null}
              {googleEnabled && (
                <div className="auth-divider">
                  <span />
                  <T text={"or continue with email"} />
                  <span />
                </div>
              )}
              <form
                noValidate
                onSubmit={async (e) => {
                  e.preventDefault();
                  if (busy) return;
                  setSubmitted(true);
                  setError("");
                  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
                    document.getElementById("login-email")?.focus();
                    return;
                  }
                  if (!password) {
                    document.getElementById("login-password")?.focus();
                    return;
                  }
                  if (
                    signup &&
                    (name.trim().length < 2 ||
                      password.length < 12 ||
                      password !== confirmPassword)
                  ) {
                    setError(
                      "Enter your name and matching passwords of at least 12 characters.",
                    );
                    return;
                  }
                  setBusy(true);
                  try {
                    if (signup)
                      await signUpWithEmail(
                        name.trim(),
                        email.trim(),
                        password,
                      );
                    else await signInWithEmail(email.trim(), password);
                    await refresh();
                    setPassword("");
                    toast("You’re signed in. Welcome to your workspace.");
                    router.replace("/dashboard");
                  } catch (e) {
                    setError((e as Error).message);
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                {signup && (
                  <>
                    <label htmlFor="signup-name">
                      <T text={"Full name"} />
                    </label>
                    <div className="auth-input">
                      <input
                        id="signup-name"
                        autoComplete="name"
                        value={name}
                        maxLength={100}
                        onChange={(e) => setName(e.target.value)}
                        disabled={busy}
                      />
                    </div>
                  </>
                )}
                <label htmlFor="login-email">
                  <T text={"Email address"} />
                </label>
                <div className={`auth-input ${emailError ? "invalid" : ""}`}>
                  <Mail size={17} />
                  <input
                    id="login-email"
                    name="email"
                    type="email"
                    autoComplete="username"
                    placeholder="you@company.com"
                    value={email}
                    disabled={busy}
                    onChange={(e) => setEmail(e.target.value)}
                    aria-invalid={!!emailError}
                    aria-describedby={emailError ? "email-error" : undefined}
                  />
                </div>
                {emailError && (
                  <p className="field-error" id="email-error" role="alert">
                    {emailError}
                  </p>
                )}
                <label htmlFor="login-password">
                  <T text={"Password"} />
                </label>
                <div className={`auth-input ${passwordError ? "invalid" : ""}`}>
                  <LockKeyhole size={17} />
                  <input
                    id="login-password"
                    name="password"
                    type={showPassword ? "text" : "password"}
                    autoComplete={signup ? "new-password" : "current-password"}
                    placeholder="Enter your password"
                    value={password}
                    disabled={busy}
                    onChange={(e) => setPassword(e.target.value)}
                    aria-invalid={!!passwordError}
                    aria-describedby={
                      passwordError ? "password-error" : undefined
                    }
                  />
                  <button
                    type="button"
                    aria-label={
                      showPassword ? "Hide password" : "Show password"
                    }
                    aria-pressed={showPassword}
                    onClick={() => setShowPassword(!showPassword)}
                  >
                    {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
                  </button>
                </div>
                {passwordError && (
                  <p className="field-error" id="password-error" role="alert">
                    {passwordError}
                  </p>
                )}
                {signup && (
                  <>
                    <p className="muted small">
                      <T
                        text={
                          "Use at least 12 characters. A memorable passphrase works well."
                        }
                      />
                    </p>
                    <label htmlFor="confirm-password">
                      <T text={"Confirm password"} />
                    </label>
                    <div className="auth-input">
                      <input
                        id="confirm-password"
                        type="password"
                        autoComplete="new-password"
                        value={confirmPassword}
                        maxLength={128}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        disabled={busy}
                      />
                    </div>
                  </>
                )}
                {error && (
                  <p className="auth-error" role="alert">
                    {error}
                  </p>
                )}
                <button
                  className="button button-primary auth-submit"
                  type="submit"
                  disabled={busy || loading}
                >
                  {busy ? <LoaderCircle size={17} className="spin" /> : null}
                  <T
                    text={
                      busy
                        ? "Please wait…"
                        : signup
                          ? "Create account"
                          : "Sign in to workspace"
                    }
                  />
                  <ArrowRight size={16} />
                </button>
              </form>
              <p className="auth-availability">
                {signup ? "Already have an account? " : "New to shift.AI? "}
                <Link href={signup ? "/login" : "/signup"}>
                  {signup ? "Sign in" : "Create an account"}
                </Link>
              </p>
              {health?.local_access_enabled && (
                <Link className="auth-local" href="/dashboard">
                  <T text={"Continue locally "} />
                  <ArrowUpRight size={14} />
                </Link>
              )}
            </>
          )}
          <div className="auth-privacy">
            <ShieldCheck size={15} />
            <span>
              <T text={"Your ideas. Your projects. Your workspace."} />
            </span>
          </div>
        </div>
        <footer className="auth-footer">
          <span>
            © {new Date().getFullYear()}
            <T text={" shift.AI"} />
          </span>
          <span>
            <T text={"Clarity before complexity."} />
          </span>
        </footer>
      </main>
    </div>
  );
}
