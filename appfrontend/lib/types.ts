export type Health = {
  status: string;
  database: string;
  gemini_configured: boolean;
  google_configured: boolean;
  google_client_id: string;
  local_access_enabled: boolean;
  vector_search_configured: boolean;
  max_upload_mb: number;
  email_configured: boolean;
};
export type User = { id: string; name: string; email: string; local: boolean };
export type Fact = { category: string; fact: string; source: string };
export type Necessity = {
  classification: string;
  score: number;
  reasoning: string[];
  non_ai_alternative: string;
  recommended_approach: string;
  confidence: number;
};
export type ModelOption = {
  id: string;
  label: string;
  description: string;
  supports_effort: boolean;
};
export type EffortOption = { id: string; label: string; description: string };
export type ModelCatalog = {
  models: ModelOption[];
  default_model: string;
  efforts: EffortOption[];
  default_effort: string;
};
export type Project = {
  id: string;
  name: string;
  industry: string;
  workspace_id?: string | null;
  language?: string;
  model?: string;
  effort?: string;
  access_role?: string;
  initial_problem: string;
  status: string;
  discovery_scores: Record<string, number>;
  discovery: {
    collected_information: Fact[];
    missing_information: string[];
    critical_missing: string[];
  } | null;
  analysis_ready: boolean;
  busy: boolean;
  active_generation_id?: string | null;
  ai_necessity: Necessity | null;
  error: string | null;
  created_at: string;
  updated_at: string;
  retrieval_warnings?: string[];
};
export type DiscoveryQuestion = {
  question: string;
  topic: string;
  reason: string;
  label?: string;
  hint?: string;
};
export type Message = {
  id: string;
  role: string;
  content: string;
  created_at: string;
  message_type?: string;
  request_id?: string;
  questions?: DiscoveryQuestion[];
  question_notice?: string;
};
export type Document = {
  id: string;
  filename: string;
  status: string;
  summary: string;
  file_type: string;
  size: number;
  chunk_count?: number;
  error: string | null;
  warnings?: string[];
  facts?: Fact[];
};
export type Finding = {
  category: string;
  severity: string;
  issue: string;
  reason: string;
  mitigation: string;
  requires_revision: boolean;
};
export type Evidence = {
  title: string;
  description: string;
  evidence: string[];
  confidence: number;
};
export type Table = { title: string; columns: string[]; rows: string[][] };
export type Diagram = {
  title: string;
  kind: string;
  nodes: { id: string; label: string; lane: string; kind: string }[];
  edges: { source: string; target: string; label: string }[];
};
export type ReportChapter = {
  key: string;
  title: string;
  narrative: string;
  basis: string;
  applicability: "applicable" | "not_applicable";
  items: string[];
  tables: Table[];
  diagrams: Diagram[];
  screens: {
    name: string;
    persona: string;
    purpose: string;
    controls: { label: string; kind: string; detail: string }[];
  }[];
  code_assets: { filename: string; language: string; content: string }[];
};
export type ImplementationDocument = {
  schema_version: number;
  report_version?: number;
  prepared_at?: string;
  title: string;
  industry: string;
  language: string;
  source_revision: number;
  selected_option: string;
  sections: ReportChapter[];
};
type Dimension = { score: number; reason: string };
export type Solution = {
  title: string;
  summary: string;
  solution_type: string;
  complexity: string;
  components: {
    name: string;
    responsibility: string;
    uses_ai: boolean;
    reason: string;
  }[];
  data_flow: string[];
  data_requirements: string[];
  integrations: string[];
  human_in_loop: string[];
  constraints: string[];
  assumptions: string[];
  roadmap: {
    phase: string;
    title: string;
    actions: string[];
    exit_criteria: string;
  }[];
  success_metrics: string[];
};
export type Analysis = import("./review").ReviewData & {
  final_report?: ImplementationDocument;
  workflow_analysis?: {
    business_context: string;
    current_system: {
      people: string[];
      process: string;
      technology: string[];
      data: string[];
    };
    workflow: {
      name: string;
      owner: string;
      description: string;
      tools: string[];
    }[];
    bottlenecks: Evidence[];
  };
  root_cause?: {
    user_request: string;
    root_problem: string;
    root_causes: Evidence[];
    assumptions: string[];
  };
  ai_necessity?: Necessity;
  solution?: Solution;
  red_team?: { summary: string; findings: Finding[] };
  red_team_cycle?: number;
  red_team_history?: { summary: string; findings: Finding[] }[];
  solution_history?: Solution[];
  business_value?: {
    summary: string;
    metrics: {
      metric: string;
      estimate: string;
      basis: string;
      is_assumption: boolean;
    }[];
    feasibility: {
      technical: Dimension;
      data: Dimension;
      integration: Dimension;
      operational: Dimension;
      business: Dimension;
      overall: number;
    };
    risks: Finding[];
  };
  conclusion?: {
    executive_summary: string;
    recommendation: string;
    next_steps: string[];
  };
  evidence?: Fact[];
  problem_statement?: string;
  retrieval_warnings?: string[];
};
export type Blueprint = {
  id: string;
  version: number;
  created_at: string;
  content: Analysis;
};
export type Usage = {
  configured_connections: number;
  available_connections: number;
  status: string;
  retry_at: string | null;
  remaining_requests: number | null;
  request_limit: number | null;
  reset_at: string | null;
  quota_note: string;
};
