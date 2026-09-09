"use client";
import { useEffect, useState } from "react";

const reducedMotion = () =>
  typeof window !== "undefined" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/**
 * Reveals every `.reveal` element once it scrolls into view and drives the
 * reading-progress bar. One observer for the whole page keeps the markup
 * server-rendered and the runtime cost near zero.
 */
export function ScrollFX({ progress = false }: { progress?: boolean }) {
  const [value, setValue] = useState(0);

  useEffect(() => {
    const nodes = Array.from(document.querySelectorAll<HTMLElement>(".reveal"));
    if (reducedMotion()) {
      nodes.forEach((node) => node.classList.add("is-visible"));
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        });
      },
      { rootMargin: "0px 0px -12% 0px", threshold: 0.12 },
    );
    nodes.forEach((node) => observer.observe(node));

    // Elements added after hydration (route transitions, lazy sections).
    const mutations = new MutationObserver(() => {
      document
        .querySelectorAll<HTMLElement>(".reveal:not(.is-visible)")
        .forEach((node) => observer.observe(node));
    });
    mutations.observe(document.body, { childList: true, subtree: true });

    return () => {
      observer.disconnect();
      mutations.disconnect();
    };
  }, []);

  useEffect(() => {
    if (!progress) return;
    let frame = 0;
    const update = () => {
      frame = 0;
      const max =
        document.documentElement.scrollHeight - window.innerHeight || 1;
      setValue(Math.min(100, Math.max(0, (window.scrollY / max) * 100)));
    };
    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (frame) cancelAnimationFrame(frame);
    };
  }, [progress]);

  if (!progress) return null;
  return (
    <div className="scroll-progress" aria-hidden>
      <span style={{ "--progress": `${value}%` } as React.CSSProperties} />
    </div>
  );
}
