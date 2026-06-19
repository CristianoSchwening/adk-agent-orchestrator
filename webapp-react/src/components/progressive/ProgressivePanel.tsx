import { useState, useMemo } from 'react'
import { Message } from './Message'
import { DagView } from './DagView'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { AgentVisibleResponse } from '@/types/contract'

type View = 'chat' | 'dag'

interface ProgressivePanelProps {
  responses: AgentVisibleResponse[]
}

export function ProgressivePanel({ responses }: ProgressivePanelProps) {
  const [view, setView]             = useState<View>('chat')
  const [showInternal, setInternal] = useState(true)

  const sorted = useMemo(
    () => [...responses].sort((a, b) => (a.publication_order ?? 0) - (b.publication_order ?? 0)),
    [responses],
  )

  const visible = useMemo(
    () => sorted.filter(r => {
      if (r.visibility === 'hidden') return false
      if (!showInternal && r.visibility === 'internal') return false
      return true
    }),
    [sorted, showInternal],
  )

  // Look-up maps for dependency labels
  const idToRole  = useMemo(() => Object.fromEntries(sorted.map(r => [r.response_id, r.agent_role || r.agent_name])), [sorted])
  const idToOrder = useMemo(() => Object.fromEntries(sorted.map(r => [r.response_id, r.publication_order])), [sorted])

  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden">

      {/* ── Header ─────────────────────────────────────────────────── */}
      <div className="px-4 py-3 border-b border-border flex items-center gap-2">
        <div className="w-5 h-5 rounded-md bg-purple-500/15 flex items-center justify-center text-sm flex-shrink-0">💬</div>
        <span className="text-xs font-semibold uppercase tracking-widest text-foreground">
          Progressive Agent Responses
        </span>

        <div className="ml-auto flex items-center gap-2">
          <span className="text-[11px] text-muted-foreground">{responses.length} responses</span>

          {/* Chat / DAG toggle */}
          <div className="flex border border-border rounded-md overflow-hidden">
            <button
              onClick={() => setView('chat')}
              className={cn(
                'px-3 py-1 text-[11px] font-semibold transition-colors',
                view === 'chat' ? 'bg-primary text-white' : 'bg-transparent text-muted-foreground hover:text-foreground',
              )}
            >
              💬 Chat
            </button>
            <button
              onClick={() => setView('dag')}
              className={cn(
                'px-3 py-1 text-[11px] font-semibold transition-colors',
                view === 'dag' ? 'bg-primary text-white' : 'bg-transparent text-muted-foreground hover:text-foreground',
              )}
            >
              🔀 DAG
            </button>
          </div>

          {/* Internal toggle */}
          <Button
            variant={showInternal ? 'outline' : 'ghost'}
            size="sm"
            onClick={() => setInternal(v => !v)}
            className={cn('text-[11px] h-7 px-2', showInternal && 'border-purple-500/40 text-purple-400')}
          >
            👁 Internal
          </Button>
        </div>
      </div>

      {/* ── Legend (chat view only) ────────────────────────────────── */}
      {view === 'chat' && (
        <div className="px-4 py-2 border-b border-border flex flex-wrap gap-1.5 items-center">
          <span className="text-[10px] text-muted-foreground font-semibold uppercase tracking-wide mr-1">Status:</span>
          {(['published', 'superseded', 'draft', 'failed'] as const).map(v => (
            <Badge key={v} variant={v}>{v}</Badge>
          ))}
          <span className="text-[10px] text-muted-foreground font-semibold uppercase tracking-wide ml-3 mr-1">Visibility:</span>
          <Badge variant="user_visible">user_visible</Badge>
          <Badge variant="internal">internal</Badge>
        </div>
      )}

      {/* ── Content ───────────────────────────────────────────────── */}
      {view === 'chat' ? (
        <div className="p-4 flex flex-col gap-4 max-h-[560px] overflow-y-auto">
          {visible.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-10 text-muted-foreground gap-2">
              <span className="text-3xl opacity-40">💬</span>
              <span className="text-sm">No responses yet</span>
            </div>
          ) : (
            visible.map((r, i) => (
              <Message
                key={r.response_id}
                response={r}
                index={i}
                idToRole={idToRole}
                idToOrder={idToOrder}
              />
            ))
          )}
        </div>
      ) : (
        <div className="p-4">
          <DagView responses={sorted} showInternal={showInternal} />
        </div>
      )}
    </div>
  )
}
