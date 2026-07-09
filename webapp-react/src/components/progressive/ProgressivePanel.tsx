import { useState, useMemo } from 'react'
import { Message } from './Message'
import { GraderMessage } from './GraderMessage'
import { DagView } from './DagView'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { AgentVisibleResponse } from '@/types/contract'

type View = 'chat' | 'dag'

interface ProgressivePanelProps {
  responses: AgentVisibleResponse[]
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function getIteration(r: AgentVisibleResponse): number | undefined {
  const v = (r.metadata as Record<string, unknown>)?.loop_iteration
  return typeof v === 'number' ? v : undefined
}

function isGrader(r: AgentVisibleResponse) {
  return r.agent_role === 'Grader' || r.agent_name === 'rubric_grader'
}

// ── Iteration header ──────────────────────────────────────────────────────────

function IterationHeader({ iteration, graderMeta }: {
  iteration: number
  graderMeta: Record<string, unknown> | null
}) {
  const passed = graderMeta?.passed as boolean | undefined
  const score  = graderMeta?.overall_score as number | undefined

  return (
    <div className={cn(
      'flex items-center gap-2 px-3 py-2 rounded-lg border text-[11px] font-semibold',
      passed === true  ? 'border-green-500/30 bg-green-500/5  text-green-400' :
      passed === false ? 'border-red-500/30   bg-red-500/5    text-red-400' :
                         'border-border       bg-secondary    text-muted-foreground',
    )}>
      <span className="text-base">{passed === true ? '✅' : passed === false ? '❌' : '🔁'}</span>
      <span>Iteration {iteration + 1}</span>
      {score !== undefined && (
        <span className="opacity-70">— score: {(score * 100).toFixed(0)}%</span>
      )}
      {passed === false && <span className="ml-auto opacity-70 font-normal">FAILED · retrying…</span>}
      {passed === true  && <span className="ml-auto opacity-70 font-normal">PASSED · published</span>}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

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

  const idToRole  = useMemo(() => Object.fromEntries(sorted.map(r => [r.response_id, r.agent_role || r.agent_name])), [sorted])
  const idToOrder = useMemo(() => Object.fromEntries(sorted.map(r => [r.response_id, r.publication_order])), [sorted])

  // Detect verification loop mode (any response has loop_iteration in metadata)
  const isVerificationLoop = useMemo(
    () => visible.some(r => getIteration(r) !== undefined),
    [visible],
  )

  // Group by iteration (only in verification mode)
  const byIteration = useMemo(() => {
    if (!isVerificationLoop) return null
    const map = new Map<number, AgentVisibleResponse[]>()
    for (const r of visible) {
      const it = getIteration(r) ?? 0
      if (!map.has(it)) map.set(it, [])
      map.get(it)!.push(r)
    }
    return map
  }, [visible, isVerificationLoop])

  // Build render list: for verification mode, add iteration headers
  const renderItems = useMemo(() => {
    if (!isVerificationLoop || !byIteration) {
      return visible.map((r, i) => ({ type: 'message' as const, r, chatIndex: i }))
    }
    const items: Array<
      | { type: 'iteration-header'; iteration: number; graderMeta: Record<string, unknown> | null }
      | { type: 'message'; r: AgentVisibleResponse; chatIndex: number }
    > = []
    let chatIndex = 0
    for (const [iteration, group] of [...byIteration.entries()].sort(([a], [b]) => a - b)) {
      const graderR = group.find(isGrader)
      const graderMeta = graderR
        ? (graderR.metadata as Record<string, unknown>)
        : null
      items.push({ type: 'iteration-header', iteration, graderMeta })
      for (const r of group) {
        items.push({ type: 'message', r, chatIndex: chatIndex++ })
      }
    }
    return items
  }, [visible, isVerificationLoop, byIteration])

  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden">

      {/* ── Header ─────────────────────────────────────────────────── */}
      <div className="px-4 py-3 border-b border-border flex items-center gap-2 flex-wrap">
        <div className="w-5 h-5 rounded-md bg-purple-500/15 flex items-center justify-center text-sm flex-shrink-0">
          {isVerificationLoop ? '🔁' : '💬'}
        </div>
        <span className="text-xs font-semibold uppercase tracking-widest text-foreground">
          {isVerificationLoop ? 'Loop 2 — Verification' : 'Progressive Agent Responses'}
        </span>

        {isVerificationLoop && byIteration && (
          <div className="flex gap-1 ml-1">
            {[...byIteration.entries()].sort(([a], [b]) => a - b).map(([it, group]) => {
              const graderR = group.find(isGrader)
              const passed = graderR
                ? (graderR.metadata as Record<string, unknown>).passed as boolean
                : undefined
              return (
                <span key={it} className={cn(
                  'text-[10px] px-1.5 py-0.5 rounded-full border font-semibold',
                  passed === true  ? 'border-green-500/30 bg-green-500/10 text-green-400' :
                  passed === false ? 'border-red-500/30   bg-red-500/10   text-red-400' :
                                     'border-border bg-secondary text-muted-foreground',
                )}>
                  Iter {it + 1} {passed === true ? '✅' : passed === false ? '❌' : ''}
                </span>
              )
            })}
          </div>
        )}

        <div className="ml-auto flex items-center gap-2">
          <span className="text-[11px] text-muted-foreground">{responses.length} responses</span>

          {/* Chat / DAG toggle */}
          <div className="flex border border-border rounded-md overflow-hidden">
            {(['chat', 'dag'] as View[]).map(v => (
              <button
                key={v}
                onClick={() => setView(v)}
                className={cn(
                  'px-3 py-1 text-[11px] font-semibold transition-colors',
                  view === v
                    ? 'bg-primary text-white'
                    : 'bg-transparent text-muted-foreground hover:text-foreground',
                )}
              >
                {v === 'chat' ? '💬 Chat' : '🔀 DAG'}
              </button>
            ))}
          </div>

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

      {/* ── Legend ────────────────────────────────────────────────── */}
      {view === 'chat' && (
        <div className="px-4 py-2 border-b border-border flex flex-wrap gap-1.5 items-center">
          <span className="text-[10px] text-muted-foreground font-semibold uppercase tracking-wide mr-1">Status:</span>
          {(['published', 'superseded', 'draft', 'failed'] as const).map(v => (
            <Badge key={v} variant={v}>{v}</Badge>
          ))}
          {isVerificationLoop && (
            <>
              <span className="text-[10px] text-muted-foreground font-semibold uppercase tracking-wide ml-3 mr-1">Grader:</span>
              <span className="text-[10px] px-2 py-0.5 rounded-full border border-green-500/30 bg-green-500/10 text-green-400">pass</span>
              <span className="text-[10px] px-2 py-0.5 rounded-full border border-red-500/30 bg-red-500/10 text-red-400">fail</span>
            </>
          )}
        </div>
      )}

      {/* ── Content ───────────────────────────────────────────────── */}
      {view === 'chat' ? (
        <div className="p-4 flex flex-col gap-3 max-h-[620px] overflow-y-auto">
          {visible.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-10 text-muted-foreground gap-2">
              <span className="text-3xl opacity-40">💬</span>
              <span className="text-sm">No responses yet</span>
            </div>
          ) : (
            renderItems.map((item) => {
              if (item.type === 'iteration-header') {
                return (
                  <IterationHeader
                    key={`iter-${item.iteration}`}
                    iteration={item.iteration}
                    graderMeta={item.graderMeta}
                  />
                )
              }
              const { r, chatIndex } = item
              if (isGrader(r) && isVerificationLoop) {
                return <GraderMessage key={r.response_id} response={r} />
              }
              return (
                <Message
                  key={r.response_id}
                  response={r}
                  index={chatIndex}
                  idToRole={idToRole}
                  idToOrder={idToOrder}
                />
              )
            })
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
