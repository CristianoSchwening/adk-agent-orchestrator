import { useState } from 'react'
import { Loader2, ArrowLeft, Play, Zap } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ProgressivePanel } from '@/components/progressive/ProgressivePanel'
import { useContract } from '@/hooks/useContract'
import { cn } from '@/lib/utils'

const WORKFLOWS = [
  { value: 'progressive_multi_agent_response', label: 'Progressive Multi-Agent' },
  { value: 'sequential',                       label: 'Sequential' },
  { value: 'parallel',                         label: 'Parallel' },
  { value: 'review_critic',                    label: 'Review & Critic' },
  { value: 'iterative_refinement',             label: 'Iterative Refinement' },
]

export default function App() {
  const [objective, setObjective] = useState('')
  const [workflow,  setWorkflow]  = useState('progressive_multi_agent_response')
  const { contract, loading, error, loadDemo, run } = useContract()

  const handleDemo = () => {
    const obj = objective.trim() || 'Build a production-ready ADK agent orchestrator'
    loadDemo(obj, workflow)
  }

  const handleRun = () => {
    const obj = objective.trim()
    if (!obj) return
    run(obj, workflow)
  }

  const responses = contract?.progressive_agent_responses ?? []
  const hasProgressive = responses.length > 0

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col">

      {/* ── Topbar ───────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-50 border-b border-border bg-card px-6 h-14 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-purple-500 flex items-center justify-center text-base">🤖</div>
          <div>
            <div className="text-sm font-bold leading-none">ADK Orchestrator</div>
            <div className="text-[11px] text-muted-foreground leading-none mt-0.5">
              React — Stage 1 · AI Elements Messages
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Stage badge */}
          <span className="text-[10px] font-semibold px-2 py-1 rounded-full bg-primary/10 text-primary border border-primary/20">
            Estágio 1
          </span>
          <a
            href="/"
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            App atual
          </a>
        </div>
      </header>

      {/* ── Input bar ────────────────────────────────────────────────── */}
      <div className="border-b border-border bg-card px-6 py-3">
        <div className="max-w-4xl mx-auto flex gap-2 flex-wrap items-center">
          <input
            value={objective}
            onChange={e => setObjective(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleRun()}
            placeholder="Enter objective for the orchestrator…"
            className={cn(
              'flex-1 min-w-[240px] h-9 px-3 rounded-lg border border-border bg-secondary',
              'text-sm text-foreground placeholder:text-muted-foreground',
              'focus:outline-none focus:border-primary/60 transition-colors',
            )}
          />
          <select
            value={workflow}
            onChange={e => setWorkflow(e.target.value)}
            className={cn(
              'h-9 px-3 rounded-lg border border-border bg-secondary',
              'text-sm text-foreground cursor-pointer',
              'focus:outline-none focus:border-primary/60',
            )}
          >
            {WORKFLOWS.map(w => (
              <option key={w.value} value={w.value} className="bg-card">
                {w.label}
              </option>
            ))}
          </select>
          <Button variant="secondary" size="sm" onClick={handleDemo} disabled={loading} className="h-9">
            {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Zap className="w-3.5 h-3.5" />}
            Load Demo
          </Button>
          <Button size="sm" onClick={handleRun} disabled={loading || !objective.trim()} className="h-9">
            {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
            Run
          </Button>
        </div>
      </div>

      {/* ── Main content ─────────────────────────────────────────────── */}
      <main className="flex-1 max-w-4xl mx-auto w-full px-6 py-8 flex flex-col gap-6">

        {/* Error */}
        {error && (
          <div className="rounded-xl border border-red-500/30 bg-red-500/5 px-4 py-3 text-sm text-red-400">
            ⚠ {error}
          </div>
        )}

        {/* Task summary */}
        {contract?.task && (
          <div className="rounded-xl border border-border bg-card px-5 py-4 flex items-center justify-between gap-4 flex-wrap">
            <div>
              <div className="text-xs text-muted-foreground mb-1">Objective</div>
              <div className="text-sm font-semibold">{contract.task.objective}</div>
            </div>
            <div className="flex items-center gap-3 flex-shrink-0">
              <span className={cn(
                'text-[11px] font-semibold px-2 py-1 rounded-full border',
                contract.task.status === 'completed'
                  ? 'bg-green-500/10 text-green-400 border-green-500/30'
                  : 'bg-primary/10 text-primary border-primary/30',
              )}>
                {contract.task.status}
              </span>
              {contract.metrics?.duration_ms != null && (
                <span className="text-[11px] text-muted-foreground">
                  {(contract.metrics.duration_ms / 1000).toFixed(2)}s
                </span>
              )}
              <span className="text-[11px] text-muted-foreground">
                {contract.decision_metadata?.selected_workflow}
              </span>
            </div>
          </div>
        )}

        {/* Progressive Responses panel */}
        {hasProgressive ? (
          <ProgressivePanel responses={responses} />
        ) : !loading && !contract ? (
          /* Empty state */
          <div className="flex-1 flex flex-col items-center justify-center py-20 gap-6 text-center">
            <div className="w-20 h-20 rounded-2xl bg-primary/10 border border-primary/20 flex items-center justify-center text-4xl">
              💬
            </div>
            <div>
              <h2 className="text-lg font-semibold mb-2">Stage 1 — AI Elements Messages</h2>
              <p className="text-sm text-muted-foreground max-w-sm leading-relaxed">
                Clique em <strong>Load Demo</strong> para carregar 5 respostas de agentes com{' '}
                <code className="text-primary text-xs bg-primary/10 px-1 rounded">visibility</code>,{' '}
                <code className="text-primary text-xs bg-primary/10 px-1 rounded">status</code> e{' '}
                <code className="text-primary text-xs bg-primary/10 px-1 rounded">agent_role</code>.
                Depois alterne entre <strong>Chat</strong> e <strong>DAG</strong> (com hover cards).
              </p>
            </div>
            <Button onClick={handleDemo} disabled={loading} className="gap-2">
              <Zap className="w-4 h-4" />
              Load Demo
            </Button>
          </div>
        ) : loading ? (
          <div className="flex-1 flex items-center justify-center py-20">
            <div className="flex items-center gap-3 text-muted-foreground">
              <Loader2 className="w-5 h-5 animate-spin" />
              <span className="text-sm">Running orchestrator…</span>
            </div>
          </div>
        ) : (
          /* Contract loaded but no progressive responses */
          <div className="rounded-xl border border-dashed border-border p-8 text-center text-muted-foreground text-sm">
            Este workflow não gerou respostas progressivas.
            Selecione <strong>Progressive Multi-Agent</strong> e clique em Load Demo.
          </div>
        )}

      </main>
    </div>
  )
}
