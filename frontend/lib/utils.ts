import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
/** Stagger helper for scroll-reveal animations: style={delay(index * 70)}. */
export function delay(ms: number): React.CSSProperties {
  return { "--reveal-delay": `${ms}ms` } as React.CSSProperties;
}
