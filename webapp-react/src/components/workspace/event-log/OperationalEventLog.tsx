import {
  AlertTriangle,
  Bot,
  Check,
  ChevronDown,
  CircleDot,
  Clipboard,
  Cpu,
  FileSearch,
  Search,
  Wrench,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  buildEventLogEntries,
  entryMatchesFilter,
  entryMatchesQuery,
  type EventLogEntry,
  type EventLogFilter,
} from '@/lib/event-log-model'
import { formatTime } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { EventDTO } from '@/types/contract'

const FILTERS: { id: EventLogFilter; label: string }[] = [
  { id: 'all', label: 'Todos' },
  { id: 'model', label: 'Modelo' },
  { id: 'tools', label: 'Tools' },
  { id: 'errors', label: 'Erros' },
  { id: 'workspace', label: 'Workspace' },
]

function JsonDetails({ label, value }: { label: string; value: unknown }) {
  const [copied, setCopied] = useState(false)
  if (value == null || (typeof value === 'object' && Object.keys(value as object).length === 0)) return null
  const formatted = typeof value === 'string' ? value : JSON.stringify(value, null, 2)
  const copy = async () => {
    await navigator.clipboard.writeText(formatted)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1200)
  }
  return (
    <section className="overflow-hidden rounded-lg border border-border bg-background/70">
      <div className="flex items-center border-b border-border px-3 py-2">
        <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">{label}</span>
        <Button variant="ghost" size="icon" onClick={copy} className="ml-auto size-6" aria-label={`Copiar ${label}`}>
          {copied ? <Check className="size-3 text-emerald-500" /> : <Clipboard className="size-3" />}
        </Button>
      </div>
      <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words p-3 font-mono text-[11px] leading-5 text-foreground/80">{formatted}</pre>
    </section>
  )
}

function eventTone(event: EventDTO) {
  if (event.severity === 'error' || event.type === 'error') return 'text-destructive bg-destructive/10 border-destructive/20'
  if (event.type.startsWith('workspace_')) return 'text-violet-500 bg-violet-500/10 border-violet-500/20'
  if (event.type === 'final_response') return 'text-emerald-500 bg-emerald-500/10 border-emerald-500/20'
  return 'text-primary bg-primary/10 border-primary/20'
}

function EventEntry({ event }: { event: EventDTO }) {
  const Icon = event.severity === 'error' ? AlertTriangle : event.type.startsWith('workspace_') ? FileSearch : event.type === 'model' ? Cpu : event.type === 'final_response' ? Bot : CircleDot
  return (
    <details className="group rounded-xl border border-border bg-card">
      <summary className="focus-ring flex cursor-pointer list-none items-start gap-3 px-4 py-3 [&::-webkit-details-marker]:hidden">
        <span className={cn('mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg border', eventTone(event))}><Icon className="size-4" /></span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold">{event.source}</span>
            <Badge variant="outline">{event.type.replace(/_/g, ' ')}</Badge>
            {event.severity === 'error' && <Badge variant="failed">Erro</Badge>}
          </div>
          <p className="mt-1 line-clamp-2 text-xs leading-5 text-muted-foreground">{event.message}</p>
        </div>
        <time className="shrink-0 text-[10px] text-muted-foreground">{formatTime(event.timestamp)}</time>
        <ChevronDown className="mt-1 size-3.5 shrink-0 text-muted-foreground transition-transform group-open:rotate-180" />
      </summary>
      <div className="grid gap-3 border-t border-border p-4">
        <p className="whitespace-pre-wrap text-sm leading-6">{event.message}</p>
        <JsonDetails label="Metadados" value={event.metadata} />
        <div className="flex flex-wrap gap-3 text-[10px] text-muted-foreground">
          <span>event_id: {event.event_id}</span>
          {event.subtask_id && <span>subtask: {event.subtask_id}</span>}
          <span>severity: {event.severity}</span>
        </div>
      </div>
    </details>
  )
}

function ToolEntry({ entry }: { entry: Extract<EventLogEntry, { kind: 'tool' }> }) {
  const failed = [entry.call, entry.response].some((event) => event?.severity === 'error')
  const status = failed ? 'Erro' : entry.response ? 'Concluída' : 'Pendente'
  return (
    <details className="group rounded-xl border border-border bg-card">
      <summary className="focus-ring flex cursor-pointer list-none items-start gap-3 px-4 py-3 [&::-webkit-details-marker]:hidden">
        <span className={cn('mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg border', failed ? 'border-destructive/20 bg-destructive/10 text-destructive' : 'border-cyan-500/20 bg-cyan-500/10 text-cyan-500')}><Wrench className="size-4" /></span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2"><span className="text-xs font-semibold">{entry.toolName}</span><Badge variant="outline">tool</Badge><Badge variant={failed ? 'failed' : entry.response ? 'published' : 'draft'}>{status}</Badge></div>
          <p className="mt-1 truncate text-xs text-muted-foreground">{entry.source}</p>
        </div>
        <time className="shrink-0 text-[10px] text-muted-foreground">{formatTime(entry.timestamp)}</time>
        <ChevronDown className="mt-1 size-3.5 shrink-0 text-muted-foreground transition-transform group-open:rotate-180" />
      </summary>
      <div className="grid gap-3 border-t border-border p-4 lg:grid-cols-2">
        <JsonDetails label="Input" value={entry.call?.metadata?.input ?? entry.call?.metadata?.arguments ?? entry.call?.message} />
        <JsonDetails label="Output" value={entry.response?.metadata?.output ?? entry.response?.metadata?.result ?? entry.response?.message} />
        <JsonDetails label="Metadados da chamada" value={entry.call?.metadata} />
        <JsonDetails label="Metadados da resposta" value={entry.response?.metadata} />
      </div>
    </details>
  )
}

export function OperationalEventLog({ events }: { events: EventDTO[] }) {
  const [filter, setFilter] = useState<EventLogFilter>('all')
  const [query, setQuery] = useState('')
  const [autoScroll, setAutoScroll] = useState(true)
  const listRef = useRef<HTMLDivElement>(null)
  const entries = useMemo(() => buildEventLogEntries(events), [events])
  const filtered = useMemo(() => entries.filter((entry) => entryMatchesFilter(entry, filter) && entryMatchesQuery(entry, query)), [entries, filter, query])

  useEffect(() => {
    if (autoScroll && listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight
  }, [filtered, autoScroll])

  return (
    <div>
      <div className="flex flex-col gap-3 border-b border-border p-3 sm:p-4">
        <div className="flex flex-wrap items-center gap-1">
          {FILTERS.map(({ id, label }) => <button key={id} type="button" onClick={() => setFilter(id)} className={cn('focus-ring rounded-lg px-3 py-1.5 text-xs font-medium', filter === id ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:bg-secondary')}>{label}</button>)}
          <button type="button" aria-pressed={autoScroll} onClick={() => setAutoScroll((value) => !value)} className={cn('focus-ring ml-auto rounded-lg px-3 py-1.5 text-xs font-medium', autoScroll ? 'bg-emerald-500/10 text-emerald-600' : 'text-muted-foreground hover:bg-secondary')}>Auto-scroll</button>
        </div>
        <label className="relative block">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Buscar agente, tool, mensagem ou metadado…" className="focus-ring h-9 w-full rounded-lg border border-border bg-secondary/60 pl-9 pr-3 text-xs" />
        </label>
        <div className="text-[10px] text-muted-foreground">{filtered.length} de {entries.length} entradas operacionais</div>
      </div>
      <div ref={listRef} className="max-h-[680px] space-y-2 overflow-y-auto p-3 sm:p-4">
        {filtered.map((entry) => entry.kind === 'tool' ? <ToolEntry key={entry.id} entry={entry} /> : <EventEntry key={entry.id} event={entry.event} />)}
        {!filtered.length && <div className="py-14 text-center text-sm text-muted-foreground">Nenhum evento corresponde aos filtros atuais.</div>}
      </div>
    </div>
  )
}
