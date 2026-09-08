import Link from "next/link";
import {
  ArrowRight,
  ArrowUpRight,
  Check,
  MessageSquare,
  Search,
  Workflow,
  ShieldCheck,
  FileCheck2,
  MoveDown,
  CheckCheck,
} from "lucide-react";
import { Logo } from "@/components/layout/shell";
export default function Landing() {
  return (
    <div className="landing">
      <header className="landing-nav">
        <Logo />
        <nav>
          <a href="#how-it-works">How it works</a>
          <a href="#why-shift">Why shift.AI</a>
          <Link href="/login">Sign in</Link>
          <Link href="/dashboard" className="button button-dark button-sm">
            Open workspace <ArrowUpRight size={16} />
          </Link>
        </nav>
      </header>
      <main>
        <section className="hero">
          <div className="hero-copy">
            <span className="eyebrow">
              <span className="tiny-orange" /> BUSINESS CLARITY, BY DESIGN
            </span>
            <h1>
              Better questions.
              <br />
              Smarter decisions.
              <br />
              <span>Meaningful shift.</span>
            </h1>
            <p>
              Not every business problem needs AI.
              <br />
              Find out what yours actually needs — and get a clear blueprint to
              move forward.
            </p>
            <div className="hero-actions">
              <Link href="/project/new" className="button button-primary">
                Find your next shift <ArrowRight size={18} />
              </Link>
              <a href="#how-it-works" className="button button-secondary">
                Explore the process
              </a>
            </div>
            <div className="hero-proof">
              <span>
                <Check size={15} /> Evidence-led decisions
              </span>
              <span>
                <Check size={15} /> Built-in risk review
              </span>
            </div>
          </div>
          <div
            className="hero-visual"
            aria-label="Illustrative example of the shift.AI decision process"
          >
            <div className="visual-caption">
              <span>FROM AMBIGUITY TO ACTION</span>
              <span>ILLUSTRATIVE EXAMPLE</span>
            </div>
            <div className="example-question">
              <span className="mini-icon">
                <MessageSquare size={18} />
              </span>
              <div>
                <small>THE INITIAL ASK</small>
                <p>“We need AI to speed up our operations.”</p>
              </div>
            </div>
            <div className="connector">
              <MoveDown size={22} />
              <span>Understand the real problem</span>
            </div>
            <div className="diagnosis-card">
              <div className="row-between">
                <span className="eyebrow">THE DIAGNOSIS</span>
                <Search size={19} />
              </div>
              <h3>
                A process gap.
                <br />
                Not an intelligence gap.
              </h3>
              <p>
                Manual handoffs and disconnected tools create the bottleneck.
              </p>
              <div className="evidence-line">
                <CheckCheck size={15} /> Connect the evidence. Challenge the
                assumption.
              </div>
            </div>
            <div className="connector">
              <MoveDown size={22} />
              <span>Choose what actually works</span>
            </div>
            <div className="result-card">
              <span className="result-check">
                <Check size={21} />
              </span>
              <div>
                <small>THE RIGHT NEXT STEP</small>
                <strong>Simple automation. Real impact.</strong>
              </div>
              <ArrowUpRight size={23} />
            </div>
            <div className="visual-footer">
              <ShieldCheck size={15} /> Every recommendation gets a second look.
            </div>
          </div>
        </section>
        <section className="principles-strip">
          <span>START WITH THE PROBLEM</span>
          <span>FOLLOW THE EVIDENCE</span>
          <span>CHALLENGE THE SOLUTION</span>
          <span>MAKE THE NEXT MOVE</span>
        </section>
        <section id="how-it-works" className="landing-section">
          <div className="section-heading">
            <div>
              <span className="eyebrow">A THOUGHTFUL PROCESS</span>
              <h2>
                From “what if” to
                <br />
                “here’s how.”
              </h2>
            </div>
            <p>
              A structured journey that turns an open-ended challenge into a
              practical, evidence-backed plan.
            </p>
          </div>
          <div className="process-grid">
            {[
              [
                MessageSquare,
                "01",
                "Discover",
                "A focused conversation to understand your goals, workflow, and constraints.",
              ],
              [
                Search,
                "02",
                "Diagnose",
                "Connect your documents and context to uncover the actual root cause.",
              ],
              [
                ShieldCheck,
                "03",
                "Challenge",
                "Explore the right approach. Then stress-test its assumptions and risks.",
              ],
              [
                FileCheck2,
                "04",
                "Move forward",
                "Get a complete blueprint with architecture, business value, and next steps.",
              ],
            ].map(([Icon, n, title, copy]) => {
              const I = Icon as typeof Workflow;
              return (
                <article key={String(n)}>
                  <div className="row-between">
                    <I size={24} />
                    <span>{String(n)}</span>
                  </div>
                  <h3>{String(title)}</h3>
                  <p>{String(copy)}</p>
                </article>
              );
            })}
          </div>
        </section>
        <section id="why-shift" className="why-section">
          <div>
            <span className="eyebrow">TECHNOLOGY WITH INTENTION</span>
            <h2>
              The best solution
              <br />
              might be <span>less AI.</span>
            </h2>
            <p>
              A better process. An existing tool. A simple integration. Or an
              intelligent hybrid. shift.AI helps you choose with a reason, not a
              trend.
            </p>
            <Link href="/project/new" className="button button-primary">
              Start with your problem <ArrowRight size={17} />
            </Link>
          </div>
          <div className="why-list">
            {[
              [
                "Your context, connected",
                "Conversations and documents come together in one persistent project.",
              ],
              [
                "An independent second opinion",
                "A Red Team reviews complexity, privacy, cost, and failure points.",
              ],
              [
                "A plan you can act on",
                "Clear responsibilities, human checkpoints, and measurable next steps.",
              ],
            ].map(([t, c]) => (
              <div key={t}>
                <Check size={20} />
                <div>
                  <h3>{t}</h3>
                  <p>{c}</p>
                </div>
              </div>
            ))}
          </div>
        </section>
      </main>
      <footer className="landing-footer">
        <Logo />
        <p>Clarity before complexity.</p>
        <Link href="/dashboard">
          Enter your workspace <ArrowUpRight size={16} />
        </Link>
      </footer>
    </div>
  );
}
