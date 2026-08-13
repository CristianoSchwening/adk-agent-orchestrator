import { AlertCircle, Bot, CheckCircle2, CircleDot, Cpu, Wrench } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { formatTime, humanizeStatus } from '@/lib/format'
import type { AgentVisibleResponse, EventDTO } from '@/types/contract'

type TimelineItem =
  | { id: string; timestamp: string; kind: 'event'; event: EventDTO }
  | { id: string; timestamp: string; kind: 'response'; response: AgentVisibleResponse }

function eventIcon(type: string, severity: string) {
  if (severity === 'error' || type === 'error') return AlertCircle
  if (type.includes('tool')) return Wrench
  if (type === 'final_response') return CheckCircle2
  if (type === 'model') return Cpu
  return CircleDot
}

function buildTimeline(events: EventDTO[], responses: AgentVisibleResponse[]): TimelineItem[] {
  return [
    ...events.map((event): TimelineItem => ({ id: event.event_id, timestamp: event.timestamp, kind: 'event', event })),
    ...responses.map((response): TimelineItem => ({ id: response.response_id, timestamp: response.created_at, kind: 'response', response })),
  ].sort((left, right) => {
    const timeDifference = Date.parse(left.timestamp) - Date.parse(right.timestamp)
    if (timeDifference !== 0) return timeDifference
    if (left.kind === 'response' && right.kind === 'response') return left.response.publication_order - right.response.publication_order
    return left.kind === 'event' ? -1 : 1
  })
}

interface ActivityTimelineProps {
  events: EventDTO[]
  responses: AgentVisibleResponse[]
}

export function ActivityTimeline({ events, responses }: ActivityTimelineProps) {
  const items = buildTimeline(events, responses)

  if (!items.length) {
    return <div className="py-12 text-center text-sm text-muted-foreground">Nenhuma atividade registrada nesta execução.</div>
  }

  return (
    <div className="px-4 py-5 sm:px-6">
      <ol className="relative ml-3 border-l border-border">
        {items.map((item) => {
          if (item.kind === 'response') {
            const { response } = item
            return (
              <li key={item.id} className="relative pb-7 pl-7 last:pb-0">
                <span className="absolute -left-3 flex size-6 items-center justify-center rounded-full border border-primary/20 bg-primary/10 text-primary ring-4 ring-card">
                  <Bot className="size-3.5" />
                </span>
                <div className="flex flex-wrap items-start gap-x-3 gap-y-1">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs font-semibold">{response.agent_name}</span>
                      <span className="text-[11px] text-muted-foreground">{response.agent_role}</span>
                      <Badge variant={response.status}>{humanizeStatus(response.status)}</Badge>
                      {response.visibility === 'internal' && <Badge variant="internal">Interna</Badge>}
                    </div>
                    <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-foreground/90">{response.content}</p>
                    {response.depends_on_response_ids.length > 0 && (
                      <div className="mt-2 text-[11px] text-muted-foreground">
                        Depende de {response.depends_on_response_ids.length} contribuição{response.depends_on_response_ids.length > 1 ? 'ões' : ''}
                      </div>
                    )}
                  </div>
                  <time className="text-[10px] text-muted-foreground">{formatTime(response.created_at)}</time>
                </div>
              </li>
            )
          }

          const { event } = item
          const Icon = eventIcon(event.type, event.severity)
          return (
            <li key={item.id} className="relative pb-7 pl-7 last:pb-0">
              <span className="absolute -left-3 flex size-6 items-center justify-center rounded-full border border-border bg-secondary text-muted-foreground ring-4 ring-card">
                <Icon className="size-3.5" />
              </span>
              <div className="flex flex-wrap items-start gap-x-3 gap-y-1">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-semibold">{event.source}</span>
                    <Badge variant="outline">{event.type.replace(/_/g, ' ')}</Badge>
                  </div>
                  <p className="mt-1 text-sm leading-6 text-muted-foreground">{event.message}</p>
                </div>
                <time className="text-[10px] text-muted-foreground">{formatTime(event.timestamp)}</time>
              </div>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
