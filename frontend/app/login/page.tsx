"use client";
import Link from "next/link";
import Script from "next/script";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Check, ShieldCheck } from "lucide-react";
import { Logo } from "@/components/layout/shell";
import { useSession } from "@/components/providers";
import { api, post } from "@/lib/api";
import { ErrorBox, Loading } from "@/components/ui/states";
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
  const ref = useRef<HTMLDivElement>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  const [signingIn, setSigningIn] = useState(false);
  const clientId =
    process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || health?.google_client_id;
  useEffect(() => {
    if (!ready || !clientId || !ref.current || !window.google) return;
    let active = true;
    api<{ nonce: string }>("/auth/nonce")
      .then(({ nonce }) => {
        if (!active || !ref.current) return;
        window.google?.accounts.id.initialize({
          client_id: clientId,
          nonce,
          callback: async ({ credential }) => {
            setSigningIn(true);
            setError("");
            try {
              await post("/auth/google", { credential });
              await refresh();
              router.push("/dashboard");
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setSigningIn(false);
            }
          },
        });
        window.google?.accounts.id.renderButton(ref.current, {
          theme: "outline",
          size: "large",
          width: 320,
          text: "continue_with",
          shape: "rectangular",
        });
      })
      .catch((e) => setError(e.message));
    return () => {
      active = false;
    };
  }, [ready, clientId, refresh, router]);
  return (
    <div className="login-page">
      <div className="login-story">
        <Logo light />
        <div>
          <span className="eyebrow">WELCOME TO YOUR NEXT CHAPTER</span>
          <h1>
            Make the right
            <br />
            kind of shift.
          </h1>
          <p>A little clarity can change the way you work.</p>
          <ul>
            <li>
              <Check size={18} /> Start with the real problem
            </li>
            <li>
              <Check size={18} /> Build on your own evidence
            </li>
            <li>
              <Check size={18} /> Move forward with a reviewed plan
            </li>
          </ul>
        </div>
        <span className="login-foot">PROBLEM FIRST. POSSIBILITY NEXT.</span>
      </div>
      <main className="login-form">
        <div>
          <span className="eyebrow">YOUR STRATEGY WORKSPACE</span>
          <h2>Good to have you here.</h2>
          <p className="muted">
            Sign in to keep your projects and insights together.
          </p>
          {loading ? (
            <Loading />
          ) : user && !user.local ? (
            <Link href="/dashboard" className="button button-primary">
              Continue as {user.name}
              <ArrowRight size={17} />
            </Link>
          ) : health?.google_configured ? (
            <>
              <Script
                src="https://accounts.google.com/gsi/client"
                onReady={() => setReady(true)}
                onError={() =>
                  setError(
                    "Google sign-in could not load. Check your network and retry.",
                  )
                }
              />
              <div className="google-button" ref={ref} />
              {signingIn && <Loading label="Signing you in…" />}
            </>
          ) : (
            <div className="login-local">
              <p>
                Google sign-in is not configured yet. You can use the local
                workspace while you finish setup.
              </p>
              {health?.local_access_enabled && (
                <Link className="button button-primary" href="/dashboard">
                  Continue locally <ArrowRight size={17} />
                </Link>
              )}
              <Link className="text-button" href="/settings">
                View connection setup <ArrowRight size={15} />
              </Link>
            </div>
          )}
          {error && <ErrorBox message={error} />}
          <p className="privacy-note">
            <ShieldCheck size={16} /> Your projects stay separate from other
            accounts.
          </p>
          <Link className="text-button" href="/">
            Back to home
          </Link>
        </div>
      </main>
    </div>
  );
}
