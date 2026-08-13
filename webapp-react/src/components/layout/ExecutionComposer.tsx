import { ArrowUp, FlaskConical, Loader2, Paperclip } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { WORKFLOW_OPTIONS } from '@/config/workflows'

interface ExecutionComposerProps {
  objective: string
  workflow: string
  loading: boolean
  onObjectiveChange: (value: string) => void
  onWorkflowChange: (value: string) => void
  onRun: () => void
  onDemo: () => void
}

export function ExecutionComposer({
  objective,
  workflow,
  loading,
  onObjectiveChange,
  onWorkflowChange,
  onRun,
  onDemo,
}: ExecutionComposerProps) {
  return (
    <div className="mx-auto w-full max-w-4xl px-4 pb-4">
      <div className="rounded-2xl border border-border bg-card p-2 shadow-[0_12px_36px_rgba(15,23,42,0.12)]">
        <textarea
          value={objective}
          onChange={(event) => onObjectiveChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault()
              if (objective.trim() && !loading) onRun()
            }
          }}
          placeholder="Descreva o objetivo para a equipe de agentes…"
          rows={3}
          className="focus-ring w-full resize-none rounded-xl bg-transparent px-3 py-2 text-sm leading-6 placeholder:text-muted-foreground"
        />
        <div className="flex flex-wrap items-center gap-2 border-t border-border px-2 pt-2">
          <Button variant="ghost" size="icon" aria-label="Anexar contexto" title="Anexos serão habilitados em uma próxima etapa">
            <Paperclip className="size-4" />
          </Button>
          <select
            value={workflow}
            onChange={(event) => onWorkflowChange(event.target.value)}
            className="focus-ring h-8 max-w-[220px] rounded-lg border border-border bg-secondary px-2 text-xs"
            aria-label="Workflow"
          >
            {WORKFLOW_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
          <Button variant="ghost" size="sm" onClick={onDemo} disabled={loading} className="ml-auto">
            <FlaskConical className="size-4" />
            Carregar demo
          </Button>
          <Button size="icon" onClick={onRun} disabled={loading || !objective.trim()} aria-label="Iniciar execução">
            {loading ? <Loader2 className="size-4 animate-spin" /> : <ArrowUp className="size-4" />}
          </Button>
        </div>
      </div>
    </div>
  )
}
