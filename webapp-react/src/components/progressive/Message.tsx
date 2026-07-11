import { cn } from '@/lib/utils'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import type { AgentVisibleResponse, AgentStatus } from '@/types/contract'

const PALETTE = ['#6366f1', '#a855f7', '#06b6d4', '#22c55e', '#eab308', '#3b82f6']
const allAgentNames: string[] = []

function agentColor(name: string): string {
  if (!allAgentNames.includes(name)) allAgentNames.push(name)
  return PALETTE[allAgentNames.indexOf(name) % PALETTE.length]
}

function statusVariant(status: AgentStatus) {
  return status as 'published' | 'superseded' | 'draft' | 'failed'
}

function fmtTime(iso: string) {
  try {
    return new Date(iso).toLocaleTimeString('en', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch { return iso.slice(11, 19) || '—' }
}

interface MessageProps {
  response: AgentVisibleResponse
  index: number
  idToRole: Record<string, string>
  idToOrder: Record<string, number>
}

export function Message({ response: r, index, idToRole, idToOrder }: MessageProps) {
  const isRight      = index % 2 === 1
  const isInternal   = r.visibility === 'internal'
  const isSuperseded = r.status === 'superseded'
  const isDimmed     = isSuperseded || r.status === 'draft'
  const color        = agentColor(r.agent_name)
  const ts           = r.created_at || ''

  return (
    <div
      className={cn(
        'flex flex-col gap-1.5 fade-in',
        isRight ? 'items-end' : 'items-start',
        isDimmed && 'opacity-60',
      )}
    >
      {/* ── Header row ── */}
      <div
        className={cn(
          'flex items-center gap-1.5 flex-wrap',
          isRight && 'flex-row-reverse',
        )}
      >
        <Avatar className="w-6 h-6 flex-shrink-0" style={{ background: color }}>
          <AvatarFallback style={{ background: color }}>
            {r.agent_name.charAt(0).toUpperCase()}
          </AvatarFallback>
        </Avatar>

        <div className={cn('flex flex-col', isRight && 'items-end')}>
          <div className={cn('flex items-center gap-1.5 flex-wrap', isRight && 'flex-row-reverse')}>
            <span className="text-[12px] font-bold leading-none" style={{ color }}>
              {r.agent_name}
            </span>
            {r.agent_role && (
              <span className="text-[10px] text-muted-foreground italic leading-none">
                {r.agent_role}
              </span>
            )}
            <span className="text-[10px] text-muted-foreground leading-none">
              · order {r.publication_order}
            </span>
          </div>
          <div className={cn('flex items-center gap-1 mt-1 flex-wrap', isRight && 'flex-row-reverse')}>
            <Badge variant={statusVariant(r.status)}>
              {r.status}
            </Badge>
            {isInternal && <Badge variant="internal">🔒 internal</Badge>}
            <span className="text-[10px] text-muted-foreground">{fmtTime(ts)}</span>
          </div>
        </div>
      </div>

      {/* ── Bubble ── */}
      <div
        className={cn(
          'rounded-xl px-4 py-3 max-w-[88%] text-sm leading-relaxed',
          isRight ? 'rounded-tr-sm' : 'rounded-tl-sm',
          isInternal
            ? 'bg-purple-500/5 border border-dashed border-purple-500/30'
            : isRight
            ? 'bg-primary/10 border border-primary/20'
            : 'bg-secondary border border-border',
        )}
      >
        {/* Dependency badges */}
        {r.depends_on_response_ids.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-2">
            <span className="text-[10px] text-muted-foreground">depends on:</span>
            {r.depends_on_response_ids.map(depId => (
              <span
                key={depId}
                className="inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded-full bg-purple-500/10 border border-purple-500/20 text-purple-300"
              >
                🔗 {idToRole[depId] || depId.slice(-6)} #{idToOrder[depId] ?? '?'}
              </span>
            ))}
          </div>
        )}

        {/* Content */}
        <pre
          className={cn(
            'whitespace-pre-wrap break-words font-sans text-[13px] leading-relaxed',
            isSuperseded ? 'line-through text-muted-foreground' : 'text-foreground',
          )}
        >
          {r.content}
        </pre>
      </div>
    </div>
  )
}
