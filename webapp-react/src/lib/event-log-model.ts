import type { EventDTO } from '@/types/contract'

export type EventLogFilter = 'all' | 'model' | 'tools' | 'errors' | 'workspace'

export type EventLogEntry =
  | { kind: 'event'; id: string; event: EventDTO }
  | {
      kind: 'tool'
      id: string
      call: EventDTO | null
      response: EventDTO | null
      toolName: string
      source: string
      timestamp: string
    }

function metadataText(event: EventDTO, ...keys: string[]) {
  for (const key of keys) {
    const value = event.metadata?.[key]
    if (value != null && String(value).trim()) return String(value)
  }
  return null
}

export function toolName(event: EventDTO) {
  return metadataText(event, 'tool_name', 'tool', 'name') ?? event.source ?? 'tool'
}

function correlationKey(event: EventDTO) {
  const explicit = metadataText(
    event,
    'invocation_id',
    'tool_call_id',
    'call_id',
    'request_id',
    'correlation_id',
  )
  return explicit ? `id:${explicit}` : `fallback:${event.source}:${toolName(event)}`
}

export function buildEventLogEntries(events: EventDTO[]): EventLogEntry[] {
  const entries: EventLogEntry[] = []
  const pending = new Map<string, number[]>()

  for (const event of events) {
    if (event.type !== 'tool_call' && event.type !== 'tool_response') {
      entries.push({ kind: 'event', id: event.event_id, event })
      continue
    }

    const key = correlationKey(event)
    if (event.type === 'tool_call') {
      const index = entries.push({
        kind: 'tool',
        id: `tool:${event.event_id}`,
        call: event,
        response: null,
        toolName: toolName(event),
        source: event.source,
        timestamp: event.timestamp,
      }) - 1
      pending.set(key, [...(pending.get(key) ?? []), index])
      continue
    }

    const queue = pending.get(key) ?? []
    const match = queue.shift()
    if (match != null) {
      const entry = entries[match]
      if (entry.kind === 'tool') entry.response = event
      if (queue.length) pending.set(key, queue)
      else pending.delete(key)
    } else {
      entries.push({
        kind: 'tool',
        id: `tool:${event.event_id}`,
        call: null,
        response: event,
        toolName: toolName(event),
        source: event.source,
        timestamp: event.timestamp,
      })
    }
  }

  return entries.sort((left, right) => Date.parse(entryTimestamp(left)) - Date.parse(entryTimestamp(right)))
}

export function entryTimestamp(entry: EventLogEntry) {
  return entry.kind === 'tool' ? entry.timestamp : entry.event.timestamp
}

export function entryMatchesFilter(entry: EventLogEntry, filter: EventLogFilter) {
  if (filter === 'all') return true
  if (filter === 'tools') return entry.kind === 'tool'
  if (entry.kind === 'tool') {
    return filter === 'errors' && [entry.call, entry.response].some((event) => event?.severity === 'error')
  }
  if (filter === 'model') return ['model', 'final_response'].includes(entry.event.type)
  if (filter === 'errors') return entry.event.severity === 'error' || entry.event.type === 'error'
  return entry.event.type.startsWith('workspace_') || Boolean(entry.event.metadata?.trace_id)
}

export function entryMatchesQuery(entry: EventLogEntry, query: string) {
  const normalized = query.trim().toLocaleLowerCase()
  if (!normalized) return true
  const events = entry.kind === 'tool' ? [entry.call, entry.response].filter(Boolean) : [entry.event]
  const searchable = entry.kind === 'tool' ? [entry.toolName, entry.source] : []
  for (const event of events) {
    if (!event) continue
    searchable.push(event.source, event.type, event.message, JSON.stringify(event.metadata ?? {}))
  }
  return searchable.join(' ').toLocaleLowerCase().includes(normalized)
}
