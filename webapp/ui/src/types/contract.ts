export type EventSeverity = "debug" | "info" | "warning" | "error";

export type EventType =
  | "model"
  | "tool_call"
  | "tool_response"
  | "tool_result"
  | "final_response"
  | "adk_event"
  | string;

export interface ContractArtifact {
  artifact_id: string;
  name: string;
  mime_type?: string | null;
  uri?: string | null;
  size_bytes?: number | null;
  metadata?: Record<string, unknown>;
}

export interface ContractEvent {
  event_id: string;
  type: EventType;
  message: string;
  timestamp: string;
  source: string;
  severity: EventSeverity;
  subtask_id?: string | null;
  metadata?: Record<string, unknown>;
}

export interface ContractTask {
  task_id: string;
  objective: string;
  status: string;
  app_name?: string | null;
  user_id?: string | null;
  session_id?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  final_response?: string | null;
}

export interface ContractSubtask {
  subtask_id: string;
  name: string;
  status: string;
  agent_name?: string | null;
  workflow?: string | null;
  input_summary?: string | null;
  output_summary?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  error?: string | null;
}

export interface ContractMetrics {
  duration_ms?: number | null;
  event_count?: number | null;
  subtask_count?: number | null;
  artifact_count?: number | null;
  tool_call_count?: number | null;
  model_event_count?: number | null;
  error_count?: number | null;
  custom?: Record<string, unknown> | null;
}

export interface DecisionMetadata {
  selected_workflow?: string | null;
  rationale?: string | null;
  confidence?: number | null;
  alternatives?: string[] | null;
  policy_version?: string | null;
}

export interface ExecutionContract {
  contract_version: string;
  task: ContractTask;
  subtasks: ContractSubtask[];
  events: ContractEvent[];
  metrics?: ContractMetrics | null;
  decision_metadata?: DecisionMetadata | null;
  artifacts: ContractArtifact[];
}

export type EventFilter = "all" | "model" | "tool_call" | "error";
