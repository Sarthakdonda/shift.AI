"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Lightbulb, LoaderCircle, Sparkles } from "lucide-react";
import { Screen } from "@/components/shell/screen";
import { useRequireAuth } from "@/components/shell/guard";
import { Field } from "@/components/auth/field";
import { ErrorNote, Splash } from "@/components/ui/states";
import { useToast } from "@/components/providers";
import { post } from "@/lib/api";
import type { Project } from "@/lib/types";

const EXAMPLES = [
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
  const { ready } = useRequireAuth();
  const router = useRouter();
  const toast = useToast();
  const [name, setName] = useState("");
  const [industry, setIndustry] = useState("");
  const [problem, setProblem] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const nameError =
    name.trim().length < 2 ? "Give the project a name (2 characters or more)." : "";
  const problemError =
    problem.trim().length < 15
      ? "Describe the situation in at least 15 characters."
      : "";

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setSubmitted(true);
    setError("");
    if (nameError) {
      document.getElementById("project-name")?.focus();
      return;
    }
    if (problemError) {
      document.getElementById("project-problem")?.focus();
      return;
    }
    setBusy(true);
    try {
      const project = await post<Project>("/projects", {
        name: name.trim(),
        industry: industry.trim(),
        initial_problem: problem.trim(),
      });
      toast("Project created.");
      router.replace(`/chat/${project.id}`);
    } catch (failure) {
      setError((failure as Error).message);
      setBusy(false);
    }
  }

  if (!ready) return <Splash message="Preparing your workspace…" />;

  return (
    <Screen depth="root" tabs title="New project" padded={false}>
      <form className="form-screen" onSubmit={submit} noValidate aria-busy={busy}>
        <div className="form-intro project-brief-hero">
          <span className="hero-kicker"><Sparkles size={13} /> New strategy brief</span>
          <h1>Start with the situation,<br />not the solution.</h1>
          <p>
            Give your AI strategist enough context to ask sharper questions and
            uncover the real constraint.
          </p>
          <div className="brief-steps" aria-label="Project workflow">
            <span data-active="true"><b>01</b> Brief</span>
            <span><b>02</b> Discover</span>
            <span><b>03</b> Blueprint</span>
          </div>
        </div>

        <div className="form-panel">
          <div className="form-panel-head">
            <div><span>01</span><h2>Frame the challenge</h2></div>
            <small>Required fields are marked</small>
          </div>
        <Field
          id="project-name"
          label="Project name"
          placeholder="Reduce invoice approval time"
          value={name}
          maxLength={100}
          disabled={busy}
          error={submitted ? nameError : ""}
          onChange={(event) => setName(event.target.value)}
          required
        />

        <Field
          id="project-industry"
          label="Industry or team"
          placeholder="Finance operations"
          hint="Optional — it helps tailor the questions."
          value={industry}
          maxLength={100}
          disabled={busy}
          onChange={(event) => setIndustry(event.target.value)}
        />

        <div className="field">
          <label htmlFor="project-problem">The situation today</label>
          <textarea
            id="project-problem"
            placeholder="What happens now, who is involved, and what makes it painful?"
            value={problem}
            maxLength={12000}
            disabled={busy}
            aria-invalid={submitted && problemError ? true : undefined}
            onChange={(event) => setProblem(event.target.value)}
            required
          />
          <div className="row-between">
            {submitted && problemError ? (
              <p className="field-error">{problemError}</p>
            ) : (
              <p className="field-note">Plain language works best.</p>
            )}
            <span className="counter">{problem.trim().length}/12000</span>
          </div>
        </div>

        {error && <ErrorNote message={error} />}

        <button className="btn btn-primary btn-block" type="submit" disabled={busy}>
          {busy ? "Creating…" : "Create and start"}
          {busy ? (
            <LoaderCircle size={17} className="spin" aria-hidden="true" />
          ) : (
            <ArrowRight size={17} aria-hidden="true" />
          )}
        </button>
        </div>

        <div className="stack template-section">
          <p className="eyebrow">
            <Lightbulb
              size={12}
              aria-hidden="true"
              style={{ display: "inline", verticalAlign: "-2px", marginRight: 5 }}
            />
            Need a starting point?
          </p>
          <div className="example-grid">
            {EXAMPLES.map((example) => (
              <button
                className="suggestion"
                type="button"
                key={example.name}
                disabled={busy}
                onClick={() => {
                  setName(example.name);
                  setIndustry(example.industry);
                  setProblem(example.problem);
                }}
              >
                <span>
                  <strong style={{ display: "block", fontWeight: 570 }}>
                    {example.name}
                  </strong>
                  <small className="muted">{example.industry}</small>
                </span>
                <Sparkles size={15} aria-hidden="true" />
              </button>
            ))}
          </div>
          <p className="field-note">
            Examples fill the form so you can edit them. Nothing is created until
            you choose Create.
          </p>
        </div>
      </form>
    </Screen>
  );
}
