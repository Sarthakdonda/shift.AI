"use client";

import Script from "next/script";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { LoaderCircle } from "lucide-react";
import { T } from "@/components/locale";
import { useSession } from "@/components/providers";
import { api, post } from "@/lib/api";
import { verifySession } from "@/lib/auth";
import styles from "./access.module.css";

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (options: {
            client_id: string;
            nonce: string;
            callback: (response: { credential: string }) => void;
          }) => void;
          renderButton: (element: HTMLElement, options: object) => void;
        };
      };
    };
  }
}

function GoogleMark() {
  return (
    <svg width="17" height="17" viewBox="0 0 48 48" aria-hidden="true">
      <path
        fill="#4285F4"
        d="M45.1 24.5c0-1.6-.1-3.1-.4-4.5H24v8.5h11.8c-.5 2.8-2.1 5.1-4.4 6.7v5.5h7.1c4.2-3.8 6.6-9.5 6.6-16.2z"
      />
      <path
        fill="#34A853"
        d="M24 46c5.9 0 10.9-2 14.5-5.3l-7.1-5.5c-2 1.3-4.5 2.1-7.4 2.1-5.7 0-10.5-3.8-12.2-9H4.5v5.7C8.1 41.3 15.4 46 24 46z"
      />
      <path
        fill="#FBBC05"
        d="M11.8 28.3c-.4-1.3-.7-2.8-.7-4.3s.3-2.9.7-4.3v-5.7H4.5C2.9 17.2 2 20.5 2 24s.9 6.8 2.5 10l7.3-5.7z"
      />
      <path
        fill="#EA4335"
        d="M24 10.2c3.2 0 6.1 1.1 8.4 3.3l6.3-6.3C34.9 3.7 29.9 1.7 24 1.7 15.4 1.7 8.1 6.4 4.5 13.3l7.3 5.7c1.7-5.2 6.5-8.8 12.2-8.8z"
      />
    </svg>
  );
}

/** Google's own button is layered invisibly over this design, so the real
 *  credential flow runs while the workspace keeps its own styling. */
export function GoogleAccess({
  mode,
  disabled,
  onError,
  onBusyChange,
}: {
  mode: "signin" | "signup";
  disabled?: boolean;
  onError: (message: string) => void;
  onBusyChange?: (busy: boolean) => void;
}) {
  const { health, loading, refresh } = useSession();
  const router = useRouter();
  const hostRef = useRef<HTMLDivElement>(null);
  const [scriptReady, setScriptReady] = useState(false);
  const [rendered, setRendered] = useState(false);
  const [working, setWorking] = useState(false);
  const clientId =
    process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || health?.google_client_id;
  const configured = !!health?.google_configured && !!clientId;

  useEffect(() => {
    if (!scriptReady || !configured || !clientId || !hostRef.current) return;
    let active = true;
    api<{ nonce: string }>("/auth/nonce", {
      signal: AbortSignal.timeout(15000),
    })
      .then(({ nonce }) => {
        if (!active || !hostRef.current || !window.google) return;
        window.google.accounts.id.initialize({
          client_id: clientId,
          nonce,
          callback: async ({ credential }) => {
            setWorking(true);
            onBusyChange?.(true);
            try {
              await post("/auth/google", { credential });
              await verifySession();
              await refresh();
              router.replace("/dashboard");
            } catch (error) {
              onError((error as Error).message);
              setWorking(false);
              onBusyChange?.(false);
            }
          },
        });
        window.google.accounts.id.renderButton(hostRef.current, {
          theme: "outline",
          size: "large",
          width: Math.max(
            200,
            Math.min(hostRef.current.clientWidth || 320, 400),
          ),
          text: mode === "signup" ? "signup_with" : "signin_with",
          shape: "rectangular",
          logo_alignment: "center",
        });
        setRendered(true);
      })
      .catch((error: Error) => {
        if (active) onError(error.message);
      });
    return () => {
      active = false;
    };
  }, [
    scriptReady,
    configured,
    clientId,
    mode,
    onError,
    onBusyChange,
    refresh,
    router,
  ]);

  const face = (
    <span className={styles.googleFace}>
      {working ? (
        <LoaderCircle size={17} className="spin" aria-hidden="true" />
      ) : (
        <GoogleMark />
      )}
      <T text="Continue with Google" />
    </span>
  );

  if (!configured)
    return (
      <>
        <button
          type="button"
          className={styles.googleButton}
          disabled
          aria-describedby="google-availability"
        >
          {face}
        </button>
        <p className={styles.googleNote} id="google-availability">
          <T
            text={
              loading
                ? "Checking whether Google sign-in is available…"
                : "Google sign-in turns on once GOOGLE_CLIENT_ID is set. Email accounts work now."
            }
          />
        </p>
      </>
    );

  return (
    <div
      className={styles.googleButton}
      data-pending={rendered && !working ? "false" : "true"}
      aria-busy={working}
    >
      <Script
        src="https://accounts.google.com/gsi/client"
        onReady={() => setScriptReady(true)}
        onError={() =>
          onError(
            "Google sign-in could not load. You can still continue with your email address.",
          )
        }
      />
      {face}
      <div
        className={styles.googleFrame}
        ref={hostRef}
        inert={disabled || working}
      />
    </div>
  );
}
