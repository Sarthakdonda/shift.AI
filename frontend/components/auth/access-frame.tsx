"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { LanguagePicker, T } from "@/components/locale";
import { Logo } from "@/components/layout/logo";
import styles from "./access.module.css";

const journey = [
  "Start with a question",
  "Find your clarity",
  "Make your next move",
];

/** Ascending isometric steps: the blocks rise in sequence, then keep a slow, quiet motion. */
function Artwork() {
  return (
    <div className={styles.art} aria-hidden="true">
      <svg viewBox="0 0 560 300" fill="none">
        <defs>
          <linearGradient id="access-sheen" x1="0" x2="1" y1="0" y2="0">
            <stop offset="0%" stopColor="#ffffff" stopOpacity="0" />
            <stop offset="48%" stopColor="#ffffff" stopOpacity="0.5" />
            <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
          </linearGradient>
          <clipPath id="access-crest">
            <path d="M298 98L400 39L502 98L400 157Z" />
          </clipPath>
        </defs>
        <g className={styles.guides} stroke="#e4ddd3">
          <path d="M35 245L280 104L525 245" />
          <path d="M92 278L337 137" />
          <path d="M150 310L395 169" />
        </g>
        <g className={`${styles.step} ${styles.stepOne}`}>
          <path d="M70 202L172 143L274 202L172 261Z" fill="#eee8df" />
          <path d="M70 202L172 261V296L70 237Z" fill="#d9cfc1" />
          <path d="M172 261L274 202V237L172 296Z" fill="#bcb1a2" />
        </g>
        <g className={`${styles.step} ${styles.stepTwo}`}>
          <path d="M184 159L286 100L388 159L286 218Z" fill="#ffc78f" />
          <path d="M184 159L286 218V267L184 208Z" fill="#f9a862" />
          <path d="M286 218L388 159V208L286 267Z" fill="#e08842" />
        </g>
        <g className={`${styles.step} ${styles.stepThree}`}>
          <path d="M298 98L400 39L502 98L400 157Z" fill="#ff912f" />
          <path d="M298 98L400 157V235L298 176Z" fill="#ff7a00" />
          <path d="M400 157L502 98V176L400 235Z" fill="#cf5f00" />
          <g clipPath="url(#access-crest)">
            <g className={styles.sheen}>
              <path
                d="M300 18L354 18L436 178L382 178Z"
                fill="url(#access-sheen)"
              />
            </g>
          </g>
          <path
            className={styles.pulse}
            d="M350 98L400 69L450 98L400 127Z"
            stroke="#ffffff"
            strokeOpacity="0.8"
            strokeWidth="1.5"
          />
          <path
            className={styles.arrow}
            d="M374 97L400 82L426 97M400 82V112"
            stroke="#ffffff"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </g>
        <g fill="#e08a3e">
          <circle className={styles.mote} cx="468" cy="44" r="3" />
          <circle
            className={`${styles.mote} ${styles.moteTwo}`}
            cx="332"
            cy="34"
            r="2.4"
          />
          <circle
            className={`${styles.mote} ${styles.moteThree}`}
            cx="508"
            cy="62"
            r="2"
          />
        </g>
        <g
          className={styles.ticks}
          stroke="#d6a374"
          strokeWidth="2"
          strokeLinecap="round"
        >
          <path d="M400 15V1" />
          <path d="M530 94H544" />
          <path d="M498 28L508 18" />
        </g>
      </svg>
    </div>
  );
}

export function AccessFrame({
  title,
  description,
  switchPrompt,
  switchLabel,
  switchHref,
  eyebrow = "YOUR SPACE TO THINK AHEAD",
  children,
}: {
  title: string;
  description: string;
  switchPrompt: string;
  switchLabel: string;
  switchHref: string;
  eyebrow?: string;
  children: ReactNode;
}) {
  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div className={styles.navigation}>
          <Logo />
          <span className={styles.headerRule} aria-hidden="true" />
          <Link href="/" className={styles.back}>
            <ArrowLeft size={16} />
            <T text="Back to home" />
          </Link>
        </div>
        <LanguagePicker />
      </header>
      <main className={styles.layout} id="main">
        <aside className={styles.editorial} aria-label="About shift.AI">
          <div className={styles.editorialCopy}>
            <span className={styles.eyebrow}>
              <span aria-hidden="true" />
              <T text="A NEW WAY FORWARD" />
            </span>
            <h2>
              <T text="Make room for" />
              <br />
              <T text="your next" />{" "}
              <em>
                <T text="big idea." />
              </em>
            </h2>
            <p>
              <T text="A place to ask better questions, see what matters, and decide what comes next." />
            </p>
          </div>
          <Artwork />
          <div className={styles.journey}>
            {journey.map((label, index) => (
              <div key={label}>
                <span>0{index + 1}</span>
                <p>
                  <T text={label} />
                </p>
              </div>
            ))}
          </div>
          <div className={styles.editorialFoot}>
            <span>
              <T text="Problem first. Possibility next." />
            </span>
            <ArrowRight size={17} aria-hidden="true" />
          </div>
        </aside>
        <section className={styles.formSide} aria-labelledby="account-title">
          <div className={styles.formContent}>
            <div className={styles.formTop}>
              <span className={styles.formEyebrow}>
                <T text={eyebrow} />
              </span>
              <p className={styles.switchAccount}>
                <T text={switchPrompt} />{" "}
                <Link href={switchHref}>
                  <T text={switchLabel} />
                  <ArrowRight size={13} aria-hidden="true" />
                </Link>
              </p>
            </div>
            <h1 id="account-title">
              <T text={title} />
            </h1>
            <p className={styles.description}>
              <T text={description} />
            </p>
            {children}
          </div>
        </section>
      </main>
      <footer className={styles.footer}>
        <span>
          © {new Date().getFullYear()}
          <T text={" shift.AI"} />
        </span>
        <span>
          <T text="Clarity before complexity." />
        </span>
      </footer>
    </div>
  );
}

export { styles as accessStyles };
