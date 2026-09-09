"use client";

import { T } from "@/components/locale";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  LoaderCircle,
  Lightbulb,
} from "lucide-react";
import { Shell } from "@/components/layout/shell";
import { Button } from "@/components/ui/button";
import { ErrorBox } from "@/components/ui/states";
import { api, post } from "@/lib/api";
import { languages, type Workspace } from "@/lib/deliverables";
import { Project } from "@/lib/types";
import { delay } from "@/lib/utils";
import { ConfirmDialog, useToast } from "@/components/ui/feedback";

const examples = [
  {
    name: "Streamline customer support",
    industry: "Customer service",
    problem:
      "Our support team spends too much time on repetitive customer questions. We want to understand the bottlenecks and reduce response times without sacrificing service quality.",
  },
  {
    name: "Simplify invoice processing",
    industry: "Finance operations",
    problem:
      "Our team manually copies invoice details between email, spreadsheets, and our accounting tool. Errors and slow approvals delay payments. We want a simpler, more reliable process.",
  },
  {
    name: "Improve appointment scheduling",
    industry: "Healthcare",
    problem:
      "Our reception team handles scheduling by phone and a shared calendar. Missed calls and duplicate bookings are causing delays. We want to improve access and reduce administrative work.",
  },
];

export default function NewProject() {
  const router = useRouter();
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [workspaceId, setWorkspaceId] = useState("");
  const [language, setLanguage] = useState("en");
  useEffect(() => {
    void api<Workspace[]>("/workspaces")
      .then(setWorkspaces)
      .catch(() => {});
    setWorkspaceId(
      new URLSearchParams(window.location.search).get("workspace") || "",
    );
  }, []);
  const [form, setForm] = useState({
    name: "",
    initial_problem: "",
    industry: "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [leaving, setLeaving] = useState("");
  const [sample, setSample] = useState<(typeof examples)[number] | null>(null);
  const toast = useToast();
  const dirty = !!(form.name || form.industry || form.initial_problem);
  const applyExample = (x: (typeof examples)[number]) =>
    setForm({ name: x.name, industry: x.industry, initial_problem: x.problem });
  useEffect(() => {
    if (!dirty || busy) return;
    const intercept = (event: MouseEvent) => {
      if (
        event.defaultPrevented ||
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.altKey ||
        event.button !== 0
      )
        return;
      const link = (event.target as HTMLElement).closest<HTMLAnchorElement>(
        "a[href]",
      );
      if (
        !link ||
        link.target === "_blank" ||
        link.origin !== location.origin ||
        link.pathname === location.pathname
      )
        return;
      event.preventDefault();
      event.stopPropagation();
      setLeaving(link.pathname + link.search + link.hash);
    };
    document.addEventListener("click", intercept, true);
    return () => document.removeEventListener("click", intercept, true);
  }, [dirty, busy]);
  return (
    <Shell>
      <Link className="back-page" href="/dashboard">
        <ArrowLeft size={16} />
        <T text={" All projects"} />
      </Link>
      <div className="page-heading">
        <div>
          <span className="eyebrow">
            <T text={"The first step is understanding"} />
          </span>
          <h1>
            <T text={"What would you like to improve?"} />
          </h1>
          <p>
            <T
              text={
                "Start with the challenge. You do not need to know the solution yet — that is what discovery is for."
              }
            />
          </p>
        </div>
      </div>
      <div className="new-project-layout">
        <form
          noValidate
          className="panel project-form enter"
          onSubmit={async (e) => {
            e.preventDefault();
            if (busy) return;
            if (
              form.name.trim().length < 2 ||
              form.initial_problem.trim().length < 15
            ) {
              setError(
                "Add a project name of at least 2 characters and describe your challenge in at least 15 characters.",
              );
              const field = e.currentTarget.querySelector<HTMLElement>(
                form.name.trim().length < 2 ? "input" : "textarea",
              );
              field?.focus();
              return;
            }
            setBusy(true);
            setError("");
            try {
              const p = await post<Project>("/projects", {
                ...form,
                workspace_id: workspaceId || null,
                language,
              });
              toast("Project created. Let’s explore your challenge.");
              router.push(`/project/${p.id}`);
            } catch (e) {
              setError((e as Error).message);
              setBusy(false);
            }
          }}
        >
          <div className="form-step">
            <span>01</span>
            <div>
              <h2>
                <T text={"Give your project some context"} />
              </h2>
              <p>
                <T
                  text={
                    "A few details help us ask sharper questions from the start."
                  }
                />
              </p>
            </div>
          </div>
          <label>
            <T text={"Project name"} />
            <input
              required
              disabled={busy}
              minLength={2}
              maxLength={100}
              placeholder="e.g. A better customer support workflow"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </label>
          <label>
            <T text={"Industry "} />
            <span className="optional">
              <T text={"Optional"} />
            </span>
            <input
              disabled={busy}
              maxLength={100}
              placeholder="e.g. Healthcare, retail, logistics"
              value={form.industry}
              onChange={(e) => setForm({ ...form, industry: e.target.value })}
            />
          </label>
          <label>
            <T text={"Workspace"} />
            <select
              value={workspaceId}
              onChange={(e) => setWorkspaceId(e.target.value)}
              disabled={busy}
            >
              <option value="">Personal workspace</option>
              {workspaces
                .filter((w) =>
                  ["owner", "admin", "editor"].includes(w.access_role),
                )
                .map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.name}
                  </option>
                ))}
            </select>
          </label>
          <label>
            <T text={"Conversation language"} />
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              disabled={busy}
            >
              {Object.entries(languages).map(([code, label]) => (
                <option key={code} value={code}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label>
            <T text={"What’s the challenge?"} />
            <textarea
              required
              disabled={busy}
              minLength={15}
              maxLength={12000}
              rows={8}
              placeholder="Tell us what happens today, what isn’t working, and what you’d like to change. Plain language is perfect."
              value={form.initial_problem}
              onChange={(e) =>
                setForm({ ...form, initial_problem: e.target.value })
              }
            />
          </label>
          <div className="field-hint">
            <T
              text={
                "Describe the problem, who it affects, and your ideal outcome."
              }
            />
            <span>{form.initial_problem.length}/12000</span>
          </div>
          {error && <ErrorBox message={error} />}
          <div className="form-footer">
            <Link className="text-button" href="/dashboard">
              <T text={"Cancel"} />
            </Link>
            <Button disabled={busy} type="submit">
              {busy ? <LoaderCircle size={17} className="spin" /> : null}
              {busy ? "Creating project…" : "Start discovery"}
              <ArrowRight size={17} />
            </Button>
          </div>
        </form>
        <aside className="new-project-aside">
          <div className="warm-panel enter" style={delay(80)}>
            <span className="eyebrow">
              <T text={"What happens next"} />
            </span>
            <h3>
              <T text={"Clarity, one question at a time."} />
            </h3>
            <ol>
              <li>
                <T text={"We map how your current process actually works."} />
              </li>
              <li>
                <T text={"You can add documents for supporting evidence."} />
              </li>
              <li>
                <T text={"We diagnose the root cause and weigh the options."} />
              </li>
              <li>
                <T text={"You get a reviewed, actionable blueprint."} />
              </li>
            </ol>
          </div>
          <div className="example-list enter" style={delay(140)}>
            <h3>
              <Lightbulb size={17} />
              <T text={" Need a starting point?"} />
            </h3>
            <p className="muted">
              <T
                text={
                  "Load a sample challenge, then edit it into your own words."
                }
              />
            </p>
            {examples.map((x) => (
              <button
                type="button"
                disabled={busy}
                key={x.name}
                onClick={() => (dirty ? setSample(x) : applyExample(x))}
              >
                {x.name}
                <ArrowUpRight size={16} />
              </button>
            ))}
          </div>
        </aside>
      </div>
      <ConfirmDialog
        open={!!leaving}
        onOpenChange={(open) => {
          if (!open) setLeaving("");
        }}
        title="Leave this draft?"
        description="This project hasn’t been created yet. Leaving will discard the details you’ve entered."
        confirmLabel="Discard draft"
        danger
        onConfirm={() => router.push(leaving)}
      />
      <ConfirmDialog
        open={!!sample}
        onOpenChange={(open) => {
          if (!open) setSample(null);
        }}
        title="Replace your project details?"
        description="This example will replace the name, industry, and challenge you’ve entered. You can edit the example afterward."
        confirmLabel="Use example"
        onConfirm={() => {
          if (sample) applyExample(sample);
        }}
      />
    </Shell>
  );
}
