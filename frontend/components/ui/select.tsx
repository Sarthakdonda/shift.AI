"use client";

import * as SelectPrimitive from "@radix-ui/react-select";
import { Check, ChevronDown, ChevronUp } from "lucide-react";
import type { ComponentPropsWithoutRef } from "react";
import styles from "./select.module.css";

type SelectOption = { value: string; label: string; disabled?: boolean };
type Props = Pick<
  ComponentPropsWithoutRef<typeof SelectPrimitive.Trigger>,
  "id" | "className" | "aria-label" | "aria-labelledby" | "aria-describedby"
> & {
  value: string;
  onValueChange: (value: string) => void;
  options: SelectOption[];
  disabled?: boolean;
  required?: boolean;
  compact?: boolean;
};

// Empty selections remain empty on Root so native required validation works.
// Items need nonempty IDs; prefixing also avoids collisions with user values.
const itemValue = (value: string) => `option:${value}`;

export function Select({
  value,
  onValueChange,
  options,
  disabled,
  required,
  compact,
  className = "",
  ...triggerProps
}: Props) {
  const empty = options.find((option) => option.value === "");
  return (
    <SelectPrimitive.Root
      value={value === "" ? "" : itemValue(value)}
      onValueChange={(next) => onValueChange(next.slice("option:".length))}
      disabled={disabled}
      required={required}
    >
      <SelectPrimitive.Trigger
        {...triggerProps}
        className={`${styles.trigger} ${compact ? styles.compact : ""} ${className}`}
      >
        <span className={styles.value}>
          <SelectPrimitive.Value
            placeholder={empty?.label ?? "Choose an option"}
          />
        </span>
        <SelectPrimitive.Icon asChild>
          <ChevronDown
            size={16}
            className={styles.chevron}
            aria-hidden="true"
          />
        </SelectPrimitive.Icon>
      </SelectPrimitive.Trigger>
      <SelectPrimitive.Portal>
        <SelectPrimitive.Content
          className={styles.menu}
          position="popper"
          sideOffset={8}
          collisionPadding={12}
          align="start"
          aria-label={triggerProps["aria-label"]}
          // Keep a containing settings popover open while using this portal.
          onPointerDown={(event) => event.stopPropagation()}
          onKeyDown={(event) => event.stopPropagation()}
          onEscapeKeyDown={(event) => event.stopPropagation()}
        >
          <SelectPrimitive.ScrollUpButton className={styles.scroll}>
            <ChevronUp size={15} aria-hidden="true" />
          </SelectPrimitive.ScrollUpButton>
          <SelectPrimitive.Viewport className={styles.viewport}>
            {options.map((option) => (
              <SelectPrimitive.Item
                key={option.value}
                value={itemValue(option.value)}
                disabled={option.disabled || (required && option.value === "")}
                className={styles.option}
                textValue={option.label}
              >
                <SelectPrimitive.ItemText>
                  {option.label}
                </SelectPrimitive.ItemText>
                <SelectPrimitive.ItemIndicator className={styles.check}>
                  <Check size={15} aria-hidden="true" />
                </SelectPrimitive.ItemIndicator>
              </SelectPrimitive.Item>
            ))}
          </SelectPrimitive.Viewport>
          <SelectPrimitive.ScrollDownButton className={styles.scroll}>
            <ChevronDown size={15} aria-hidden="true" />
          </SelectPrimitive.ScrollDownButton>
        </SelectPrimitive.Content>
      </SelectPrimitive.Portal>
    </SelectPrimitive.Root>
  );
}
