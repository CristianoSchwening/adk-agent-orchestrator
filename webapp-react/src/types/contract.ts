export type AgentVisibility = 'internal' | 'user_visible' | 'hidden'
export type AgentStatus = 'draft' | 'published' | 'superseded' | 'failed'

export interface AgentVisibleResponse {
  response_id: string
  agent_name: string
  agent_role: string
  content: string
  depends_on_response_ids: string[]
  visibility: AgentVisibility
  status: AgentStatus
  publication_order: number
  created_at: string
  metadata: Record<string, unknown>
}

export interface TaskDTO {
  task_id: string
  session_id: string
  objective: string
  status: string
  workflow: string
  started_at: string
  finished_at: string | null
  final_response: string | null
}

export interface SubtaskDTO {
  subtask_id: string
  name: string
  agent_name: string | null
  status: string
  workflow: string | null
  output_summary: string | null
  started_at: string | null
  finished_at: string | null
}

export interface EventDTO {
  event_id: string
  type: string
  message: string
  timestamp: string
  source: string
  severity: string
  subtask_id: string | null
  metadata: Record<string, unknown>
}

export interface MetricsDTO {
  duration_ms: number
  event_count: number
  subtask_count: number
  artifact_count: number
  tool_call_count: number
  model_event_count: number
  error_count: number
  custom: Record<string, unknown>
}

export interface DecisionMetadataDTO {
  selected_workflow: string
  rationale: string
  confidence: number
  alternatives: string[]
  policy_version: string
}

export interface ArtifactDTO {
  artifact_id: string
  name: string
  mime_type: string | null
  uri: string | null
}

export interface ExecutionContractDTO {
  contract_version: string
  task: TaskDTO
  subtasks: SubtaskDTO[]
  events: EventDTO[]
  metrics: MetricsDTO
  decision_metadata: DecisionMetadataDTO
  artifacts: ArtifactDTO[]
  progressive_agent_responses: AgentVisibleResponse[]
}
