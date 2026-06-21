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

export type EventFilter = "all" | "model" | "tool_call" | "error";
