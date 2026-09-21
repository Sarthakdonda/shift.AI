import Link from "next/link";
import {
  ArrowRight,
  ArrowUpRight,
  Check,
  FileText,
  Workflow,
  ShieldCheck,
  Search,
  Layers3,
  Database,
  Target,
  MessagesSquare,
  Route,
  FolderOpen,
  GitBranch,
  Download,
} from "lucide-react";
import { T } from "@/components/locale";
import { Logo } from "@/components/layout/logo";
import { SiteHeader } from "@/components/layout/site-header";
import {
  LandingMotion,
  MotionToggle,
  RotatingHeadline,
  BlueprintPreview,
  SolutionTicker,
  Reveal,
} from "@/components/landing/landing-interactions";
import styles from "@/components/landing/render-home.module.css";

const faqs = [
  [
    "Will shift.AI always recommend AI?",
    "No. The recommendation follows your problem and evidence. It may be simple automation, a better process, existing software, AI, or a combination. The plan explains the reasoning and alternatives.",
  ],
  [
    "What do I need to get started?",
    "Just a business challenge you want to understand. Describe what happens today and what you would like to improve. Add PDF, DOCX, TXT, CSV, or XLSX documents when you have them.",
  ],
  [
    "What will I get at the end?",
    "A reviewed implementation blueprint with the recommended solution, architecture, relevant data models and ER diagrams, risks, a phased roadmap, and success measures. Download your report as PDF or Word, or copy it to share.",
  ],
  [
    "Can I return to a project later?",
    "Yes. Your saved projects keep the discovery conversation, documents, analysis, and blueprint together, so you can pick up where you left off.",
  ],
  [
    "Can I treat the recommendations as final decisions?",
    "Use them to support your decisions. Estimates are advisory. Validate assumptions, feasibility, costs, and any security or compliance requirements with your team before committing resources.",
  ],
];
const capabilities = [
  [
    MessagesSquare,
    "Guided discovery",
    "Questions that build a picture of your workflow, constraints, and goals.",
  ],
  [
    FolderOpen,
    "Document context",
    "Bring process notes, requirements, and spreadsheets into the conversation.",
  ],
  [
    Search,
    "Problem diagnosis",
    "Separate the underlying bottleneck from its symptoms.",
  ],
  [
    GitBranch,
    "Solution comparison",
    "Consider AI, automation, existing software, and process changes.",
  ],
  [
    ShieldCheck,
    "Independent challenge",
    "Review the proposal for risk, complexity, and unsupported assumptions.",
  ],
  [
    Database,
    "Architecture & data",
    "Understand components, business records, and their relationships.",
  ],
  [
    Route,
    "Phased roadmaps",
    "Turn a recommendation into sequenced, practical next steps.",
  ],
  [
    Download,
    "Shareable blueprints",
    "Take a structured PDF or Word document into your next meeting.",
  ],
] as const;

function Action({
  children,
  href = "/project/new",
  secondary = false,
}: {
  children: React.ReactNode;
  href?: string;
  secondary?: boolean;
}) {
  return (
    <Link
      href={href}
      className={secondary ? styles.secondaryButton : styles.primaryButton}
    >
      <T text={String(children)} />
      <ArrowUpRight size={17} aria-hidden />
    </Link>
  );
}

export default function Landing() {
  return (
    <LandingMotion>
      <div className={styles.announcement}>
        <span>
          <T text="From business challenge to implementation blueprint." />
        </span>
        <a href="#capabilities">
          <T text="Explore what’s inside" />
          <ArrowRight size={14} aria-hidden />
        </a>
      </div>
      <SiteHeader />
      <main id="main">
        <section className={styles.hero} aria-labelledby="hero-title">
          <div className={styles.heroCopy}>
            <div className={styles.eyebrow}>
              <span className={styles.statusDot} />
              <T text="CLARITY BEFORE COMPLEXITY" />
            </div>
            <h1 id="hero-title">
              <T text="Your clearest path" />
              <br />
              <T text="from challenge to" />
              <br />
              <RotatingHeadline />
            </h1>
            <p>
              <T text="Understand the real problem. Explore the right solution. Turn your next big question into a plan you can act on." />
            </p>
            <div className={styles.actions}>
              <Action>Start your next shift</Action>
              <Action href="#how-it-works" secondary>
                See how it works
              </Action>
            </div>
            <div className={styles.heroNote}>
              <Check size={14} aria-hidden />
              <T text="Problem first. Evidence led. Built for action." />
            </div>
          </div>
          <BlueprintPreview />
          <div className={styles.heroBaseline}>
            <span>01 — A CLEARER WAY FORWARD</span>
            <MotionToggle />
          </div>
        </section>
        <section className={styles.outcomes} aria-label="Solution approaches">
          <p className={styles.eyebrow}>
            <T text="THE RIGHT ANSWER ISN’T ALWAYS MORE TECHNOLOGY" />
          </p>
          <div>
            {[
              [Workflow, "Simple automation"],
              [Layers3, "Better processes"],
              [FolderOpen, "Existing software"],
              [GitBranch, "Thoughtful AI"],
            ].map(([Icon, label]) => {
              const Symbol = Icon as typeof Workflow;
              return (
                <span key={String(label)}>
                  <Symbol size={23} strokeWidth={1.6} aria-hidden />
                  <T text={String(label)} />
                </span>
              );
            })}
          </div>
          <a className={styles.textLink} href="#approach">
            <T text="Find what fits your business" />
            <ArrowRight size={15} aria-hidden />
          </a>
        </section>
        <section id="how-it-works" className={styles.section}>
          <Reveal>
            <span className={styles.eyebrow}>THE PROCESS</span>
            <h2>
              <T text="A question. A conversation." />
              <br />
              <T text="A clear next move." />
            </h2>
          </Reveal>
          <div className={styles.steps}>
            <Reveal className={styles.step}>
              <span className={styles.stepNumber}>1</span>
              <h3>
                <T text="Bring your challenge" />
              </h3>
              <p>
                <T text="Tell us what happens today, what slows you down, and what better would look like." />
              </p>
              <div className={styles.discoveryDemo}>
                <span className={styles.miniLabel}>
                  START WITH WHAT YOU KNOW
                </span>
                {[
                  "Understand a bottleneck",
                  "Explore an opportunity",
                  "Improve a workflow",
                ].map((text, i) => (
                  <div key={text} data-selected={i === 0}>
                    <MessagesSquare size={14} />
                    <span>{text}</span>
                    {i === 0 && <Check size={14} />}
                  </div>
                ))}
                <span className={styles.demoCaption}>
                  Illustrative discovery prompts
                </span>
              </div>
            </Reveal>
            <Reveal className={styles.step}>
              <span className={styles.stepNumber}>2</span>
              <h3>
                <T text="Connect the evidence" />
              </h3>
              <p>
                <T text="Add your context and documents. Explore the root cause and compare practical ways forward." />
              </p>
              <div className={styles.evidenceDemo}>
                <div>
                  <FileText size={16} />
                  <span>Current workflow.pdf</span>
                  <Check size={14} />
                </div>
                <div>
                  <Database size={16} />
                  <span>Operations data.csv</span>
                  <Check size={14} />
                </div>
                <div className={styles.evidenceLine} />
                <strong>
                  <Search size={15} /> A clearer picture emerges
                </strong>
                <span className={styles.demoCaption}>
                  Example documents and analysis
                </span>
              </div>
            </Reveal>
            <Reveal className={styles.step}>
              <span className={styles.stepNumber}>3</span>
              <h3>
                <T text="Leave with a blueprint" />
              </h3>
              <p>
                <T text="Review a challenged recommendation, a phased roadmap, and the details your team needs to move." />
              </p>
              <div className={styles.planDemo}>
                <span className={styles.miniLabel}>
                  YOUR IMPLEMENTATION PLAN
                </span>
                {[
                  "Recommended approach",
                  "Architecture & ER diagram",
                  "Risks & rollout roadmap",
                ].map((text) => (
                  <div key={text}>
                    <span className={styles.statusDot} />
                    {text}
                    <Check size={13} />
                  </div>
                ))}
                <span className={styles.demoCaption}>
                  Structured. Reviewed. Ready to share.
                </span>
              </div>
            </Reveal>
          </div>
        </section>
        <section
          className={styles.tickerSection}
          aria-labelledby="solutions-heading"
        >
          <div>
            <h2 id="solutions-heading">
              <T text="Whatever your challenge," />
              <br />
              <T text="start with clarity." />
            </h2>
            <a className={styles.textLink} href="#capabilities">
              <T text="Explore your workspace" />
              <ArrowRight size={16} />
            </a>
          </div>
          <SolutionTicker />
        </section>
        <section
          id="capabilities"
          className={`${styles.section} ${styles.featureSection}`}
        >
          <Reveal>
            <span className={styles.eyebrow}>ONE CONNECTED WORKSPACE</span>
            <h2>
              <T text="From scattered information" />
              <br />
              <T text="to " />
              <span className={styles.accent}>
                <T text="shared direction." />
              </span>
            </h2>
          </Reveal>
          <div className={styles.featureGrid}>
            <Reveal className={`${styles.feature} ${styles.manifesto}`}>
              <span className={styles.miniLabel}>CONTEXT, NOT GUESSWORK</span>
              <h3>
                <T text="Bring together your " />
                <span>
                  <T text="questions, documents, workflows, constraints, opportunities, and goals." />
                </span>
                <T text=" See the whole picture." />
              </h3>
              <a href="#approach" className={styles.textLink}>
                <T text="Our problem-first approach" />
                <ArrowRight size={15} />
              </a>
              <div
                className={styles.contextDots}
                data-motion-region
                aria-hidden
              >
                {Array.from({ length: 32 }, (_, i) => (
                  <i key={i} style={{ "--i": i } as React.CSSProperties} />
                ))}
              </div>
            </Reveal>
            <Reveal className={styles.feature}>
              <span className={styles.miniLabel}>
                DOCUMENTS → UNDERSTANDING
              </span>
              <h3>
                <T text="Your evidence, at the heart of every decision." />
              </h3>
              <p>
                <T text="Keep source documents connected to the analysis. Make the thinking behind the recommendation easy to follow." />
              </p>
              <div className={styles.sourceDiagram} data-motion-region>
                <div>
                  <FileText size={19} />
                  <span>Process notes</span>
                </div>
                <div>
                  <Database size={19} />
                  <span>Business data</span>
                </div>
                <svg viewBox="0 0 300 60" aria-hidden>
                  <path d="M75 0 V20 Q75 30 85 30 H215 Q225 30 225 20 V0 M150 30 V60" />
                </svg>
                <strong>
                  <Search size={18} /> Evidence-led analysis
                </strong>
              </div>
            </Reveal>
            <Reveal className={`${styles.feature} ${styles.wideFeature}`}>
              <div>
                <span className={styles.miniLabel}>
                  THE NEXT MOVE, IN ORDER
                </span>
                <h3>
                  <T text="A roadmap your team can actually follow." />
                </h3>
                <p>
                  <T text="Break the recommendation into phases. Understand what needs validating, what to build first, and how to measure progress." />
                </p>
                <a href="#deliverables" className={styles.textLink}>
                  <T text="See what’s in the blueprint" />
                  <ArrowRight size={15} />
                </a>
              </div>
              <div
                className={styles.roadmapArt}
                data-motion-region
                aria-label="Example roadmap: validate, pilot, then roll out"
              >
                <div className={styles.roadmapLabels}>
                  <span>01 / VALIDATE</span>
                  <span>02 / PILOT</span>
                  <span>03 / ROLL OUT</span>
                </div>
                <svg
                  viewBox="0 0 560 210"
                  role="img"
                  aria-label="Three connected roadmap milestones"
                >
                  <path
                    className={styles.chartGrid}
                    d="M0 50 H560 M0 110 H560 M0 170 H560 M90 0 V210 M280 0 V210 M470 0 V210"
                  />
                  <path
                    className={styles.chartArea}
                    d="M0 185 L90 155 L180 155 L280 95 L375 95 L470 35 L560 35 V210 H0Z"
                  />
                  <path
                    className={styles.chartLine}
                    d="M0 185 L90 155 L180 155 L280 95 L375 95 L470 35 L560 35"
                  />
                  {[
                    [90, 155],
                    [280, 95],
                    [470, 35],
                  ].map(([cx, cy]) => (
                    <circle key={cx} cx={cx} cy={cy} r="6" />
                  ))}
                </svg>
                <small>Illustrative phases, not a performance forecast</small>
              </div>
            </Reveal>
            <Reveal className={styles.feature}>
              <span className={styles.miniLabel}>A SECOND PERSPECTIVE</span>
              <h3>
                <T text="Good ideas deserve tough questions." />
              </h3>
              <p>
                <T text="An independent red-team review challenges risk, unsupported assumptions, and unnecessary complexity before the final plan." />
              </p>
              <div className={styles.reviewDemo}>
                {[
                  "Is the approach proportionate?",
                  "Are the assumptions supported?",
                  "What could go wrong?",
                ].map((text, i) => (
                  <div key={text}>
                    <ShieldCheck size={17} />
                    <span>{text}</span>
                    <span className={styles.reviewIndex}>0{i + 1}</span>
                  </div>
                ))}
              </div>
            </Reveal>
            <Reveal className={styles.feature} id="deliverables">
              <span className={styles.miniLabel}>DETAIL THAT CONNECTS</span>
              <h3>
                <T text="Not just an answer. An implementation plan." />
              </h3>
              <p>
                <T text="Architecture, relevant ER diagrams, decisions, and rollout steps. A structured document with the detail that matters." />
              </p>
              <div
                className={styles.erArt}
                aria-label="Illustrative data model: one project has many documents"
              >
                <div>
                  <strong>Project</strong>
                  <span>
                    id <b>PK</b>
                  </span>
                  <span>name</span>
                </div>
                <svg viewBox="0 0 90 75" role="img" aria-label="One to many">
                  <path d="M0 38 H90 M12 30 V46 M77 38 L90 28 M77 38 L90 48" />
                  <text x="16" y="25">
                    1
                  </text>
                  <text x="64" y="25">
                    N
                  </text>
                </svg>
                <div>
                  <strong>Document</strong>
                  <span>
                    id <b>PK</b>
                  </span>
                  <span>
                    project_id <b>FK</b>
                  </span>
                </div>
              </div>
              <span className={styles.demoCaption}>
                Example ER diagram · PDF / Word export
              </span>
            </Reveal>
          </div>
        </section>
        <section id="approach" className={styles.approach}>
          <Reveal className={styles.approachInner}>
            <span className={styles.eyebrow}>THE SHIFT IN PERSPECTIVE</span>
            <div className={styles.approachFlow}>
              <span>“We need an AI tool.”</span>
              <ArrowRight size={25} aria-hidden />
              <strong>“What’s the real bottleneck?”</strong>
            </div>
            <blockquote>
              <T text="The best solution isn’t always the most complex one. It’s the one that solves the right problem." />
            </blockquote>
            <p>
              <T text="An invoice delay might need a simpler approval handoff, not a new AI system. shift.AI helps you examine the evidence before choosing the technology." />
            </p>
            <span className={styles.miniLabel}>
              ILLUSTRATIVE EXAMPLE · PROBLEM FIRST, POSSIBILITY NEXT
            </span>
          </Reveal>
        </section>
        <section className={styles.section} id="workspace">
          <Reveal>
            <span className={styles.eyebrow}>BUILT FOR THE WAY YOU THINK</span>
            <h2>
              <T text="Everything you need" />
              <br />
              <T text="to make your next move." />
            </h2>
            <p className={styles.sectionIntro}>
              <T text="Keep the conversation, evidence, and decisions in one place." />
            </p>
          </Reveal>
          <div className={styles.capabilityGrid}>
            {capabilities.map(([Icon, title, copy]) => (
              <Reveal key={title}>
                <Icon size={23} strokeWidth={1.5} aria-hidden />
                <h3>
                  <T text={title} />
                </h3>
                <p>
                  <T text={copy} />
                </p>
              </Reveal>
            ))}
          </div>
        </section>
        <section id="faq" className={`${styles.section} ${styles.faqSection}`}>
          <Reveal>
            <span className={styles.eyebrow}>BEFORE YOUR FIRST SHIFT</span>
            <h2>
              <T text="Good questions." />
              <br />
              <T text="Straight answers." />
            </h2>
          </Reveal>
          <div className={styles.faqList}>
            {faqs.map(([question, answer]) => (
              <details key={question} name="landing-faq">
                <summary>
                  <T text={question} />
                  <span aria-hidden>+</span>
                </summary>
                <p>
                  <T text={answer} />
                </p>
              </details>
            ))}
          </div>
        </section>
        <section
          id="android-app"
          className={`${styles.section} ${styles.androidSection}`}
        >
          <Reveal className={styles.androidCard}>
            <div>
              <span className={styles.androidLabel}>shift.AI for Android</span>
              <h2>
                <T text="Your next move. Wherever you are." />
              </h2>
              <p>
                <T text="Keep your questions, projects, and next steps close. Sign in to pick up where you left off." />
              </p>
            </div>
            <div className={styles.androidDownload}>
              <a
                className={styles.androidButton}
                href="/downloads/shift-ai.apk"
                download="shift-ai.apk"
              >
                <Download size={20} aria-hidden />
                <T text="Download for Android" />
              </a>
              <span>
                <T text="Android 8 or later · Internet required" />
              </span>
              <p>
                <T text="Open the downloaded APK to install." />
              </p>
            </div>
          </Reveal>
        </section>
        <section className={styles.finalSection}>
          <div className={styles.floatingTiles} data-motion-region aria-hidden>
            {[
              [Search, "Discover"],
              [FileText, "Evidence"],
              [Workflow, "Automate"],
              [ShieldCheck, "Review"],
              [Target, "Outcomes"],
              [Database, "Data"],
              [Route, "Roadmap"],
              [Layers3, "Blueprint"],
            ].map(([Icon, label], i) => {
              const Symbol = Icon as typeof Search;
              return (
                <div
                  key={String(label)}
                  style={{ "--i": i } as React.CSSProperties}
                >
                  <Symbol size={24} />
                  <span>{String(label)}</span>
                </div>
              );
            })}
          </div>
          <Reveal className={styles.finalCard}>
            <span className={styles.eyebrow}>
              YOUR NEXT CHAPTER STARTS HERE
            </span>
            <h2>
              <T text="Big question?" />
              <br />
              <T text="Make your next shift." />
            </h2>
            <p>
              <T text="Bring the challenge. Leave with direction." />
            </p>
            <Action>Start your first project</Action>
          </Reveal>
        </section>
      </main>
      <footer className={styles.footer}>
        <div className={styles.footerTop}>
          <div>
            <Logo />
            <p>
              <T text="Problem first." />
              <br />
              <T text="Possibility next." />
            </p>
          </div>
          <nav aria-label="Explore">
            <span>EXPLORE</span>
            <a href="#how-it-works">How it works</a>
            <a href="#approach">Our approach</a>
            <a href="#capabilities">Capabilities</a>
          </nav>
          <nav aria-label="Workspace">
            <span>YOUR WORKSPACE</span>
            <Link href="/project/new">New project</Link>
            <Link href="/dashboard">Saved projects</Link>
            <Link href="/login">Sign in</Link>
          </nav>
          <nav aria-label="Resources">
            <span>GOOD TO KNOW</span>
            <a href="#deliverables">Your blueprint</a>
            <a href="#faq">Questions & answers</a>
            <a href="#android-app">Download Android app</a>
            <Link href="/signup">
              Create an account <ArrowUpRight size={13} />
            </Link>
          </nav>
        </div>
        <div className={styles.footerBottom}>
          <span>© {new Date().getFullYear()} shift.AI</span>
          <span>A clearer way forward.</span>
          <a href="#main">Back to top ↑</a>
        </div>
        <div className={styles.footerWordmark} aria-hidden>
          shift<span>.AI</span>
          <span className={styles.pixelMark}>↗</span>
        </div>
      </footer>
    </LandingMotion>
  );
}
