"use client";

import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import {
  ArrowUpRight,
  Check,
  Database,
  FileCheck2,
  FileText,
  GitBranch,
  Layers3,
  MessagesSquare,
  Pause,
  Play,
  Search,
  ShieldCheck,
  Target,
  Workflow,
} from "lucide-react";
import { T } from "@/components/locale";
import styles from "./render-home.module.css";

const MotionContext = createContext({
  running: false,
  paused: false,
  toggle: () => {},
});
export function LandingMotion({ children }: { children: ReactNode }) {
  const root = useRef<HTMLDivElement>(null);
  const [paused, setPaused] = useState(false);
  const [reduced, setReduced] = useState(true);
  const [visible, setVisible] = useState(true);
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const sync = () => setReduced(media.matches);
    const visibility = () => setVisible(!document.hidden);
    sync();
    visibility();
    media.addEventListener("change", sync);
    document.addEventListener("visibilitychange", visibility);
    return () => {
      media.removeEventListener("change", sync);
      document.removeEventListener("visibilitychange", visibility);
    };
  }, []);
  useEffect(() => {
    if (!root.current || typeof IntersectionObserver === "undefined") return;
    // One observer for animated illustrations, not per-frame scroll handlers or
    // React updates. Prepare nearby layers before they enter the viewport.
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          (entry.target as HTMLElement).dataset.motionVisibility =
            entry.isIntersecting ? "near" : "away";
        }
      },
      { rootMargin: "160px 0px" },
    );
    root.current
      .querySelectorAll("[data-motion-region]")
      .forEach((element) => observer.observe(element));
    return () => observer.disconnect();
  }, []);
  const running = !paused && !reduced && visible;
  return (
    <MotionContext.Provider
      value={{ running, paused, toggle: () => setPaused((value) => !value) }}
    >
      <div
        ref={root}
        className={styles.home}
        data-motion={running ? "on" : "off"}
      >
        {children}
      </div>
    </MotionContext.Provider>
  );
}
export function MotionToggle() {
  const { paused, toggle } = useContext(MotionContext);
  return (
    <button
      className={styles.motionToggle}
      onClick={toggle}
      aria-pressed={paused}
      aria-label={paused ? "Resume animations" : "Pause animations"}
    >
      {paused ? <Play size={12} /> : <Pause size={12} />}
      <T text={paused ? "Motion paused" : "Pause motion"} />
    </button>
  );
}
export function Reveal({
  children,
  className = "",
  id,
}: {
  children: ReactNode;
  className?: string;
  id?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const element = ref.current;
    if (
      !element ||
      window.matchMedia("(prefers-reduced-motion: reduce)").matches ||
      typeof IntersectionObserver === "undefined"
    )
      return;
    // Hide only offscreen content after hydration, so the page works without JavaScript.
    if (element.getBoundingClientRect().top > window.innerHeight)
      element.dataset.reveal = "waiting";
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          element.dataset.reveal = "visible";
          observer.disconnect();
        }
      },
      { threshold: 0.08 },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return (
    <div ref={ref} className={`${styles.reveal} ${className}`} id={id}>
      {children}
    </div>
  );
}
export function RotatingHeadline() {
  const { running } = useContext(MotionContext);
  const [index, setIndex] = useState(0);
  const words = ["clear direction.", "better decisions.", "a practical plan."];
  useEffect(() => {
    if (!running) return;
    const timer = window.setInterval(
      () => setIndex((value) => (value + 1) % 3),
      4200,
    );
    return () => window.clearInterval(timer);
  }, [running]);
  return (
    <span className={styles.rotatingHeadline} data-motion-region>
      <span className={styles.srOnly}>clear direction.</span>
      <span key={index} className={styles.rotatingWord} aria-hidden>
        <T text={words[index]} />
      </span>
      <i aria-hidden />
    </span>
  );
}
const stages = [
  {
    name: "Discover",
    icon: MessagesSquare,
    title: "Start with the real question.",
    copy: "Where does your workflow slow down?",
    result: "Business context",
    detail: "Goals, people, and constraints",
  },
  {
    name: "Diagnose",
    icon: Search,
    title: "Follow the evidence.",
    copy: "The delay is in the approval handoff.",
    result: "Root-cause analysis",
    detail: "Evidence connected to the problem",
  },
  {
    name: "Challenge",
    icon: ShieldCheck,
    title: "Give the plan a second look.",
    copy: "Could a simpler approach solve this?",
    result: "Independent review",
    detail: "Risks and assumptions challenged",
  },
  {
    name: "Blueprint",
    icon: FileCheck2,
    title: "Turn clarity into action.",
    copy: "Validate. Pilot. Measure. Roll out.",
    result: "Implementation plan",
    detail: "Roadmap, architecture, and data model",
  },
];
export function BlueprintPreview() {
  const { running } = useContext(MotionContext);
  const [stage, setStage] = useState(0);
  const [interacted, setInteracted] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const [inView, setInView] = useState(true);
  useEffect(() => {
    const observer = new IntersectionObserver((entries) =>
      setInView(entries[0].isIntersecting),
    );
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    if (!running || interacted || !inView) return;
    const timer = window.setInterval(
      () => setStage((value) => (value + 1) % stages.length),
      4200,
    );
    return () => window.clearInterval(timer);
  }, [running, interacted, inView]);
  const current = stages[stage];
  const select = (index: number, focus = false) => {
    setInteracted(true);
    setStage(index);
    if (focus)
      ref.current
        ?.querySelectorAll<HTMLButtonElement>('[role="tab"]')
        [index]?.focus();
  };
  return (
    <div ref={ref} className={styles.heroVisual} data-motion-region>
      <div className={styles.visualGrid} aria-hidden />
      <div className={styles.promptTag}>
        <span>↗</span>
        <T text="One question. New possibilities." />
      </div>
      <div className={styles.previewWindow}>
        <div className={styles.previewToolbar}>
          <span>
            <i />
            <i />
            <i />
          </span>
          <span>YOUR SHIFT WORKSPACE</span>
          <ArrowUpRight size={13} />
        </div>
        <div className={styles.previewProject}>
          <span>
            <span className={styles.statusDot} /> PROJECT / OPERATIONS
          </span>
          <span>ILLUSTRATIVE PREVIEW</span>
        </div>
        <div
          className={styles.previewTabs}
          role="tablist"
          aria-label="Explore the planning stages"
          onFocusCapture={() => setInteracted(true)}
        >
          {stages.map(({ name, icon: Icon }, index) => (
            <button
              type="button"
              key={name}
              id={`stage-tab-${index}`}
              role="tab"
              aria-selected={stage === index}
              aria-controls="stage-panel"
              tabIndex={stage === index ? 0 : -1}
              onClick={() => select(index)}
              onKeyDown={(event) => {
                let next = stage;
                if (event.key === "ArrowRight") next = (stage + 1) % 4;
                else if (event.key === "ArrowLeft") next = (stage + 3) % 4;
                else if (event.key === "Home") next = 0;
                else if (event.key === "End") next = 3;
                else return;
                event.preventDefault();
                select(next, true);
              }}
            >
              <Icon size={15} />
              <span>{name}</span>
            </button>
          ))}
        </div>
        <div
          id="stage-panel"
          role="tabpanel"
          aria-labelledby={`stage-tab-${stage}`}
          className={styles.previewPanel}
          tabIndex={0}
        >
          <div key={stage} className={styles.previewPanelInner}>
            <span className={styles.miniLabel}>
              0{stage + 1} / {current.name.toUpperCase()}
            </span>
            <h2>{current.title}</h2>
            <div className={styles.previewQuestion}>
              <MessagesSquare size={17} />
              <span>{current.copy}</span>
            </div>
            <div className={styles.previewFlow} aria-hidden>
              <span />
              <span />
              <span />
            </div>
            <div className={styles.previewResult}>
              <div>
                <current.icon size={21} />
              </div>
              <span>
                <strong>{current.result}</strong>
                <small>{current.detail}</small>
              </span>
              <Check size={17} />
            </div>
          </div>
        </div>
        <div className={styles.previewFooter}>
          <span>PROBLEM → EVIDENCE → PLAN</span>
          <span>
            shift.AI <span className={styles.statusDot} />
          </span>
        </div>
      </div>
      <div className={styles.attachedCard}>
        <FileText size={18} />
        <span>
          <strong>From insight to implementation</strong>
          <small>Your blueprint, ready to share</small>
        </span>
        <ArrowUpRight size={16} />
      </div>
    </div>
  );
}
const tiles = [
  [Search, "Discovery"],
  [FileText, "Evidence"],
  [Workflow, "Workflows"],
  [Target, "Outcomes"],
  [ShieldCheck, "Review"],
  [Database, "Data models"],
  [Layers3, "Blueprints"],
  [GitBranch, "Decisions"],
] as const;
export function SolutionTicker() {
  return (
    <div
      className={styles.ticker}
      data-motion-region
      data-testid="solution-ticker"
      aria-label="Discovery, evidence, workflows, outcomes, review, data models, blueprints, and decisions"
    >
      {[0, 1].map((row) => (
        <div key={row} className={styles.tickerLane} aria-hidden>
          <div
            className={styles.tickerTrack}
            style={
              { "--direction": row ? "reverse" : "normal" } as CSSProperties
            }
          >
            {[0, 1].map((copy) => (
              <div className={styles.tileSet} key={copy}>
                {(row ? [...tiles].reverse() : tiles).map(
                  ([Icon, label], i) => (
                    <div
                      className={styles.solutionTile}
                      data-tone={(i + row) % 3}
                      key={label}
                    >
                      <Icon size={26} strokeWidth={1.5} />
                      <span>{label}</span>
                    </div>
                  ),
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
