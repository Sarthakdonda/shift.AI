export type ReviewFinding = {
  id: string;
  category: string;
  severity: string;
  issue: string;
  reason: string;
  mitigation: string;
  requires_revision: boolean;
  action: "revise" | "reconsider_solution" | "ask_user" | "retain_risk";
  affected_sections: string[];
  decision: string;
  validation: string;
  question: string;
  status: "open" | "fixed" | "mitigated" | "needs_input" | "accepted_risk";
  verification: string;
  verification_quote: string;
  verified_section: string;
  residual_risk: string;
  acceptance_reason?: string;
  user_response?: string;
};
export type DesignChange = {
  cycle: number;
  finding_ids?: string[];
  decisions?: string[];
  changed_sections: string[];
  diffs?: { section: string; before: unknown; after: unknown }[];
};
export type ReviewData = {
  review_ledger?: ReviewFinding[];
  review_gate?: "passed" | "conditional" | "blocked";
  design_changes?: DesignChange[];
};
