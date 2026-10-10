import { ArrowUp, FlaskConical, Loader2, Paperclip, Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface ExecutionComposerProps {
  objective: string
  loading: boolean
  useKev: boolean
  onObjectiveChange: (value: string) => void
  onUseKevChange: (value: boolean) => void
  onRun: () => void
  onDemo: () => void
}

export function ExecutionComposer({
  objective,
  loading,
  useKev,
  onObjectiveChange,
  onUseKevChange,
  onRun,
  onDemo,
}: ExecutionComposerProps) {
  return (
    <div className="safe-bottom mx-auto w-full max-w-4xl px-3 sm:px-4">
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
          aria-label="Objetivo da execução"
          className="focus-ring w-full resize-none rounded-xl bg-transparent px-3 py-2 text-sm leading-6 placeholder:text-muted-foreground"
        />
        <div className="flex flex-wrap items-center gap-2 border-t border-border px-1 pt-2 sm:px-2">
          <Button variant="ghost" size="icon" aria-label="Anexar contexto" title="Anexos serão habilitados em uma próxima etapa">
            <Paperclip className="size-4" />
          </Button>
          <label className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-xs text-muted-foreground hover:bg-secondary" title="Envia o título, a descrição e as capacidades da tarefa ao Kev para escolher o especialista.">
            <Sparkles className={`size-3.5 ${useKev ? 'text-primary' : ''}`} />
            <span>Usar Kev</span>
            <input
              type="checkbox"
              checked={useKev}
              onChange={(event) => onUseKevChange(event.target.checked)}
              disabled={loading}
              aria-label="Usar Kev para escolher especialistas"
              className="size-3.5 accent-primary"
            />
          </label>
          <Button variant="ghost" size="sm" onClick={onDemo} disabled={loading} className="ml-auto px-2 sm:px-3">
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
