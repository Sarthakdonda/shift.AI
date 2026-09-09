"use client";

import { T } from "@/components/locale";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowUpRight, Menu, X } from "lucide-react";
import { Logo } from "@/components/layout/logo";

const links = [
  ["#how-it-works", "How it works"],
  ["#approach", "Our approach"],
  ["#capabilities", "The workspace"],
  ["#faq", "FAQ"],
] as const;

export function SiteHeader() {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 10);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    const onResize = () => {
      if (window.innerWidth > 860) setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("resize", onResize);
    };
  }, []);

  return (
    <header className="landing-nav" data-scrolled={scrolled}>
      <div className="nav-inner">
        <Logo />
        <nav className="nav-links" aria-label="Main navigation">
          {links.map(([href, label]) => (
            <a key={href} href={href}>
              {label}
            </a>
          ))}
        </nav>
        <div className="nav-actions">
          <Link href="/login" className="nav-signin">
            <T text={"Sign in"} />
          </Link>
          <Link href="/dashboard" className="button button-dark button-sm">
            <T text={"Open workspace "} />
            <ArrowUpRight size={15} />
          </Link>
        </div>
        <button
          className="nav-toggle icon-button"
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
          aria-controls="mobile-site-navigation"
          onClick={() => setOpen(!open)}
        >
          {open ? <X size={19} /> : <Menu size={19} />}
        </button>
      </div>
      {open && (
        <nav
          className="nav-drawer"
          id="mobile-site-navigation"
          aria-label="Mobile navigation"
        >
          {links.map(([href, label]) => (
            <a key={href} href={href} onClick={() => setOpen(false)}>
              {label}
            </a>
          ))}
          <Link href="/login" onClick={() => setOpen(false)}>
            <T text={"Sign in"} />
          </Link>
          <Link
            href="/dashboard"
            className="button button-dark"
            onClick={() => setOpen(false)}
          >
            <T text={"Open workspace "} />
            <ArrowUpRight size={15} />
          </Link>
        </nav>
      )}
    </header>
  );
}
