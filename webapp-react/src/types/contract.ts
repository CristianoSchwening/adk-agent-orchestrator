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
  workflow?: string
  app_name?: string
  user_id?: string
  started_at?: string
  finished_at?: string | null
  created_at?: string
  updated_at?: string
  final_response: string | null
}

export interface SubtaskDTO {
  subtask_id: string
  name: string
  agent_name: string | null
  status: string
  workflow: string | null
  input_summary?: string | null
  output_summary: string | null
  started_at: string | null
  finished_at: string | null
  error?: string | null
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
  size_bytes?: number | null
  metadata?: Record<string, unknown>
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
  task_plan?: TaskPlanDTO | null
  task_run?: PlanRunDTO | null
}

export interface TaskRunDTO {
  task_id: string
  status: string
  assigned_agent: string | null
  execution_strategy: string
  execution_node: string | null
  selection_reason: string | null
  attempt: number
  result: unknown
  error: string | null
  updated_at: string
}

export interface PlanRunDTO {
  schema_version: string
  run_id: string
  plan_id: string
  status: string
  tasks: TaskRunDTO[]
  created_at: string
  updated_at: string
}

export interface PlannedTaskDTO {
  task_id: string
  title: string
  description: string
  task_type: string
  depends_on: string[]
  required_capabilities: string[]
  acceptance_criteria: string[]
  strategy: string
  requires_review: boolean
  requires_approval: boolean
  metadata: Record<string, unknown>
}

export interface TaskPlanDTO {
  schema_version: string
  plan_id: string
  status: string
  revision: number
  goal: {
    objective: string
    constraints: string[]
    success_criteria: string[]
  }
  tasks: PlannedTaskDTO[]
  deliverables: Array<{ deliverable_id: string; description: string }>
  assumptions: string[]
  workstream_id: string | null
  created_at: string
  updated_at: string
}
