"use client";

import { useEffect, useRef, useState } from "react";
import { Check, ChevronRight, ChevronLeft, Sparkles, Gauge } from "lucide-react";
import { T } from "@/components/locale";
import type { EffortOption, ModelOption } from "@/lib/types";

/** Model and reasoning-effort selection for the conversation.
 *  The choice is saved on the project, so it also applies to analysis and deliverables. */
export function ModelPicker({
  models,
  efforts,
  model,
  effort,
  disabled,
  onChange,
}: {
  models: ModelOption[];
  efforts: EffortOption[];
  model: string;
  effort: string;
  disabled?: boolean;
  onChange: (next: { model: string; effort: string }) => void;
}) {
  const [open, setOpen] = useState(false);
  const [view, setView] = useState<"models" | "effort">("models");
  const wrapper = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointer = (event: MouseEvent) => {
      if (!wrapper.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setOpen(false);
      trigger.current?.focus();
    };
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  useEffect(() => {
    if (!open) setView("models");
  }, [open]);

  const current = models.find((m) => m.id === model);
  const currentEffort = efforts.find((e) => e.id === effort);
  const effortAvailable = current ? current.supports_effort : true;

  return (
    <div className="model-picker" ref={wrapper}>
      <button
        type="button"
        ref={trigger}
        className="model-trigger"
        disabled={disabled}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        <Sparkles size={15} />
        <span className="model-trigger-name">
          {current?.label || model || "Model"}
        </span>
        {effortAvailable && currentEffort && (
          <span className="model-trigger-effort">{currentEffort.label}</span>
        )}
        <ChevronRight size={14} className="model-trigger-caret" />
      </button>
      {open && (
        <div className="model-menu" role="menu" aria-label="Model and effort">
          {view === "models" ? (
            <>
              <p className="model-menu-label">
                <T text={"Model"} />
              </p>
              <div className="model-menu-scroll">
                {models.map((option) => (
                  <button
                    type="button"
                    key={option.id}
                    role="menuitemradio"
                    aria-checked={option.id === model}
                    className={`model-option ${option.id === model ? "selected" : ""}`}
                    onClick={() => {
                      onChange({ model: option.id, effort });
                      setOpen(false);
                    }}
                  >
                    <span>
                      <strong>{option.label}</strong>
                      <small>{option.description}</small>
                    </span>
                    {option.id === model && <Check size={16} />}
                  </button>
                ))}
              </div>
              <button
                type="button"
                className="model-option model-effort-row"
                onClick={() => setView("effort")}
                disabled={!effortAvailable}
                aria-haspopup="menu"
              >
                <span>
                  <strong>
                    <Gauge size={14} />
                    <T text={" Effort"} />
                  </strong>
                  {!effortAvailable && (
                    <small>
                      <T text={"Not adjustable for this model"} />
                    </small>
                  )}
                </span>
                <span className="model-effort-value">
                  {effortAvailable ? currentEffort?.label : "—"}
                  <ChevronRight size={15} />
                </span>
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                className="model-menu-back"
                onClick={() => setView("models")}
              >
                <ChevronLeft size={15} />
                <T text={" Effort"} />
              </button>
              <div className="model-menu-scroll">
                {efforts.map((option) => (
                  <button
                    type="button"
                    key={option.id}
                    role="menuitemradio"
                    aria-checked={option.id === effort}
                    className={`model-option ${option.id === effort ? "selected" : ""}`}
                    onClick={() => {
                      onChange({ model, effort: option.id });
                      setOpen(false);
                    }}
                  >
                    <span>
                      <strong>{option.label}</strong>
                      <small>{option.description}</small>
                    </span>
                    {option.id === effort && <Check size={16} />}
                  </button>
                ))}
              </div>
              <p className="model-menu-hint">
                <T
                  text={
                    "Less effort answers faster. More effort reasons longer."
                  }
                />
              </p>
            </>
          )}
        </div>
      )}
    </div>
  );
}
