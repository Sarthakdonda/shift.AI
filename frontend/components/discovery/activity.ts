/** Activity copy follows observable work, never a simulated sequence of thoughts. */
const stages: Record<string, string> = {
  DOCUMENT_ANALYSIS: "Reading documents",
  SYSTEM_ANALYSIS: "Analyzing your workflow",
  AI_NECESSITY: "Evaluating whether AI is needed",
  SOLUTION_GENERATION: "Developing your solution",
  RED_TEAM_REVIEW: "Reviewing risks and assumptions",
  BUSINESS_VALUE: "Assessing business value",
};

export function activityLabel({ status, busy, action, effort, stopping }: {
  status: string;
  busy: boolean;
  action: string;
  effort: string;
  stopping: boolean;
}) {
  if (stopping) return "Stopping response";
  // Server stages take priority over the initial request's generic action label.
  if (busy && stages[status]) return stages[status];
  if (action === "Uploading document") return "Uploading document";
  if (action === "Starting analysis") return "Preparing analysis";
  if (action === "Thinking through your answer" || (busy && status === "DISCOVERY")) {
    return effort === "instant" ? "Preparing your reply" : "Thinking";
  }
  return "Working";
}
