"use client";

import { Check, ChevronDown, Cpu, Gauge, Zap } from "lucide-react";
import { T } from "@/components/locale";
import { Popover } from "@/components/ui/popover";
import type { EffortOption, ModelOption } from "@/lib/types";

/**
 * Model selection for the composer.
 *
 * Options come from `GET /models` (what the configured keys can actually use)
 * and the choice is saved on the project by the page, exactly as before.
 */
export function ModelSelector({
  models,
  model,
  disabled,
  onSelect,
}: {
  models: ModelOption[];
  model: string;
  disabled?: boolean;
  onSelect: (id: string) => void;
}) {
  const current = models.find((option) => option.id === model);
  return (
    <Popover
      label="Model"
      align="start"
      width={300}
      className="dx-pop-menu"
      trigger={(props) => (
        <button
          {...props}
          type="button"
          disabled={disabled}
          className="dx-chip"
          aria-label={`Model: ${current?.label || model || "default"}`}
        >
          <Cpu size={14} />
          <span className="dx-chip-text">
            {current?.label || model || "Model"}
          </span>
          <ChevronDown size={13} className="dx-chip-caret" />
        </button>
      )}
    >
      {(close) => (
        <>
          <p className="dx-pop-label">
            <T text={"Model"} />
          </p>
          <div className="dx-pop-scroll">
            {models.map((option) => (
              <button
                key={option.id}
                type="button"
                role="menuitemradio"
                aria-checked={option.id === model}
                className={`dx-pop-option ${option.id === model ? "is-selected" : ""}`}
                onClick={() => {
                  onSelect(option.id);
                  close();
                }}
              >
                <span>
                  <strong>{option.label}</strong>
                  {option.description && <small>{option.description}</small>}
                </span>
                {option.id === model && <Check size={15} />}
              </button>
            ))}
          </div>
          <p className="dx-pop-hint">
            <T
              text={
                "Your choice is saved on this project and applies to analysis too."
              }
            />
          </p>
        </>
      )}
    </Popover>
  );
}

const icons: Record<string, React.ReactNode> = {
  minimal: <Zap size={14} />,
  low: <Zap size={14} />,
  medium: <Gauge size={14} />,
  high: <Gauge size={14} />,
};

/**
 * Reasoning effort — a real backend capability (`effort` on the project), so
 * the control is wired to it rather than being decorative.
 */
export function ResponseModeSelector({
  efforts,
  effort,
  supported,
  disabled,
  onSelect,
}: {
  efforts: EffortOption[];
  effort: string;
  supported: boolean;
  disabled?: boolean;
  onSelect: (id: string) => void;
}) {
  const current = efforts.find((option) => option.id === effort);
  if (!supported)
    return (
      <span
        className="dx-chip dx-chip-static"
        title="Response mode is not adjustable for this model."
      >
        <Gauge size={14} />
        <span className="dx-chip-text">
          <T text={"Standard"} />
        </span>
      </span>
    );
  return (
    <Popover
      label="Response mode"
      align="start"
      width={286}
      className="dx-pop-menu"
      trigger={(props) => (
        <button
          {...props}
          type="button"
          disabled={disabled}
          className="dx-chip"
          aria-label={`Response mode: ${current?.label || effort}`}
        >
          {icons[effort] || <Gauge size={14} />}
          <span className="dx-chip-text">{current?.label || effort}</span>
          <ChevronDown size={13} className="dx-chip-caret" />
        </button>
      )}
    >
      {(close) => (
        <>
          <p className="dx-pop-label">
            <T text={"Response mode"} />
          </p>
          <div className="dx-pop-scroll">
            {efforts.map((option) => (
              <button
                key={option.id}
                type="button"
                role="menuitemradio"
                aria-checked={option.id === effort}
                className={`dx-pop-option ${option.id === effort ? "is-selected" : ""}`}
                onClick={() => {
                  onSelect(option.id);
                  close();
                }}
              >
                <span>
                  <strong>
                    {icons[option.id] || <Gauge size={14} />}
                    {option.label}
                  </strong>
                  <small>{option.description}</small>
                </span>
                {option.id === effort && <Check size={15} />}
              </button>
            ))}
          </div>
          <p className="dx-pop-hint">
            <T
              text={
                "Less effort answers faster. More effort reasons for longer."
              }
            />
          </p>
        </>
      )}
    </Popover>
  );
}
