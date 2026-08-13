import type { ExecutionContractDTO } from '@/types/contract'

export interface AgentSummary {
  name: string
  role: string
  status: string
  responseCount: number
  subtaskCount: number
  eventCount: number
}

export function deriveAgents(contract: ExecutionContractDTO | null): AgentSummary[] {
  if (!contract) return []
  const agents = new Map<string, AgentSummary>()

  for (const response of contract.progressive_agent_responses) {
    const current = agents.get(response.agent_name) ?? {
      name: response.agent_name,
      role: response.agent_role || 'Especialista',
      status: response.status,
      responseCount: 0,
      subtaskCount: 0,
      eventCount: 0,
    }
    current.responseCount += 1
    current.status = response.status
    agents.set(response.agent_name, current)
  }

  for (const subtask of contract.subtasks) {
    if (!subtask.agent_name) continue
    const current = agents.get(subtask.agent_name) ?? {
      name: subtask.agent_name,
      role: subtask.name,
      status: subtask.status,
      responseCount: 0,
      subtaskCount: 0,
      eventCount: 0,
    }
    current.subtaskCount += 1
    current.status = subtask.status
    agents.set(subtask.agent_name, current)
  }

  for (const event of contract.events) {
    const current = agents.get(event.source)
    if (current) current.eventCount += 1
  }

  return Array.from(agents.values()).sort((left, right) => right.responseCount - left.responseCount || left.name.localeCompare(right.name))
}

export function collectToolNames(contract: ExecutionContractDTO | null) {
  if (!contract) return []
  const names = new Set<string>()
  for (const event of contract.events) {
    if (!event.type.includes('tool')) continue
    const candidate = event.metadata.tool_name ?? event.metadata.name ?? event.source
    if (typeof candidate === 'string' && candidate) names.add(candidate)
  }
  return Array.from(names)
}

export function formatBytes(bytes?: number | null) {
  if (bytes == null) return null
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
