"use client";

import { useState, type InputHTMLAttributes, type ReactNode } from "react";
import { Eye, EyeOff } from "lucide-react";
import { T } from "@/components/locale";
import styles from "./access.module.css";

export function Field({
  label,
  error,
  hint,
  action,
  ...input
}: InputHTMLAttributes<HTMLInputElement> & {
  id: string;
  label: string;
  error?: string;
  hint?: string;
  action?: ReactNode;
}) {
  const [visible, setVisible] = useState(false);
  const password = input.type === "password";
  return (
    <div className={styles.field}>
      <div className={styles.fieldTop}>
        <label htmlFor={input.id}>
          <T text={label} />
        </label>
        {action}
      </div>
      <div className={`${styles.inputWrap} ${error ? styles.invalid : ""}`}>
        <input
          {...input}
          type={password && visible ? "text" : input.type}
          aria-invalid={!!error}
          aria-describedby={
            [hint && `${input.id}-hint`, error && `${input.id}-error`]
              .filter(Boolean)
              .join(" ") || undefined
          }
        />
        {password && (
          <button
            type="button"
            className={styles.reveal}
            disabled={input.disabled}
            aria-label={`${visible ? "Hide" : "Show"} ${label.toLowerCase()}`}
            aria-pressed={visible}
            onClick={() => setVisible(!visible)}
          >
            {visible ? <EyeOff size={18} /> : <Eye size={18} />}
          </button>
        )}
      </div>
      {hint && (
        <p className={styles.hint} id={`${input.id}-hint`}>
          <T text={hint} />
        </p>
      )}
      {error && (
        <p className={styles.fieldError} id={`${input.id}-error`} role="alert">
          <T text={error} />
        </p>
      )}
    </div>
  );
}
