export type TriggerSource = 'cron' | 'webhook' | 'manual'
export type RunStatus = 'running' | 'completed' | 'failed'

export interface ScheduleConfig {
  objective: string
  workflow: string
  interval_seconds: number
  active: boolean
  created_at: string
  next_run_at: string | null
}

export interface ExecutionSummary {
  run_id: string
  objective: string
  workflow: string
  source: TriggerSource
  status: RunStatus
  started_at: string
  finished_at: string
  duration_ms: number
  response_count: number
  verification_passed: boolean | null
  verification_score: number | null
}

export interface Loop3Config {
  webhook_token: string
  webhook_url: string
  schedule: ScheduleConfig | null
  history: ExecutionSummary[]
}
