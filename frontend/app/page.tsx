import { T } from "@/components/locale";
import Link from "next/link";
import {
  ArrowDown,
  ArrowRight,
  ArrowUpRight,
  Check,
  FileCheck2,
  FileText,
  Layers3,
  MessageSquare,
  ScanLine,
  ShieldCheck,
  Sparkles,
  Workflow,
} from "lucide-react";
import { Logo } from "@/components/layout/logo";
import { SiteHeader } from "@/components/layout/site-header";
import { ProductPreview } from "@/components/landing/product-preview";
import { ScrollFX } from "@/components/ui/motion";
import { delay } from "@/lib/utils";

const steps = [
  {
    icon: MessageSquare,
    title: "Start with your challenge.",
    copy: "A focused conversation gets to the heart of your business, your workflow, and what needs to change.",
    tag: "01 / DISCOVER",
  },
  {
    icon: ScanLine,
    title: "Find what’s really going on.",
    copy: "Connect your answers and documents. Uncover bottlenecks, question assumptions, and weigh the options.",
    tag: "02 / DIAGNOSE",
  },
  {
    icon: ShieldCheck,
    title: "Pressure-test the answer.",
    copy: "An independent review challenges the risks, complexity, and cost before the plan reaches your team.",
    tag: "03 / CHALLENGE",
  },
  {
    icon: FileCheck2,
    title: "Make your next move.",
    copy: "Leave with a practical blueprint: a phased roadmap, success measures, and the evidence behind each decision.",
    tag: "04 / BUILD YOUR PLAN",
  },
];
const faqs = [
  [
    "Will shift.AI always recommend AI?",
    "No. The recommendation follows your problem and evidence. It may be simple automation, a better process, existing software, AI, or a combination. Every decision includes the reasoning and alternatives.",
  ],
  [
    "What do I need to get started?",
    "Just a challenge you want to understand. Describe what happens today and what you would like to improve. You can add PDF, DOCX, TXT, CSV, or XLSX documents as you go.",
  ],
  [
    "What will I get at the end?",
    "A reviewed blueprint covering your problem, the recommended solution, a phased roadmap, business value, risks, and next steps. Copy it, download Markdown, or print it to PDF.",
  ],
  [
    "Can I return to a project later?",
    "Yes. Your saved projects bring together the discovery conversation, documents, analysis, and blueprint so you can continue where you left off.",
  ],
  [
    "How should I use the recommendations?",
    "Use them to support your decisions. Scores and estimates are advisory, and assumptions should be validated with your team before you commit resources.",
  ],
];

export default function Landing() {
  return (
    <div className="landing">
      <ScrollFX progress />
      <SiteHeader />
      <main id="main">
        <section className="home-hero">
          <div className="hero-orbit orbit-one" aria-hidden />
          <div className="hero-orbit orbit-two" aria-hidden />
          <div className="hero-intro">
            <span className="hero-kicker enter">
              <span className="tiny-orange" />
              <T text={" CLARITY BEFORE COMPLEXITY"} />{" "}
              <ArrowUpRight size={13} />
            </span>
            <h1 className="enter" style={delay(70)}>
              <T text={"Big possibilities."} />
              <br />
              <span>
                <T text={"The right next move."} />
              </span>
            </h1>
            <p className="enter" style={delay(140)}>
              <T
                text={
                  "Turn your business challenges into clear, actionable plans."
                }
              />
              <br className="desktop-break" />
              <T
                text={
                  " Find where AI fits, where it doesn’t, and what to do next."
                }
              />
            </p>
            <div className="hero-cta enter" style={delay(210)}>
              <Link
                href="/project/new"
                className="button button-primary button-lg"
              >
                <T text={"Find your next shift "} />
                <ArrowUpRight size={18} />
              </Link>
              <a
                href="#how-it-works"
                className="button button-secondary button-lg"
              >
                <T text={"Explore the process "} />
                <ArrowDown size={16} />
              </a>
            </div>
            <div className="hero-assurance enter" style={delay(280)}>
              <span>
                <Check size={14} />
                <T text={" Problem first"} />
              </span>
              <span>
                <Check size={14} />
                <T text={" Evidence led"} />
              </span>
              <span>
                <Check size={14} />
                <T text={" Built for action"} />
              </span>
            </div>
          </div>
          <div className="hero-product enter" style={delay(350)}>
            <ProductPreview />
          </div>
          <div className="hero-caption">
            <span>
              <T text={"LESS GUESSWORK. MORE DIRECTION."} />
            </span>
            <span>
              <T text={"A thoughtful workspace for meaningful change."} />
            </span>
          </div>
        </section>
        <section className="possibility-strip" aria-label="Possible solutions">
          <span>
            <T text={"THE RIGHT ANSWER COULD BE"} />
          </span>
          <div>
            <Workflow size={19} />
            <T text={" Simple automation"} />
          </div>
          <div>
            <Layers3 size={19} />
            <T text={" Better processes"} />
          </div>
          <div>
            <FileText size={19} />
            <T text={" Existing software"} />
          </div>
          <div>
            <Sparkles size={19} />
            <T text={" Thoughtful AI"} />
          </div>
        </section>
        <section id="how-it-works" className="home-section">
          <div className="home-section-heading reveal">
            <div>
              <span className="eyebrow">
                <T text={"FROM UNCERTAINTY TO A PLAN"} />
              </span>
              <h2>
                <T text={"A little perspective."} />
                <br />
                <T text={"A meaningful shift."} />
              </h2>
            </div>
            <p>
              <T text={"You don’t need all the answers to begin."} />
              <br />
              <T text={"Just the right place to ask better questions."} />
            </p>
          </div>
          <div className="journey-grid">
            {steps.map(({ icon: Icon, title, copy, tag }, i) => (
              <article
                className="journey-card reveal"
                style={delay(i * 70)}
                key={title}
              >
                <span className="journey-icon">
                  <Icon size={23} strokeWidth={1.6} />
                </span>
                <small>{tag}</small>
                <h3>{title}</h3>
                <p>{copy}</p>
                <span className="journey-line" aria-hidden />
              </article>
            ))}
          </div>
        </section>
        <section id="approach" className="approach-section">
          <div className="approach-inner">
            <div className="approach-copy reveal">
              <span className="eyebrow">
                <T text={"A DIFFERENT STARTING POINT"} />
              </span>
              <h2>
                <T text={"The best solution"} />
                <br />
                <T text={"starts with"} />
                <br />
                <span>
                  <T text={"the real problem."} />
                </span>
              </h2>
              <p>
                <T
                  text={
                    "New technology isn’t always the answer. A clearer understanding of how your business works is a much better place to start."
                  }
                />
              </p>
              <Link href="/project/new" className="button button-primary">
                <T text={"Let’s find your opportunity "} />
                <ArrowUpRight size={17} />
              </Link>
            </div>
            <div className="decision-example reveal">
              <div className="decision-example-top">
                <span className="eyebrow">
                  <T text={"A SHIFT IN PERSPECTIVE"} />
                </span>
                <span>
                  <T text={"ILLUSTRATIVE EXAMPLE"} />
                </span>
              </div>
              <div className="initial-thought">
                <MessageSquare size={20} />
                <div>
                  <small>
                    <T text={"THE INITIAL ASK"} />
                  </small>
                  <p>
                    <T text={"“We need an AI tool to process invoices.”"} />
                  </p>
                </div>
              </div>
              <div className="example-bridge">
                <span />
                <ScanLine size={19} />
                <p>
                  <T text={"Look closer at the workflow"} />
                </p>
                <span />
              </div>
              <div className="closer-look">
                <small>
                  <T text={"WHAT THE EVIDENCE SHOWS"} />
                </small>
                <h3>
                  <T text={"The delay is in the handoff."} />
                </h3>
                <p>
                  <T
                    text={
                      "Fixed fields. Repeated steps. Two tools that could already talk to each other."
                    }
                  />
                </p>
                <div className="workflow-mini">
                  <span>
                    <T text={"Email"} />
                  </span>
                  <ArrowRight size={15} />
                  <span>
                    <T text={"Approval"} />
                  </span>
                  <ArrowRight size={15} />
                  <span>
                    <T text={"Accounting"} />
                  </span>
                </div>
              </div>
              <div className="example-outcome">
                <span>
                  <Check size={20} />
                </span>
                <div>
                  <small>
                    <T text={"THE RIGHT NEXT MOVE"} />
                  </small>
                  <strong>
                    <T text={"Automate the handoff. Keep it simple."} />
                  </strong>
                </div>
                <ArrowUpRight size={21} />
              </div>
            </div>
          </div>
        </section>
        <section id="capabilities" className="home-section">
          <div className="home-section-heading reveal">
            <div>
              <span className="eyebrow">
                <T text={"EVERYTHING CONNECTS"} />
              </span>
              <h2>
                <T text={"One workspace."} />
                <br />
                <T text={"The whole picture."} />
              </h2>
            </div>
            <p>
              <T text={"From the first question to the final blueprint,"} />
              <br />
              <T text={"keep the thinking and the evidence together."} />
            </p>
          </div>
          <div className="feature-bento">
            <article className="feature-main reveal">
              <span className="feature-icon">
                <FileText size={24} />
              </span>
              <h3>
                <T text={"Your evidence."} />
                <br />
                <T text={"At the heart of every decision."} />
              </h3>
              <p>
                <T
                  text={
                    "Bring your process notes, spreadsheets, and requirements. Turn scattered information into context you can actually use."
                  }
                />
              </p>
              <div className="evidence-files">
                <div>
                  <span className="file-type">
                    <T text={"PDF"} />
                  </span>
                  <div>
                    <strong>
                      <T text={"Current workflow.pdf"} />
                    </strong>
                    <small>
                      <T text={"Process notes · Evidence source"} />
                    </small>
                  </div>
                  <Check size={17} />
                </div>
                <div>
                  <span className="file-type green">
                    <T text={"CSV"} />
                  </span>
                  <div>
                    <strong>
                      <T text={"Operations overview.csv"} />
                    </strong>
                    <small>
                      <T text={"Team data · Evidence source"} />
                    </small>
                  </div>
                  <Check size={17} />
                </div>
                <span className="sample-label">
                  <T text={"Example documents"} />
                </span>
              </div>
            </article>
            <article className="feature-small reveal">
              <ShieldCheck size={27} />
              <h3>
                <T text={"A second opinion,"} />
                <br />
                <T text={"built right in."} />
              </h3>
              <p>
                <T
                  text={
                    "An independent red team reviews the plan for risks, unnecessary complexity, and blind spots."
                  }
                />
              </p>
              <div className="review-tags">
                <span>
                  <T text={"Feasibility"} />
                </span>
                <span>
                  <T text={"Risk"} />
                </span>
                <span>
                  <T text={"Business value"} />
                </span>
              </div>
            </article>
            <article className="feature-small feature-warm reveal">
              <FileCheck2 size={27} />
              <h3>
                <T text={"A plan that travels"} />
                <br />
                <T text={"with you."} />
              </h3>
              <p>
                <T
                  text={
                    "Take your blueprint into the next meeting. Share the roadmap and the thinking behind it."
                  }
                />
              </p>
              <div className="export-tags">
                <span>
                  <T text={"Markdown"} />
                </span>
                <span>
                  <T text={"Copy"} />
                </span>
                <span>
                  <T text={"Print / PDF "} />
                  <ArrowUpRight size={12} />
                </span>
              </div>
            </article>
          </div>
        </section>
        <section id="faq" className="home-section home-faq">
          <div className="reveal">
            <span className="eyebrow">
              <T text={"A LITTLE MORE CLARITY"} />
            </span>
            <h2>
              <T text={"Good questions."} />
              <br />
              <T text={"Straight answers."} />
            </h2>
            <p>
              <T text={"Here’s what to know before"} />
              <br />
              <T text={"your first shift."} />
            </p>
          </div>
          <div className="home-faq-list">
            {faqs.map(([q, a]) => (
              <details className="reveal" key={q}>
                <summary>
                  {q}
                  <span aria-hidden>+</span>
                </summary>
                <p>{a}</p>
              </details>
            ))}
          </div>
        </section>
        <section className="home-final">
          <div className="reveal">
            <span className="eyebrow">
              <T text={"YOUR NEXT CHAPTER STARTS HERE"} />
            </span>
            <h2>
              <T text={"Make room for"} />
              <br />
              <span>
                <T text={"your next big shift."} />
              </span>
            </h2>
            <p>
              <T text={"Bring the challenge. Leave with direction."} />
            </p>
            <Link
              href="/project/new"
              className="button button-primary button-lg"
            >
              <T text={"Start your first project "} />
              <ArrowUpRight size={18} />
            </Link>
          </div>
          <div className="final-orbit" aria-hidden />
        </section>
      </main>
      <footer className="home-footer">
        <div>
          <Logo />
          <p>
            <T text={"Problem first. Possibility next."} />
          </p>
        </div>
        <nav aria-label="Footer">
          <a href="#how-it-works">
            <T text={"How it works"} />
          </a>
          <a href="#capabilities">
            <T text={"The workspace"} />
          </a>
          <a href="#faq">
            <T text={"FAQ"} />
          </a>
          <Link href="/login">
            <T text={"Sign in "} />
            <ArrowUpRight size={14} />
          </Link>
        </nav>
        <div className="footer-bottom">
          <span>
            © {new Date().getFullYear()}
            <T text={" shift.AI"} />
          </span>
          <span>
            <T text={"A clearer way forward."} />
          </span>
        </div>
      </footer>
    </div>
  );
}
