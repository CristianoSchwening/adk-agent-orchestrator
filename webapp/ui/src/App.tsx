import { useMemo, useState } from 'react'
import { Bot, BrainCircuit, FileUp, Gauge, GitBranch, Route, Sparkles } from 'lucide-react'
import { ArtifactsPanel } from '@/components/artifacts/ArtifactsPanel'
import { EventLogPanel } from '@/components/event-log/EventLogPanel'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import {
  PromptInput,
  PromptInputActionAddAttachments,
  PromptInputActionAddScreenshot,
  PromptInputActionMenu,
  PromptInputActionMenuContent,
  PromptInputActionMenuTrigger,
  PromptInputBody,
  PromptInputFooter,
  PromptInputHeader,
  type PromptInputMessage,
  PromptInputSubmit,
  PromptInputTextarea,
  PromptInputTools,
  usePromptInputAttachments,
} from '@/components/ai-elements/prompt-input'
import { Attachment, AttachmentInfo, AttachmentPreview, AttachmentRemove, Attachments } from '@/components/ai-elements/attachments'
import type { ContractMetrics, ContractSubtask, DecisionMetadata, ExecutionContract } from '@/types/contract'
import './App.css'

const demoObjective = 'Mapear riscos, subtarefas e métricas da orquestração ADK'

const workflowOptions = [
  { id: 'sequential', label: 'Sequential' },
  { id: 'parallel', label: 'Parallel' },
  { id: 'progressive_multi_agent_response', label: 'Progressive' },
]

function PromptInputAttachmentsDisplay() {
  const attachments = usePromptInputAttachments()
  if (attachments.files.length === 0) return null
  return (
    <Attachments variant="inline" className="max-h-28 overflow-y-auto">
      {attachments.files.map((attachment) => (
        <Attachment data={attachment} key={attachment.id} onRemove={() => attachments.remove(attachment.id)}>
          <AttachmentPreview />
          <AttachmentInfo showMediaType />
          <AttachmentRemove />
        </Attachment>
      ))}
    </Attachments>
  )
}

function statusVariant(status: string): 'default' | 'secondary' | 'destructive' | 'outline' {
  if (status === 'completed' || status === 'published') return 'default'
  if (status === 'failed' || status === 'error') return 'destructive'
  if (status === 'running') return 'secondary'
  return 'outline'
}

function formatDuration(ms?: number | null) {
  if (ms == null) return '—'
  return `${(ms / 1000).toFixed(2)}s`
}

function SubtasksPanel({ subtasks }: { subtasks: ContractSubtask[] }) {
  const completed = subtasks.filter((subtask) => subtask.status === 'completed').length
  return (
    <Card className="border-border/80 bg-card/90">
      <CardHeader className="border-b border-border/70">
        <CardTitle className="flex items-center gap-2"><GitBranch className="size-4 text-indigo-300" />Subtasks</CardTitle>
        <CardDescription>Timeline de execução dos subagentes.</CardDescription>
        <CardAction><Badge variant="outline">{subtasks.length} steps</Badge></CardAction>
      </CardHeader>
      <CardContent className="space-y-4">
        <Progress value={completed} max={Math.max(subtasks.length, 1)} />
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
          {subtasks.map((subtask) => (
            <Card key={subtask.subtask_id} size="sm" className="border-border/70 bg-background/45">
              <CardHeader>
                <CardTitle className="flex items-center justify-between gap-3">
                  <span className="truncate">{subtask.name}</span>
                  <Badge variant={statusVariant(subtask.status)}>{subtask.status}</Badge>
                </CardTitle>
                <CardDescription>{subtask.agent_name ?? 'agent'}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2 text-sm text-muted-foreground">
                <p>{subtask.output_summary ?? subtask.input_summary ?? 'Aguardando saída da etapa.'}</p>
                {subtask.workflow ? <Badge variant="outline">{subtask.workflow}</Badge> : null}
              </CardContent>
            </Card>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

function MetricsPanel({ metrics }: { metrics?: ContractMetrics | null }) {
  const items = [
    ['Duration', formatDuration(metrics?.duration_ms)],
    ['Events', metrics?.event_count ?? 0],
    ['Subtasks', metrics?.subtask_count ?? 0],
    ['Artifacts', metrics?.artifact_count ?? 0],
    ['Tool calls', metrics?.tool_call_count ?? 0],
    ['Model events', metrics?.model_event_count ?? 0],
  ]
  return (
    <Card className="border-border/80 bg-card/90">
      <CardHeader className="border-b border-border/70">
        <CardTitle className="flex items-center gap-2"><Gauge className="size-4 text-cyan-300" />Metrics</CardTitle>
        <CardDescription>Resumo operacional do contrato.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3 sm:grid-cols-2">
        {items.map(([label, value]) => (
          <div key={label} className="rounded-lg border border-border/70 bg-background/45 p-3">
            <div className="text-xs uppercase tracking-wide text-muted-foreground">{label}</div>
            <div className="mt-1 text-2xl font-semibold">{value}</div>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

function DecisionAuditPanel({ decision }: { decision?: DecisionMetadata | null }) {
  const confidence = Math.round((decision?.confidence ?? 0) * 100)
  return (
    <Card className="border-border/80 bg-card/90">
      <CardHeader className="border-b border-border/70">
        <CardTitle className="flex items-center gap-2"><Route className="size-4 text-emerald-300" />Decision Audit</CardTitle>
        <CardDescription>Roteamento, confiança e alternativas.</CardDescription>
        <CardAction><Badge>{decision?.policy_version ?? 'policy'}</Badge></CardAction>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap gap-2">
          <Badge variant="secondary">{decision?.selected_workflow ?? 'workflow'}</Badge>
          {(decision?.alternatives ?? []).map((item) => <Badge key={item} variant="outline">alt: {item}</Badge>)}
        </div>
        <div className="space-y-2">
          <div className="flex justify-between text-sm"><span>Confidence</span><span>{confidence}%</span></div>
          <Progress value={confidence} />
        </div>
        <p className="text-sm leading-6 text-muted-foreground">{decision?.rationale ?? 'Sem racional de decisão disponível.'}</p>
      </CardContent>
    </Card>
  )
}

function App() {
  const [contract, setContract] = useState<ExecutionContract | null>(null)
  const [workflow, setWorkflow] = useState(workflowOptions[0].id)
  const [status, setStatus] = useState<'ready' | 'submitted'>('ready')
  const [error, setError] = useState<string | null>(null)

  const objective = useMemo(() => contract?.task.objective ?? demoObjective, [contract])

  const runDemo = async (message?: PromptInputMessage) => {
    setStatus('submitted')
    setError(null)
    try {
      const response = await fetch('/api/run/demo', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ objective: message?.text || demoObjective, workflow }),
      })
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      setContract(await response.json())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Falha ao executar demo')
    } finally {
      setStatus('ready')
    }
  }

  return (
    <main className="min-h-screen bg-background bg-[radial-gradient(circle_at_20%_20%,rgba(99,102,241,.28),transparent_34%),radial-gradient(circle_at_80%_0%,rgba(14,165,233,.18),transparent_30%)] p-4 text-foreground md:p-8">
      <div className="mx-auto grid max-w-[1500px] gap-6 xl:grid-cols-[minmax(0,1.05fr)_minmax(420px,.95fr)]">
        <section className="space-y-6">
          <Card className="border-border/80 bg-card/90 shadow-2xl shadow-black/30">
            <CardHeader>
              <Badge variant="outline" className="w-fit gap-1"><Sparkles className="size-3" />Estágio 5 — Shell completo</Badge>
              <CardTitle className="max-w-4xl text-4xl font-semibold tracking-[-0.06em] md:text-6xl">Orquestração ADK unificada em React</CardTitle>
              <CardDescription className="max-w-3xl text-base leading-7">Subtasks, Metrics, Decision Audit, Event Log e Artifacts agora compartilham o mesmo design system shadcn com Tailwind buildado pelo Vite.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-3">
              {['React SPA único', 'Tailwind sem CDN', 'Componentes shadcn'].map((item) => (
                <div key={item} className="flex items-center gap-3 rounded-xl border border-border/70 bg-background/45 p-4"><FileUp className="size-4 text-indigo-300" />{item}</div>
              ))}
            </CardContent>
          </Card>

          <div className="grid gap-6 lg:grid-cols-2">
            <SubtasksPanel subtasks={contract?.subtasks ?? []} />
            <div className="space-y-6">
              <MetricsPanel metrics={contract?.metrics} />
              <DecisionAuditPanel decision={contract?.decision_metadata} />
            </div>
          </div>

          <EventLogPanel events={contract?.events ?? []} />
          <ArtifactsPanel artifacts={contract?.artifacts ?? []} />
        </section>

        <aside className="space-y-6 xl:sticky xl:top-8 xl:self-start">
          <Card className="border-border/80 bg-card/95 shadow-2xl shadow-black/30">
            <CardHeader className="border-b border-border/70">
              <CardTitle className="flex items-center gap-2"><Bot className="size-5 text-indigo-300" />Console de execução</CardTitle>
              <CardDescription>{objective}</CardDescription>
              <CardAction><BrainCircuit className="size-5 text-cyan-300" /></CardAction>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-3 gap-2">
                {workflowOptions.map((option) => (
                  <Button key={option.id} variant={workflow === option.id ? 'default' : 'outline'} size="sm" onClick={() => setWorkflow(option.id)}>{option.label}</Button>
                ))}
              </div>
              <PromptInput accept="image/*,.pdf,.txt,.md,.json,.csv,.log" globalDrop multiple onSubmit={runDemo} className="border-indigo-400/40">
                <PromptInputHeader><PromptInputAttachmentsDisplay /></PromptInputHeader>
                <PromptInputBody><PromptInputTextarea placeholder="Descreva a tarefa para gerar o contrato demo..." /></PromptInputBody>
                <PromptInputFooter>
                  <PromptInputTools>
                    <PromptInputActionMenu>
                      <PromptInputActionMenuTrigger />
                      <PromptInputActionMenuContent>
                        <PromptInputActionAddAttachments label="Anexar contexto" />
                        <PromptInputActionAddScreenshot label="Anexar screenshot" />
                      </PromptInputActionMenuContent>
                    </PromptInputActionMenu>
                  </PromptInputTools>
                  <PromptInputSubmit status={status} />
                </PromptInputFooter>
              </PromptInput>
              <Button className="w-full" onClick={() => runDemo()}>Carregar contrato demo</Button>
              {error ? <p className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">{error}</p> : null}
            </CardContent>
          </Card>
        </aside>
      </div>
    </main>
  )
}

export default App
