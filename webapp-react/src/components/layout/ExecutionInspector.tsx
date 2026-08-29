import {
  Activity,
  Bot,
  ChevronDown,
  CircleCheck,
  CircleDashed,
  CircleX,
  Download,
  FileJson,
  FileText,
  Gauge,
  Image,
  ListChecks,
  Route,
  ServerCog,
  Wrench,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { formatDuration, humanizeStatus } from '@/lib/format'
import { collectToolNames, deriveAgents, formatBytes } from '@/lib/execution-model'
import { workflowLabel } from '@/config/workflows'
import type { ArtifactDTO, ExecutionContractDTO } from '@/types/contract'

interface ExecutionInspectorProps {
  contract: ExecutionContractDTO | null
}

function InspectorSection({
  title,
  icon: Icon,
  children,
  detail,
  defaultOpen = true,
}: {
  title: string
  icon: typeof Bot
  children: React.ReactNode
  detail?: string
  defaultOpen?: boolean
}) {
  return (
    <details className="group overflow-hidden rounded-xl border border-border bg-card" open={defaultOpen}>
      <summary className="focus-ring flex cursor-pointer list-none items-center gap-2 px-4 py-3 [&::-webkit-details-marker]:hidden">
        <Icon className="size-4 text-muted-foreground" />
        <h2 className="text-sm font-semibold">{title}</h2>
        {detail && <span className="rounded-full bg-secondary px-2 py-0.5 text-[10px] text-muted-foreground">{detail}</span>}
        <ChevronDown className="ml-auto size-4 text-muted-foreground transition-transform group-open:rotate-180" />
      </summary>
      <div className="border-t border-border p-3">{children}</div>
    </details>
  )
}

function statusIcon(status: string) {
  if (status === 'completed' || status === 'published') return <CircleCheck className="size-3.5 text-emerald-500" />
  if (status === 'failed') return <CircleX className="size-3.5 text-destructive" />
  return <CircleDashed className="size-3.5 text-amber-500" />
}

function artifactIcon(artifact: ArtifactDTO) {
  if (artifact.mime_type?.startsWith('image/')) return Image
  if (artifact.mime_type?.includes('json')) return FileJson
  return FileText
}

export function ExecutionInspector({ contract }: ExecutionInspectorProps) {
  const agents = deriveAgents(contract)
  const tools = collectToolNames(contract)
  const completed = contract?.subtasks.filter((subtask) => subtask.status === 'completed').length ?? 0
  const mcpCount = Number(contract?.metrics.custom.mcp_server_count ?? 0)

  return (
    <aside className="h-full min-h-0 overflow-y-auto border-l border-border bg-background p-3">
      <div className="mb-3 flex items-center gap-2 px-1 py-1">
        <Bot className="size-4 text-primary" />
        <span className="text-sm font-semibold">Orquestração</span>
        {contract && <Badge variant="outline" className="ml-auto">contrato v1</Badge>}
      </div>

      <div className="space-y-3">
        <InspectorSection title="Agent Pool" icon={Bot} detail={contract ? `${agents.length} agentes` : undefined}>
          {agents.length ? (
            <div className="space-y-2">
              {agents.map((agent) => (
                <div key={agent.name} className="rounded-lg bg-secondary/70 px-3 py-2.5">
                  <div className="flex items-center gap-3">
                    <span className="flex size-8 items-center justify-center rounded-lg bg-primary/10 text-xs font-semibold text-primary">
                      {agent.name.charAt(0).toUpperCase()}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-xs font-medium">{agent.name}</div>
                      <div className="truncate text-[10px] text-muted-foreground">{agent.role}</div>
                    </div>
                    {statusIcon(agent.status)}
                  </div>
                  <div className="mt-2 flex items-center gap-2 pl-11 text-[10px] text-muted-foreground">
                    <span>{agent.responseCount} resp.</span>
                    <span>·</span>
                    <span>{agent.subtaskCount} subtarefa{agent.subtaskCount === 1 ? '' : 's'}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs leading-5 text-muted-foreground">Os agentes participantes aparecerão após iniciar uma execução.</p>
          )}
        </InspectorSection>

        <InspectorSection title="Progresso" icon={Activity} detail={contract ? `${completed}/${contract.subtasks.length}` : undefined}>
          {contract?.subtasks.length ? (
            <div className="space-y-3">
              <div className="h-1.5 overflow-hidden rounded-full bg-secondary">
                <div className="h-full rounded-full bg-emerald-500" style={{ width: `${(completed / contract.subtasks.length) * 100}%` }} />
              </div>
              {contract.subtasks.map((subtask) => (
                <div key={subtask.subtask_id} className="flex items-start gap-2 text-xs">
                  <span className="mt-0.5">{statusIcon(subtask.status)}</span>
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-medium">{subtask.name}</div>
                    <div className="mt-0.5 truncate text-[10px] text-muted-foreground">{humanizeStatus(subtask.status)} · {subtask.agent_name ?? 'Agente não informado'}</div>
                    {subtask.output_summary && <p className="mt-1 line-clamp-2 text-[10px] leading-4 text-muted-foreground">{subtask.output_summary}</p>}
                    {subtask.error && <p className="mt-1 text-[10px] text-destructive">{subtask.error}</p>}
                  </div>
                </div>
              ))}
            </div>
          ) : <p className="text-xs text-muted-foreground">Nenhuma subtarefa disponível.</p>}
        </InspectorSection>

        <InspectorSection title="Plano de tarefas" icon={ListChecks} detail={contract?.task_plan ? `${contract.task_plan.tasks.length} tarefas` : undefined}>
          {contract?.task_plan ? (
            <div className="space-y-3 text-xs">
              <div>
                <div className="font-medium">{contract.task_plan.goal.objective}</div>
                <div className="mt-1 text-[10px] text-muted-foreground">{contract.task_plan.plan_id} · revisão {contract.task_plan.revision}</div>
              </div>
              <div className="space-y-2 border-t border-border pt-2">
                {contract.task_plan.tasks.map((task) => (
                  <div key={task.task_id} className="rounded-lg bg-secondary/70 px-3 py-2">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{task.title}</span>
                      <Badge variant="outline" className="ml-auto">{task.strategy}</Badge>
                    </div>
                    <div className="mt-1 text-[10px] text-muted-foreground">
                      {task.task_id}{task.depends_on.length ? ` · depende de ${task.depends_on.join(', ')}` : ' · tarefa inicial'}
                    </div>
                  </div>
                ))}
              </div>
              <div className="border-t border-border pt-2 text-[10px] text-muted-foreground">
                {contract.task_plan.deliverables.length} entregável(is) · plano validado, ainda não executado dinamicamente
              </div>
            </div>
          ) : <p className="text-xs text-muted-foreground">Nenhum plano de tarefas associado a esta execução.</p>}
        </InspectorSection>

        <InspectorSection title="Decisão de roteamento" icon={Route}>
          {contract ? (
            <div className="space-y-3 text-xs">
              <div className="flex items-center justify-between gap-3"><span className="text-muted-foreground">Workflow</span><span className="text-right font-medium">{workflowLabel(contract.decision_metadata.selected_workflow)}</span></div>
              <div>
                <div className="mb-1.5 flex items-center justify-between"><span className="text-muted-foreground">Confiança</span><span className="font-medium">{Math.round(contract.decision_metadata.confidence * 100)}%</span></div>
                <div className="h-1.5 overflow-hidden rounded-full bg-secondary"><div className="h-full rounded-full bg-primary" style={{ width: `${contract.decision_metadata.confidence * 100}%` }} /></div>
              </div>
              <p className="border-t border-border pt-2 leading-5 text-muted-foreground">{contract.decision_metadata.rationale}</p>
              {contract.decision_metadata.alternatives.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {contract.decision_metadata.alternatives.map((alternative) => <Badge key={alternative} variant="outline">{workflowLabel(alternative)}</Badge>)}
                </div>
              )}
              <div className="text-[10px] text-muted-foreground">Política: {contract.decision_metadata.policy_version}</div>
            </div>
          ) : <p className="text-xs text-muted-foreground">A decisão de roteamento será exibida aqui.</p>}
        </InspectorSection>

        <InspectorSection title="Contexto de execução" icon={ServerCog} defaultOpen={false}>
          {contract ? (
            <div className="space-y-3 text-xs">
              <div className="flex items-center justify-between"><span className="text-muted-foreground">Sessão</span><code className="max-w-[150px] truncate text-[10px]">{contract.task.session_id}</code></div>
              <div className="flex items-center justify-between"><span className="text-muted-foreground">Aplicação</span><span>{contract.task.app_name ?? 'adk-agent-orchestrator'}</span></div>
              <div className="flex items-center justify-between"><span className="text-muted-foreground">MCP servers</span><span>{mcpCount}</span></div>
              <div className="border-t border-border pt-2">
                <div className="mb-2 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground"><Wrench className="size-3" />Tools observadas</div>
                {tools.length ? <div className="flex flex-wrap gap-1">{tools.map((tool) => <Badge key={tool} variant="secondary">{tool}</Badge>)}</div> : <p className="text-[10px] text-muted-foreground">Nenhum nome de tool publicado nos eventos.</p>}
              </div>
            </div>
          ) : <p className="text-xs text-muted-foreground">O contexto será exibido após a execução.</p>}
        </InspectorSection>

        <InspectorSection title="Métricas" icon={Gauge} defaultOpen={false}>
          <div className="grid grid-cols-2 gap-2 text-xs">
            {[
              ['Duração', formatDuration(contract?.metrics.duration_ms)],
              ['Eventos', contract?.metrics.event_count ?? 0],
              ['Subtarefas', contract?.metrics.subtask_count ?? 0],
              ['Artefatos', contract?.metrics.artifact_count ?? 0],
              ['Tool calls', contract?.metrics.tool_call_count ?? 0],
              ['Modelo', contract?.metrics.model_event_count ?? 0],
              ['Erros', contract?.metrics.error_count ?? 0],
            ].map(([label, value]) => (
              <div key={label} className="rounded-lg bg-secondary/70 p-2">
                <div className="text-[10px] text-muted-foreground">{label}</div>
                <div className="mt-1 font-semibold">{value}</div>
              </div>
            ))}
          </div>
        </InspectorSection>

        <InspectorSection title="Artefatos" icon={FileText} detail={contract ? String(contract.artifacts.length) : undefined}>
          {contract?.artifacts.length ? contract.artifacts.map((artifact) => {
            const Icon = artifactIcon(artifact)
            const canOpen = Boolean(artifact.uri?.startsWith('http'))
            return (
              <div key={artifact.artifact_id} className="group/file flex items-center gap-2 rounded-lg px-2 py-2 text-xs hover:bg-secondary">
                <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-secondary text-muted-foreground"><Icon className="size-4" /></span>
                <div className="min-w-0 flex-1">
                  <div className="truncate font-medium">{artifact.name}</div>
                  <div className="mt-0.5 flex gap-2 text-[10px] text-muted-foreground"><span>{artifact.mime_type ?? 'Arquivo'}</span>{formatBytes(artifact.size_bytes) && <span>{formatBytes(artifact.size_bytes)}</span>}</div>
                </div>
                {canOpen && <a href={artifact.uri ?? '#'} target="_blank" rel="noreferrer" aria-label={`Abrir ${artifact.name}`} className="focus-ring rounded p-1 text-muted-foreground hover:text-primary"><Download className="size-3.5" /></a>}
              </div>
            )
          }) : <p className="text-xs text-muted-foreground">Nenhum artefato produzido.</p>}
        </InspectorSection>
      </div>
    </aside>
  )
}
