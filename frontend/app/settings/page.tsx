"use client";
import Link from "next/link";
import { useState } from "react";
import {
  RefreshCw,
  Database,
  Sparkles,
  ShieldCheck,
  CheckCircle2,
  Circle,
  ArrowUpRight,
} from "lucide-react";
import { Shell } from "@/components/layout/shell";
import { useSession } from "@/components/providers";
import { Button } from "@/components/ui/button";
export default function Settings() {
  const { health, user, refresh } = useSession();
  const [busy, setBusy] = useState(false);
  return (
    <Shell>
      <div className="page-heading">
        <div>
          <span className="eyebrow">MAKE YOUR WORKSPACE YOURS</span>
          <h1>Settings & connections</h1>
          <p>A few connections bring your strategy workspace to life.</p>
        </div>
        <Button
          variant="secondary"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            await refresh();
            setBusy(false);
          }}
        >
          <RefreshCw size={16} className={busy ? "spin" : ""} /> Check
          connections
        </Button>
      </div>
      <div className="settings-grid">
        {[
          {
            icon: Sparkles,
            title: "Gemini",
            active: health?.gemini_configured,
            description:
              "Powers discovery, analysis, and your final blueprint.",
            file: "backend/.env",
            fields: [
              "GEMINI_API_KEY=your_key",
              "GEMINI_MODEL=gemini-2.5-flash",
            ],
            url: "https://aistudio.google.com/apikey",
            link: "Get a Gemini API key",
          },
          {
            icon: Database,
            title: "MongoDB Atlas",
            active: health?.database === "connected",
            description:
              "Keeps your projects, documents, and conversations saved.",
            file: "backend/.env",
            fields: [
              "MONGODB_URI=your_atlas_connection_string",
              "MONGODB_DATABASE=shift_ai",
            ],
            url: "https://cloud.mongodb.com/",
            link: "Open MongoDB Atlas",
          },
          {
            icon: ShieldCheck,
            title: "Google sign-in",
            active: health?.google_configured,
            description: "Gives each Google account its own private workspace.",
            file: "backend/.env",
            fields: [
              "GOOGLE_CLIENT_ID=your_web_client_id",
              "SESSION_SECRET=random_32_plus_character_value",
            ],
            url: "https://console.cloud.google.com/auth/clients",
            link: "Create an OAuth client",
          },
        ].map((x) => (
          <section className="panel connection-card" key={x.title}>
            <div className="row-between">
              <span className="connection-icon">
                <x.icon size={25} />
              </span>
              <span className={`badge ${x.active ? "badge-green" : ""}`}>
                {x.active ? <CheckCircle2 size={13} /> : <Circle size={13} />}{" "}
                {x.active
                  ? x.title === "MongoDB Atlas"
                    ? "Connected"
                    : "Configured"
                  : "Setup needed"}
              </span>
            </div>
            <h2>{x.title}</h2>
            <p className="muted">{x.description}</p>
            <div className="env-block">
              <small>{x.file}</small>
              <pre>{x.fields.join("\n")}</pre>
            </div>
            <a
              className="text-button"
              href={x.url}
              target="_blank"
              rel="noreferrer"
            >
              {x.link}
              <ArrowUpRight size={15} />
            </a>
          </section>
        ))}
      </div>
      <section className="panel setup-guide">
        <h2>Google sign-in setup</h2>
        <ol>
          <li>
            In Google Cloud, configure the OAuth consent screen and add your
            email as a test user while the app is in testing.
          </li>
          <li>
            Create an OAuth client with application type{" "}
            <strong>Web application</strong>.
          </li>
          <li>
            Add <code>http://localhost:3000</code> to{" "}
            <strong>Authorized JavaScript origins</strong>. This app uses a
            Google credential popup, so no redirect URI or client secret is
            needed.
          </li>
          <li>
            Paste the client ID into <code>GOOGLE_CLIENT_ID</code> in{" "}
            <code>backend/.env</code>. Optionally put the same ID in{" "}
            <code>NEXT_PUBLIC_GOOGLE_CLIENT_ID</code> in{" "}
            <code>frontend/.env.local</code>.
          </li>
          <li>
            Set a random <code>SESSION_SECRET</code> of at least 32 characters,
            then restart the backend. Restart the frontend if you changed its
            environment file.
          </li>
        </ol>
        <Link className="button button-secondary" href="/login">
          Open sign-in page <ArrowUpRight size={16} />
        </Link>
      </section>
      <div className="setup-note">
        <ShieldCheck size={18} />
        <span>
          {user?.local
            ? "You are using a local workspace. Google accounts have separate projects; local projects stay in the local workspace."
            : "Gemini and database credentials are stored only on the backend."}
        </span>
      </div>
      {!health && (
        <div className="error-box">
          The backend is unavailable. Start FastAPI, then check connections
          again.
        </div>
      )}
    </Shell>
  );
}
