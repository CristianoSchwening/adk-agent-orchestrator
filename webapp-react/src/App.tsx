import { AlertTriangle, Bot, ChevronDown, Clock3, Network, RefreshCw, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { ExecutionComposer } from '@/components/layout/ExecutionComposer'
import { EventLoopPanel } from '@/components/EventLoopPanel'
import { ExecutionViews } from '@/components/workspace/ExecutionViews'
import { FinalResponsePanel } from '@/components/workspace/FinalResponsePanel'
import { ThemeToggle } from '@/components/ThemeToggle'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { DEFAULT_WORKFLOW, workflowLabel } from '@/config/workflows'
import { formatDuration, humanizeStatus } from '@/lib/format'
import { useContract } from '@/hooks/useContract'
import { useTheme } from '@/hooks/useTheme'
import { useStoredState } from '@/hooks/useStoredState'

const DEMO_OBJECTIVE = 'Investigue como estruturar um orquestrador de agentes robusto e produza uma recomendação técnica.'

export default function App() {
  const [objective, setObjective] = useState('')
  const [workflow, setWorkflow] = useStoredState('adk-workflow', DEFAULT_WORKFLOW)
  const [automationsOpen, setAutomationsOpen] = useState(false)
  const { contract, loading, error, loadDemo, run, retry, clear } = useContract()
  const { theme, toggle } = useTheme()

  const handleDemo = () => loadDemo(objective.trim() || DEMO_OBJECTIVE, workflow)
  const handleRun = () => {
    if (objective.trim()) run(objective.trim(), workflow)
  }
  const handleNewExecution = () => {
    clear()
    setObjective('')
    setWorkflow(DEFAULT_WORKFLOW)
  }

  const completedSubtasks = contract?.subtasks.filter((subtask) => subtask.status === 'completed').length ?? 0

  const topbar = (
    <div className="flex min-w-0 items-center gap-3">
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-semibold">
          {contract?.task.objective ?? 'Nova execução'}
        </div>
        <div className="mt-0.5 flex items-center gap-2 text-[11px] text-muted-foreground">
          <span>{contract ? workflowLabel(contract.decision_metadata.selected_workflow) : 'Defina um objetivo para iniciar'}</span>
          {contract && <><span>·</span><span>{formatDuration(contract.metrics.duration_ms)}</span></>}
        </div>
      </div>
      {contract && <Badge variant={contract.task.status === 'completed' ? 'published' : 'draft'}>{humanizeStatus(contract.task.status)}</Badge>}
      <ThemeToggle theme={theme} onToggle={toggle} />
    </div>
  )

  const composer = (
    <ExecutionComposer
      objective={objective}
      workflow={workflow}
      loading={loading}
      onObjectiveChange={setObjective}
      onWorkflowChange={setWorkflow}
      onRun={handleRun}
      onDemo={handleDemo}
    />
  )

  return (
    <AppShell contract={contract} onNewExecution={handleNewExecution} topbar={topbar} composer={composer}>
      <div className="mx-auto w-full max-w-5xl px-3 py-4 sm:px-6 sm:py-6 lg:px-8">
        <div className="sr-only" role="status" aria-live="polite">
          {loading ? 'Execução em andamento' : contract ? `Execução ${humanizeStatus(contract.task.status)}` : ''}
        </div>
        {error && (
          <div role="alert" className="mb-5 flex items-start gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
            <AlertTriangle className="mt-0.5 size-4 shrink-0" />
            <div className="min-w-0 flex-1"><div className="font-semibold">Não foi possível concluir a execução</div><div className="mt-1 break-words opacity-80">{error}</div></div>
            <Button variant="outline" size="sm" onClick={retry} disabled={loading} className="shrink-0 border-destructive/30">
              <RefreshCw className={`size-3.5 ${loading ? 'animate-spin' : ''}`} />
              Tentar novamente
            </Button>
          </div>
        )}

        {loading && contract && (
          <div role="status" className="mb-5 flex items-center gap-3 rounded-xl border border-primary/20 bg-primary/5 px-4 py-3 text-sm text-primary">
            <Bot className="size-4 animate-pulse" />
            Atualizando a execução com uma nova solicitação…
          </div>
        )}

        {!contract && !loading ? (
          <section className="flex min-h-[55vh] flex-col items-center justify-center text-center">
            <div className="mb-5 flex size-16 items-center justify-center rounded-2xl bg-primary/10 text-primary">
              <Network className="size-8" />
            </div>
            <Badge variant="outline" className="mb-4"><Sparkles className="mr-1 size-3" />Workspace de execução</Badge>
            <h1 className="max-w-xl text-2xl font-semibold tracking-tight sm:text-3xl">Estude como agentes colaboram para resolver objetivos complexos</h1>
            <p className="mt-3 max-w-xl text-sm leading-6 text-muted-foreground">
              Acompanhe decisões de roteamento, dependências, avaliações, ferramentas, métricas e artefatos em uma única execução observável.
            </p>
            <div className="mt-7 grid w-full max-w-2xl gap-3 sm:grid-cols-3">
              {[
                ['Agentes', 'Papéis e contribuições individuais'],
                ['Orquestração', 'Timeline, iterações e DAG'],
                ['Evidências', 'Métricas, contexto e artefatos'],
              ].map(([title, description]) => (
                <div key={title} className="surface-panel p-4 text-left">
                  <div className="text-sm font-semibold">{title}</div>
                  <div className="mt-1 text-xs leading-5 text-muted-foreground">{description}</div>
                </div>
              ))}
            </div>
          </section>
        ) : loading && !contract ? (
          <section className="flex min-h-[55vh] flex-col items-center justify-center text-center">
            <div className="relative mb-5 flex size-16 items-center justify-center rounded-2xl bg-primary/10 text-primary">
              <Bot className="size-7" />
              <span className="absolute inset-0 animate-ping rounded-2xl border border-primary/30" />
            </div>
            <h1 className="text-xl font-semibold">Preparando a equipe de agentes</h1>
            <p className="mt-2 text-sm text-muted-foreground">O orquestrador está analisando o objetivo e selecionando o workflow.</p>
          </section>
        ) : contract ? (
          <div className="space-y-5">
            <section className="rounded-2xl bg-secondary/70 p-5">
              <div className="section-label mb-2">Objetivo</div>
              <p className="text-sm leading-6 text-foreground">{contract.task.objective}</p>
            </section>

            <section className="surface-panel overflow-hidden">
              <div className="flex flex-wrap items-center gap-4 border-b border-border px-5 py-4">
                <div className="min-w-0 flex-1">
                  <h1 className="truncate text-base font-semibold">Execução do orquestrador</h1>
                  <div className="mt-1 flex flex-wrap gap-3 text-xs text-muted-foreground">
                    <span className="flex items-center gap-1"><Clock3 className="size-3.5" />{formatDuration(contract.metrics.duration_ms)}</span>
                    <span>{completedSubtasks} de {contract.subtasks.length} subtarefas concluídas</span>
                    <span>{contract.progressive_agent_responses.length} respostas de agentes</span>
                  </div>
                </div>
                <Badge variant="published">{humanizeStatus(contract.task.status)}</Badge>
              </div>
              <div className="h-1 bg-secondary">
                <div className="h-full bg-emerald-500" style={{ width: `${contract.subtasks.length ? (completedSubtasks / contract.subtasks.length) * 100 : 0}%` }} />
              </div>
            </section>

            <ExecutionViews contract={contract} />
            <FinalResponsePanel response={contract.task.final_response} />

            <section className="surface-panel overflow-hidden">
              <button type="button" aria-expanded={automationsOpen} aria-controls="automations-panel" className="focus-ring flex w-full items-center gap-3 px-4 py-3 text-left" onClick={() => setAutomationsOpen((open) => !open)}>
                <Clock3 className="size-4 text-muted-foreground" />
                <div><div className="text-sm font-semibold">Automações e gatilhos</div><div className="text-[11px] text-muted-foreground">Webhook, execução manual e agendamento</div></div>
                <ChevronDown className={`ml-auto size-4 transition-transform ${automationsOpen ? 'rotate-180' : ''}`} />
              </button>
              {automationsOpen && <div id="automations-panel" className="border-t border-border p-3"><EventLoopPanel /></div>}
            </section>
          </div>
        ) : null}
      </div>
    </AppShell>
  )
}
