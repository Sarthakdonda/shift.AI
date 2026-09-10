"use client";

import Link from "next/link";
import { Check } from "lucide-react";
import { T } from "@/components/locale";
import { Popover } from "@/components/ui/popover";

export const stages = [
  ["Discovery", ""],
  ["Diagnosis", "/analysis"],
  ["Solution", "/solution"],
  ["Red Team", "/red-team"],
  ["Blueprint", "/blueprint"],
] as const;

/** Same status mapping the workspace has always used, presented compactly. */
export const stageIndex = (status: string) =>
  status === "BLUEPRINT_READY"
    ? 4
    : status === "BUSINESS_VALUE" || status === "RED_TEAM_REVIEW"
      ? 3
      : status === "SOLUTION_GENERATION"
        ? 2
        : ["SYSTEM_ANALYSIS", "AI_NECESSITY"].includes(status)
          ? 1
          : 0;

export function DiscoveryProgress({
  status,
  projectId,
}: {
  status: string;
  projectId: string;
}) {
  const reached = stageIndex(status);
  return (
    <Popover
      label="Workflow stages"
      align="center"
      side="bottom"
      width={252}
      className="dx-pop-menu"
      trigger={(props) => (
        <button
          {...props}
          type="button"
          className="dx-header-chip dx-stage-chip"
          aria-label={`Stage ${reached + 1} of 5: ${stages[reached][0]}`}
        >
          <span className="dx-stage-name">{stages[reached][0]}</span>
          <span className="dx-stage-dots" aria-hidden>
            {stages.map(([name], index) => (
              <i key={name} className={index <= reached ? "is-on" : ""} />
            ))}
          </span>
          <span className="dx-stage-count" aria-hidden>
            {reached + 1}/5
          </span>
        </button>
      )}
    >
      {(close) => (
        <>
          <p className="dx-pop-label">
            <T text={"Workflow"} />
          </p>
          {stages.map(([name, suffix], index) => (
            <Link
              key={name}
              href={`/project/${projectId}${suffix}`}
              onClick={() => close()}
              className={`dx-stage-row ${index === reached ? "is-current" : ""} ${index < reached ? "is-done" : ""}`}
              aria-current={index === reached ? "step" : undefined}
            >
              <span className="dx-stage-index" aria-hidden>
                {index < reached ? <Check size={12} /> : index + 1}
              </span>
              <span>
                <T text={name} />
              </span>
            </Link>
          ))}
          <p className="dx-pop-hint">
            <T text={"Each stage unlocks as the evidence supports it."} />
          </p>
        </>
      )}
    </Popover>
  );
}
