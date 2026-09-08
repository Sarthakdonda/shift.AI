"use client";
import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  ArrowUpRight,
  LoaderCircle,
} from "lucide-react";
import { Shell } from "@/components/layout/shell";
import { Button } from "@/components/ui/button";
import { ErrorBox } from "@/components/ui/states";
import { post } from "@/lib/api";
import { Project } from "@/lib/types";
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
  const [form, setForm] = useState({
    name: "",
    initial_problem: "",
    industry: "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return (
    <Shell>
      <Link className="back-page" href="/dashboard">
        <ArrowLeft size={16} /> All projects
      </Link>
      <div className="page-heading">
        <div>
          <span className="eyebrow">THE FIRST STEP IS UNDERSTANDING</span>
          <h1>What would you like to improve?</h1>
          <p>
            Start with the challenge. You don’t need to know the solution yet.
          </p>
        </div>
      </div>
      <div className="new-project-layout">
        <form
          className="panel project-form"
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            try {
              const p = await post<Project>("/projects", form);
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
              <h2>Give your project some context</h2>
              <p>A few details help us ask better questions.</p>
            </div>
          </div>
          <label>
            Project name
            <input
              required
              minLength={2}
              maxLength={100}
              placeholder="e.g. A better customer support workflow"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </label>
          <label>
            Industry <span className="optional">Optional</span>
            <input
              maxLength={100}
              placeholder="e.g. Healthcare, retail, logistics"
              value={form.industry}
              onChange={(e) => setForm({ ...form, industry: e.target.value })}
            />
          </label>
          <label>
            What’s the challenge?
            <textarea
              required
              minLength={15}
              maxLength={12000}
              rows={7}
              placeholder="Tell us what happens today, what isn’t working, and what you’d like to change. Plain language is perfect."
              value={form.initial_problem}
              onChange={(e) =>
                setForm({ ...form, initial_problem: e.target.value })
              }
            />
          </label>
          <div className="field-hint">
            Think about the problem, who it affects, and your ideal outcome.
            <span>{form.initial_problem.length}/12000</span>
          </div>
          {error && <ErrorBox message={error} />}
          <div className="form-footer">
            <span>
              <Check size={15} /> Saved in your workspace
            </span>
            <Button disabled={busy} type="submit">
              {busy ? <LoaderCircle size={17} className="spin" /> : null}
              {busy ? "Creating project…" : "Start discovery"}
              <ArrowRight size={17} />
            </Button>
          </div>
        </form>
        <aside className="new-project-aside">
          <div className="warm-panel">
            <span className="eyebrow">WHAT HAPPENS NEXT</span>
            <h3>Clarity, one question at a time.</h3>
            <ol>
              <li>We’ll understand your current process.</li>
              <li>You can add documents for context.</li>
              <li>We’ll diagnose and evaluate the options.</li>
              <li>You’ll get a reviewed, actionable blueprint.</li>
            </ol>
          </div>
          <div className="example-list">
            <h3>Need a starting point?</h3>
            <p className="muted">
              Try a sample challenge and make it your own.
            </p>
            {examples.map((x) => (
              <button
                type="button"
                disabled={busy}
                key={x.name}
                onClick={() =>
                  setForm({
                    name: x.name,
                    industry: x.industry,
                    initial_problem: x.problem,
                  })
                }
              >
                {x.name}
                <ArrowUpRight size={16} />
              </button>
            ))}
          </div>
        </aside>
      </div>
    </Shell>
  );
}
