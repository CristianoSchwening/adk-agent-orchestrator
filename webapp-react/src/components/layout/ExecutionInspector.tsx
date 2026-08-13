import { Activity, Bot, ChevronDown, FileText, Gauge, Route } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { formatDuration, humanizeStatus } from '@/lib/format'
import { workflowLabel } from '@/config/workflows'
import type { ExecutionContractDTO } from '@/types/contract'

interface ExecutionInspectorProps {
  contract: ExecutionContractDTO | null
}

function InspectorSection({
  title,
  icon: Icon,
  children,
}: {
  title: string
  icon: typeof Bot
  children: React.ReactNode
}) {
  return (
    <section className="overflow-hidden rounded-xl border border-border bg-card">
      <div className="flex items-center gap-2 border-b border-border px-4 py-3">
        <Icon className="size-4 text-muted-foreground" />
        <h2 className="text-sm font-semibold">{title}</h2>
        <ChevronDown className="ml-auto size-4 text-muted-foreground" />
      </div>
      <div className="p-3">{children}</div>
    </section>
  )
}

export function ExecutionInspector({ contract }: ExecutionInspectorProps) {
  const agents = Array.from(new Map(
    (contract?.progressive_agent_responses ?? []).map((response) => [response.agent_name, response]),
  ).values())
  const completed = contract?.subtasks.filter((subtask) => subtask.status === 'completed').length ?? 0

  return (
    <aside className="h-full min-h-0 overflow-y-auto border-l border-border bg-background p-3">
      <div className="mb-3 flex items-center gap-2 px-1 py-1">
        <Bot className="size-4 text-primary" />
        <span className="text-sm font-semibold">Orquestração</span>
        {contract && <Badge variant="outline" className="ml-auto">ao vivo</Badge>}
      </div>

      <div className="space-y-3">
        <InspectorSection title="Agent Pool" icon={Bot}>
          {agents.length ? (
            <div className="space-y-2">
              {agents.map((agent) => (
                <div key={agent.agent_name} className="flex items-center gap-3 rounded-lg bg-secondary/70 px-3 py-2">
                  <span className="flex size-7 items-center justify-center rounded-lg bg-primary/10 text-xs font-semibold text-primary">
                    {agent.agent_name.charAt(0).toUpperCase()}
                  </span>
                  <div className="min-w-0">
                    <div className="truncate text-xs font-medium">{agent.agent_name}</div>
                    <div className="text-[10px] text-muted-foreground">{agent.agent_role}</div>
                  </div>
                  <span className="ml-auto size-2 rounded-full bg-emerald-500" />
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs leading-5 text-muted-foreground">Os agentes participantes aparecerão após iniciar uma execução.</p>
          )}
        </InspectorSection>

        <InspectorSection title={`Progresso${contract ? ` · ${completed}/${contract.subtasks.length}` : ''}`} icon={Activity}>
          {contract?.subtasks.length ? (
            <div className="space-y-2">
              {contract.subtasks.map((subtask) => (
                <div key={subtask.subtask_id} className="flex items-start gap-2 text-xs">
                  <span className={`mt-1 size-2 shrink-0 rounded-full ${subtask.status === 'completed' ? 'bg-emerald-500' : 'bg-amber-500'}`} />
                  <div className="min-w-0">
                    <div className="truncate font-medium">{subtask.name}</div>
                    <div className="truncate text-[10px] text-muted-foreground">{humanizeStatus(subtask.status)} · {subtask.agent_name ?? 'Agente'}</div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">Nenhuma subtarefa disponível.</p>
          )}
        </InspectorSection>

        <InspectorSection title="Decisão" icon={Route}>
          {contract ? (
            <div className="space-y-2 text-xs">
              <div className="flex items-center justify-between gap-3"><span className="text-muted-foreground">Workflow</span><span className="text-right font-medium">{workflowLabel(contract.decision_metadata.selected_workflow)}</span></div>
              <div className="flex items-center justify-between"><span className="text-muted-foreground">Confiança</span><span className="font-medium">{Math.round(contract.decision_metadata.confidence * 100)}%</span></div>
              <p className="border-t border-border pt-2 leading-5 text-muted-foreground">{contract.decision_metadata.rationale}</p>
            </div>
          ) : <p className="text-xs text-muted-foreground">A decisão de roteamento será exibida aqui.</p>}
        </InspectorSection>

        <InspectorSection title="Métricas" icon={Gauge}>
          <div className="grid grid-cols-2 gap-2 text-xs">
            {[
              ['Duração', formatDuration(contract?.metrics.duration_ms)],
              ['Eventos', contract?.metrics.event_count ?? 0],
              ['Tools', contract?.metrics.tool_call_count ?? 0],
              ['Erros', contract?.metrics.error_count ?? 0],
            ].map(([label, value]) => (
              <div key={label} className="rounded-lg bg-secondary/70 p-2">
                <div className="text-[10px] text-muted-foreground">{label}</div>
                <div className="mt-1 font-semibold">{value}</div>
              </div>
            ))}
          </div>
        </InspectorSection>

        <InspectorSection title="Artefatos" icon={FileText}>
          {contract?.artifacts.length ? contract.artifacts.map((artifact) => (
            <div key={artifact.artifact_id} className="flex items-center gap-2 rounded-lg px-2 py-2 text-xs hover:bg-secondary">
              <FileText className="size-4 text-muted-foreground" />
              <span className="min-w-0 flex-1 truncate">{artifact.name}</span>
            </div>
          )) : <p className="text-xs text-muted-foreground">Nenhum artefato produzido.</p>}
        </InspectorSection>
      </div>
    </aside>
  )
}
