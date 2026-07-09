import { useState } from 'react'
import { Loader2, Play, Square, Copy, Check, Clock, Webhook, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { useLoop3 } from '@/hooks/useLoop3'
import type { ExecutionSummary, TriggerSource } from '@/types/loop3'

const WORKFLOWS = [
  { value: 'loop2_verification',               label: 'Loop 2 — Verificação' },
  { value: 'progressive_multi_agent_response', label: 'Progressive Multi-Agent' },
  { value: 'sequential',                       label: 'Sequential' },
]

const INTERVALS = [
  { label: '10 s',  value: 10 },
  { label: '30 s',  value: 30 },
  { label: '1 min', value: 60 },
  { label: '5 min', value: 300 },
]

function sourceBadge(source: TriggerSource) {
  if (source === 'cron')    return <span className="text-[10px] px-1.5 py-0.5 rounded-full border border-yellow-500/30 bg-yellow-500/10 text-yellow-400">🕐 cron</span>
  if (source === 'webhook') return <span className="text-[10px] px-1.5 py-0.5 rounded-full border border-cyan-500/30 bg-cyan-500/10 text-cyan-400">🔗 webhook</span>
  return <span className="text-[10px] px-1.5 py-0.5 rounded-full border border-border bg-secondary text-muted-foreground">🖐 manual</span>
}

function statusDot(status: string) {
  if (status === 'completed') return <span className="w-2 h-2 rounded-full bg-green-400 inline-block" />
  if (status === 'failed')    return <span className="w-2 h-2 rounded-full bg-red-400 inline-block" />
  return <span className="w-2 h-2 rounded-full bg-yellow-400 inline-block animate-pulse" />
}

function fmtDuration(ms: number) {
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`
}

function fmtTime(iso: string) {
  try { return new Date(iso).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) }
  catch { return iso.slice(11, 19) }
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }
  return (
    <button onClick={copy} className="p-1 rounded hover:bg-secondary transition-colors text-muted-foreground hover:text-foreground">
      {copied ? <Check className="w-3.5 h-3.5 text-green-400" /> : <Copy className="w-3.5 h-3.5" />}
    </button>
  )
}

function HistoryRow({ run }: { run: ExecutionSummary }) {
  return (
    <div className="flex items-center gap-2 px-3 py-2 rounded-lg border border-border bg-secondary/40 text-xs">
      <span className="font-mono text-[10px] text-muted-foreground w-16 flex-shrink-0">#{run.run_id}</span>
      {statusDot(run.status)}
      {sourceBadge(run.source)}
      <span className="flex-1 truncate text-foreground/80">{run.objective}</span>
      <span className="text-muted-foreground flex-shrink-0">{run.response_count} resp</span>
      {run.verification_score !== null && run.verification_score !== undefined && (
        <span className={cn(
          'flex-shrink-0 font-semibold',
          run.verification_passed ? 'text-green-400' : 'text-red-400',
        )}>
          {(run.verification_score * 100).toFixed(0)}%
        </span>
      )}
      <span className="text-muted-foreground flex-shrink-0">{fmtDuration(run.duration_ms)}</span>
      <span className="text-muted-foreground flex-shrink-0">{fmtTime(run.started_at)}</span>
    </div>
  )
}

export function EventLoopPanel() {
  const { config, loading, trigger, setSchedule, stopSchedule, fetchConfig } = useLoop3()

  const [objective,  setObjective]  = useState('Build a production-ready ADK agent orchestrator')
  const [workflow,   setWorkflow]   = useState('loop2_verification')
  const [interval,   setInterval]   = useState(30)

  const webhookUrl = config
    ? `${window.location.origin}/api/loop3/webhook/${config.webhook_token}`
    : '—'

  const handleTrigger = () => trigger(objective, workflow)

  const handleScheduleToggle = async () => {
    if (config?.schedule?.active) {
      await stopSchedule()
      setSchedActive(false)
    } else {
      await setSchedule({ objective, workflow, interval_seconds: interval, active: true })
      setSchedActive(true)
    }
  }

  const isActive = config?.schedule?.active ?? false

  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden">

      {/* ── Header ─────────────────────────────────────────────────── */}
      <div className="px-4 py-3 border-b border-border flex items-center gap-2">
        <div className="w-5 h-5 rounded-md bg-cyan-500/15 flex items-center justify-center text-sm flex-shrink-0">⚡</div>
        <span className="text-xs font-semibold uppercase tracking-widest text-foreground">Loop 3 — Event-Driven</span>
        {isActive && (
          <span className="flex items-center gap-1 text-[10px] text-green-400 border border-green-500/30 bg-green-500/10 px-2 py-0.5 rounded-full ml-1">
            <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
            cron ativo
          </span>
        )}
        <Button variant="ghost" size="icon" onClick={fetchConfig} className="ml-auto h-7 w-7">
          <RefreshCw className="w-3.5 h-3.5" />
        </Button>
      </div>

      <div className="p-4 grid grid-cols-1 md:grid-cols-2 gap-4">

        {/* ── Webhook trigger ────────────────────────────────────── */}
        <div className="space-y-3">
          <div className="flex items-center gap-1.5 text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">
            <Webhook className="w-3.5 h-3.5" /> Webhook / Manual
          </div>

          <div className="flex flex-col gap-2">
            <input
              value={objective}
              onChange={e => setObjective(e.target.value)}
              placeholder="Objective…"
              className="h-8 px-3 rounded-lg border border-border bg-secondary text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary/60 transition-colors"
            />
            <select
              value={workflow}
              onChange={e => setWorkflow(e.target.value)}
              className="h-8 px-3 rounded-lg border border-border bg-secondary text-sm text-foreground focus:outline-none focus:border-primary/60"
            >
              {WORKFLOWS.map(w => (
                <option key={w.value} value={w.value} className="bg-card">{w.label}</option>
              ))}
            </select>
            <Button size="sm" onClick={handleTrigger} disabled={loading} className="h-8">
              {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
              Trigger Manual
            </Button>
          </div>

          {/* Webhook URL */}
          <div className="rounded-lg border border-border bg-secondary/60 px-3 py-2">
            <div className="text-[10px] text-muted-foreground mb-1 font-semibold uppercase tracking-wide">Webhook URL</div>
            <div className="flex items-center gap-1">
              <code className="text-[10px] text-cyan-400 flex-1 break-all leading-snug">{webhookUrl}</code>
              <CopyButton text={webhookUrl} />
            </div>
            <div className="text-[10px] text-muted-foreground mt-1">POST com body: {'{ "objective": "...", "workflow": "..." }'}</div>
          </div>
        </div>

        {/* ── Cron schedule ──────────────────────────────────────── */}
        <div className="space-y-3">
          <div className="flex items-center gap-1.5 text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">
            <Clock className="w-3.5 h-3.5" /> Cron Schedule
          </div>

          <div className="flex flex-col gap-2">
            <div className="flex gap-2">
              <select
                value={interval}
                onChange={e => setInterval(Number(e.target.value))}
                disabled={isActive}
                className="h-8 flex-1 px-3 rounded-lg border border-border bg-secondary text-sm text-foreground focus:outline-none focus:border-primary/60 disabled:opacity-50"
              >
                {INTERVALS.map(i => (
                  <option key={i.value} value={i.value} className="bg-card">{i.label}</option>
                ))}
              </select>

              <Button
                size="sm"
                variant={isActive ? 'secondary' : 'default'}
                onClick={handleScheduleToggle}
                disabled={loading}
                className={cn('h-8', isActive && 'border-red-500/40 text-red-400 hover:border-red-500/60')}
              >
                {loading
                  ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  : isActive ? <><Square className="w-3.5 h-3.5" /> Parar</> : <><Play className="w-3.5 h-3.5" /> Iniciar</>
                }
              </Button>
            </div>
          </div>

          {/* Schedule status */}
          <div className={cn(
            'rounded-lg border px-3 py-2 text-xs space-y-1',
            isActive ? 'border-green-500/30 bg-green-500/5' : 'border-border bg-secondary/40',
          )}>
            {isActive && config?.schedule ? (
              <>
                <div className="flex items-center gap-1 text-green-400 font-semibold">
                  <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
                  Ativo — a cada {config.schedule.interval_seconds}s
                </div>
                <div className="text-muted-foreground truncate">obj: {config.schedule.objective}</div>
                {config.schedule.next_run_at && (
                  <div className="text-muted-foreground">
                    próximo: {fmtTime(config.schedule.next_run_at)}
                  </div>
                )}
              </>
            ) : (
              <div className="text-muted-foreground">Nenhum schedule ativo. Configure acima e clique em Iniciar.</div>
            )}
          </div>

          {/* Stats */}
          {config && (
            <div className="grid grid-cols-3 gap-2 text-center">
              {[
                { label: 'Total', value: config.history.length },
                { label: 'OK', value: config.history.filter(r => r.status === 'completed').length },
                { label: 'Falhas', value: config.history.filter(r => r.status === 'failed').length },
              ].map(s => (
                <div key={s.label} className="rounded-lg border border-border bg-secondary/40 py-1.5">
                  <div className="text-base font-bold text-foreground">{s.value}</div>
                  <div className="text-[10px] text-muted-foreground">{s.label}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── Execution history ─────────────────────────────────────── */}
      {config && config.history.length > 0 && (
        <div className="border-t border-border px-4 py-3">
          <div className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide mb-2">
            Histórico de Execuções ({config.history.length})
          </div>
          <div className="flex flex-col gap-1.5 max-h-52 overflow-y-auto">
            {config.history.map(run => (
              <HistoryRow key={run.run_id} run={run} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
