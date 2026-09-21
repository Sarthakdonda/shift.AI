"use client";

import { useState, type InputHTMLAttributes, type ReactNode } from "react";
import { Eye, EyeOff, TriangleAlert } from "lucide-react";

export function Field({
  id,
  label,
  error,
  hint,
  action,
  icon,
  type = "text",
  ...props
}: InputHTMLAttributes<HTMLInputElement> & {
  id: string;
  label: string;
  error?: string;
  hint?: string;
  action?: ReactNode;
  icon?: ReactNode;
}) {
  const [revealed, setRevealed] = useState(false);
  const password = type === "password";
  const describedBy =
    [error && `${id}-error`, hint && `${id}-hint`].filter(Boolean).join(" ") ||
    undefined;
  return (
    <div className="field">
      <div className="row-between">
        <label htmlFor={id}>{label}</label>
        {action}
      </div>
      <div className="field-shell" data-invalid={error ? "true" : undefined}>
        {icon}
        <input
          id={id}
          type={password && revealed ? "text" : type}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          {...props}
        />
        {password && (
          <button
            type="button"
            className="icon-btn"
            style={{ width: 32, height: 32, marginRight: -6 }}
            aria-label={revealed ? "Hide password" : "Show password"}
            onClick={() => setRevealed(!revealed)}
          >
            {revealed ? <EyeOff size={17} /> : <Eye size={17} />}
          </button>
        )}
      </div>
      {hint && !error && (
        <p className="field-note" id={`${id}-hint`}>
          {hint}
        </p>
      )}
      {error && (
        <p className="field-error" id={`${id}-error`}>
          <TriangleAlert size={12} aria-hidden="true" />
          {error}
        </p>
      )}
    </div>
  );
}
