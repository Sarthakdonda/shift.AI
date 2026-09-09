export type Table = { title: string; columns: string[]; rows: string[][] };
export type Diagram = {
  title: string;
  kind: string;
  nodes: { id: string; label: string; lane: string; kind: string }[];
  edges: { source: string; target: string; label: string }[];
};
export type Assessment = {
  dimension: string;
  rating: string;
  reason: string;
  evidence: string[];
};
export type Deliverable = {
  assessments?: Assessment[];
  title: string;
  summary: string;
  sections: {
    title: string;
    narrative: string;
    items: string[];
    tables: Table[];
  }[];
  diagrams: Diagram[];
  screens: {
    name: string;
    persona: string;
    purpose: string;
    controls: { label: string; kind: string; detail: string }[];
  }[];
  code_assets: { filename: string; language: string; content: string }[];
  assumptions: string[];
  validation_steps: string[];
};
export type Artifact = {
  id: string;
  kind: string;
  version: number;
  content: Deliverable;
  language: string;
  author: string;
  note: string;
  created_at: string;
  ai_reviews: {
    summary: string;
    findings: {
      category: string;
      severity: string;
      issue: string;
      reason: string;
      mitigation: string;
      requires_revision: boolean;
    }[];
  }[];
};
export type DeliverableState = {
  items: {
    kind: string;
    label: string;
    artifact: Artifact | null;
    stale: boolean;
  }[];
  jobs: Record<string, { status: string; error?: string }>;
  busy: boolean;
  role: string;
};
export type Collaboration = {
  comments: {
    id: string;
    author_name: string;
    content: string;
    artifact_kind: string;
    created_at: string;
  }[];
  reviews: {
    id: string;
    kind: string;
    version: number;
    decision: string;
    reviewer_name: string;
    note: string;
  }[];
  activity: {
    id: string;
    action: string;
    detail: string;
    created_at: string;
  }[];
};
export type Workspace = {
  id: string;
  name: string;
  organization: string;
  access_role: string;
  model?: string;
  ai_policy?: string;
  retention_days?: number;
};
export const languages: Record<string, string> = {
  en: "English",
  hi: "हिन्दी",
  es: "Español",
  fr: "Français",
  de: "Deutsch",
  ar: "العربية",
  pt: "Português",
  zh: "中文",
  ja: "日本語",
  ko: "한국어",
  it: "Italiano",
  bn: "বাংলা",
  ta: "தமிழ்",
  te: "తెలుగు",
  mr: "मराठी",
  ur: "اردو",
  ru: "Русский",
  id: "Bahasa Indonesia",
  tr: "Türkçe",
  vi: "Tiếng Việt",
};
export function blankDeliverable(title: string): Deliverable {
  return {
    title,
    summary: "Describe the purpose of this deliverable.",
    sections: [
      {
        title: "Requirements",
        narrative: "Describe the requirements and evidence.",
        items: [],
        tables: [],
      },
    ],
    diagrams: [],
    screens: [],
    code_assets: [],
    assumptions: [],
    validation_steps: ["Review with the project owner."],
  };
}
