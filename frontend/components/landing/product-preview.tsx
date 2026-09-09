"use client";

import { T } from "@/components/locale";
import { useState } from "react";
import {
  ArrowRight,
  Check,
  FileText,
  MessageSquare,
  ScanLine,
  ShieldCheck,
  Sparkles,
  Workflow,
} from "lucide-react";

const stages = [
  {
    label: "Discover",
    icon: MessageSquare,
    title: "Good questions. A clearer picture.",
    copy: "Let’s understand where your team spends the most time.",
    answer:
      "We copy invoice details from email into a spreadsheet. Approvals take days.",
    insight: "The opportunity is in the handoff.",
    detail: "A repeated manual step connects two tools your team already uses.",
    metric: "Context captured",
    value: "8 / 10",
  },
  {
    label: "Diagnose",
    icon: ScanLine,
    title: "Follow the evidence.",
    copy: "Your workflow points to a repeatable bottleneck.",
    answer:
      "The fields are always the same. Most delays happen while an invoice waits for approval.",
    insight: "A process gap, with a practical fix.",
    detail:
      "Connect the tools and route approvals automatically. Keep exceptions with your team.",
    metric: "Evidence sources",
    value: "03",
  },
  {
    label: "Challenge",
    icon: ShieldCheck,
    title: "Give the plan a second look.",
    copy: "Every recommendation should stand up to a challenge.",
    answer:
      "What happens when an invoice is incomplete or an approval is missed?",
    insight: "Build in a human checkpoint.",
    detail:
      "Flag incomplete records, assign an owner, and keep a visible exception queue.",
    metric: "Review areas",
    value: "05",
  },
  {
    label: "Blueprint",
    icon: FileText,
    title: "Your next move, mapped out.",
    copy: "Turn the decision into a plan your team can use.",
    answer:
      "Start with one invoice type, review exceptions weekly, then expand the pilot.",
    insight: "Simple automation. Clear direction.",
    detail:
      "A phased roadmap with owners, success measures, and assumptions to validate.",
    metric: "Pilot phases",
    value: "03",
  },
];
export function ProductPreview() {
  const [active, setActive] = useState(0);
  const stage = stages[active];
  return (
    <div className="product-preview">
      <div className="preview-windowbar">
        <span className="window-dots" aria-hidden>
          <i />
          <i />
          <i />
        </span>
        <span>
          <T text={"YOUR NEXT CHAPTER, IN ONE WORKSPACE"} />
        </span>
        <span className="preview-example">
          <T text={"Interactive example"} />
        </span>
      </div>
      <div className="preview-layout">
        <div
          className="preview-navigation"
          role="tablist"
          aria-label="Explore the process"
        >
          <span className="preview-project">
            <Workflow size={19} />
            <T text={" Invoice operations"} />
          </span>
          {stages.map(({ label, icon: Icon }, i) => (
            <button
              key={label}
              id={`preview-tab-${i}`}
              role="tab"
              aria-selected={active === i}
              aria-controls="preview-content"
              tabIndex={active === i ? 0 : -1}
              onKeyDown={(e) => {
                const next =
                  e.key === "ArrowRight" || e.key === "ArrowDown"
                    ? (i + 1) % stages.length
                    : e.key === "ArrowLeft" || e.key === "ArrowUp"
                      ? (i + stages.length - 1) % stages.length
                      : e.key === "Home"
                        ? 0
                        : e.key === "End"
                          ? stages.length - 1
                          : -1;
                if (next >= 0) {
                  e.preventDefault();
                  setActive(next);
                  document.getElementById(`preview-tab-${next}`)?.focus();
                }
              }}
              onClick={() => setActive(i)}
            >
              <Icon size={16} />
              {label}
              <span>0{i + 1}</span>
            </button>
          ))}
          <div className="preview-nav-foot">
            <span className="tiny-orange" />
            <T text={" Problem first. Always."} />
          </div>
        </div>
        <div
          id="preview-content"
          role="tabpanel"
          aria-labelledby={`preview-tab-${active}`}
          className="preview-content"
        >
          <div className="preview-content-head">
            <span>
              <span className="tiny-orange" /> {stage.label}
            </span>
            <span>
              <T text={"EXAMPLE PROJECT"} />
            </span>
          </div>
          <div key={active} className="preview-stage enter">
            <h3>{stage.title}</h3>
            <div className="preview-message">
              <span className="preview-ai">
                <Sparkles size={17} />
              </span>
              <p>{stage.copy}</p>
            </div>
            <div className="preview-answer">{stage.answer}</div>
            <div className="preview-insight">
              <span className="eyebrow">
                <ScanLine size={13} />
                <T text={" The insight"} />
              </span>
              <h4>{stage.insight}</h4>
              <p>{stage.detail}</p>
              <span className="preview-evidence">
                <Check size={13} />
                <T text={" Grounded in your context"} />
              </span>
            </div>
          </div>
          <div className="preview-input">
            <T text={"A little context goes a long way."} />
            <span>
              <ArrowRight size={16} />
            </span>
          </div>
        </div>
        <aside className="preview-context">
          <span className="eyebrow">
            <T text={"The bigger picture"} />
          </span>
          <div className="preview-ring">
            <span>
              {stage.value}
              <small>{stage.metric}</small>
            </span>
          </div>
          <h4>
            <T text={"Clarity at every step"} />
          </h4>
          <p>
            <T text={"Your context stays connected to the decision."} />
          </p>
          {["Business context", "Current workflow", "Desired outcome"].map(
            (x) => (
              <div className="preview-context-row" key={x}>
                <Check size={14} />
                {x}
              </div>
            ),
          )}
          <div className="preview-context-note">
            <ShieldCheck size={17} />
            <span>
              <T text={"Challenged before"} />
              <br />
              <T text={"you commit."} />
            </span>
          </div>
        </aside>
      </div>
    </div>
  );
}
