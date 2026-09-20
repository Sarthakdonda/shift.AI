"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  ArrowUpRight,
  ChevronDown,
  FileCheck2,
  MessagesSquare,
  Menu,
  Search,
  ShieldCheck,
  X,
} from "lucide-react";
import { Logo } from "@/components/layout/logo";
import { T } from "@/components/locale";
import styles from "@/components/landing/render-home.module.css";
const links = [
  ["#how-it-works", "How it works"],
  ["#approach", "Our approach"],
  ["#faq", "Resources"],
] as const;
export function SiteHeader() {
  const [open, setOpen] = useState(false);
  const [product, setProduct] = useState(false);
  const ref = useRef<HTMLElement>(null);
  const toggleRef = useRef<HTMLButtonElement>(null);
  const productRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const close = (event: PointerEvent) => {
      if (!ref.current?.contains(event.target as Node)) {
        setOpen(false);
        setProduct(false);
      }
    };
    const key = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        if (open) toggleRef.current?.focus();
        else if (product) productRef.current?.focus();
        setOpen(false);
        setProduct(false);
      }
    };
    const resize = () => {
      if (window.innerWidth > 860) setOpen(false);
      else setProduct(false);
    };
    document.addEventListener("pointerdown", close);
    document.addEventListener("keydown", key);
    window.addEventListener("resize", resize);
    return () => {
      document.removeEventListener("pointerdown", close);
      document.removeEventListener("keydown", key);
      window.removeEventListener("resize", resize);
    };
  }, [open, product]);
  return (
    <header
      ref={ref}
      className={styles.header}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget))
          setProduct(false);
      }}
    >
      <div className={styles.navInner}>
        <Logo />
        <nav className={styles.navLinks} aria-label="Main navigation">
          <button
            ref={productRef}
            onClick={() => setProduct((value) => !value)}
            aria-expanded={product}
            aria-controls="product-navigation"
          >
            Platform
            <ChevronDown size={13} />
          </button>
          {links.map(([href, label]) => (
            <a key={href} href={href}>
              {label}
            </a>
          ))}
        </nav>
        <div className={styles.navActions}>
          <Link href="/login">
            <T text="Sign in" />
          </Link>
          <Link href="/signup" className={styles.navCta}>
            <T text="Get started" />
            <ArrowUpRight size={15} />
          </Link>
        </div>
        <button
          ref={toggleRef}
          className={styles.navToggle}
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
          aria-controls="mobile-site-navigation"
          onClick={() => setOpen((value) => !value)}
        >
          {open ? <X size={22} /> : <Menu size={22} />}
        </button>
      </div>
      {product && (
        <nav
          id="product-navigation"
          className={styles.megaMenu}
          aria-label="Platform"
        >
          <div>
            <span className={styles.eyebrow}>THE SHIFT.AI PLATFORM</span>
            <h2>
              One workspace.
              <br />A clearer way forward.
            </h2>
            <a
              href="#capabilities"
              onClick={() => setProduct(false)}
              className={styles.textLink}
            >
              Explore the platform
              <ArrowUpRight size={16} />
            </a>
          </div>
          <div>
            {[
              [
                MessagesSquare,
                "Discovery",
                "Start with your business challenge",
                "#how-it-works",
              ],
              [
                Search,
                "Analysis",
                "Connect context and evidence",
                "#capabilities",
              ],
              [
                ShieldCheck,
                "Red-team review",
                "Challenge the recommendation",
                "#approach",
              ],
              [
                FileCheck2,
                "Implementation blueprint",
                "Take a practical plan with you",
                "#deliverables",
              ],
            ].map(([Icon, title, copy, href]) => {
              const Symbol = Icon as typeof Search;
              return (
                <a
                  key={String(title)}
                  href={String(href)}
                  onClick={() => setProduct(false)}
                >
                  <Symbol size={21} />
                  <span>
                    <strong>{String(title)}</strong>
                    <small>{String(copy)}</small>
                  </span>
                  <ArrowUpRight size={15} />
                </a>
              );
            })}
          </div>
        </nav>
      )}
      {open && (
        <nav
          id="mobile-site-navigation"
          className={styles.mobileNav}
          aria-label="Mobile navigation"
        >
          {[["#capabilities", "Platform"], ...links].map(([href, label]) => (
            <a key={href} href={href} onClick={() => setOpen(false)}>
              {label}
              <ArrowUpRight size={17} />
            </a>
          ))}
          <Link href="/login" onClick={() => setOpen(false)}>
            Sign in
          </Link>
          <Link
            className={styles.primaryButton}
            href="/signup"
            onClick={() => setOpen(false)}
          >
            Get started
            <ArrowUpRight size={16} />
          </Link>
        </nav>
      )}
    </header>
  );
}
