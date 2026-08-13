import {
  Bot,
  Boxes,
  Clock3,
  FileStack,
  History,
  Plus,
  RadioTower,
  Workflow,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { ExecutionContractDTO } from '@/types/contract'

const NAVIGATION = [
  { label: 'Execuções', icon: History, active: true },
  { label: 'Workflows', icon: Workflow },
  { label: 'Agentes', icon: Bot },
  { label: 'Contexto', icon: FileStack },
  { label: 'Agendamentos', icon: Clock3 },
  { label: 'Webhooks', icon: RadioTower },
]

interface NavigationSidebarProps {
  contract: ExecutionContractDTO | null
  onNewExecution: () => void
  className?: string
}

export function NavigationSidebar({ contract, onNewExecution, className }: NavigationSidebarProps) {
  return (
    <aside className={cn('flex h-full min-h-0 flex-col border-r border-border bg-card', className)}>
      <div className="flex h-16 items-center gap-3 border-b border-border px-4">
        <div className="flex size-9 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm">
          <Boxes className="size-5" />
        </div>
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold">ADK Orchestrator</div>
          <div className="text-[11px] text-muted-foreground">Execution Workspace</div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-3">
        <Button className="mb-5 w-full justify-start" onClick={onNewExecution}>
          <Plus className="size-4" />
          Nova execução
        </Button>

        <div className="section-label mb-2 px-2">Workspace</div>
        <nav className="space-y-1" aria-label="Navegação principal">
          {NAVIGATION.map(({ label, icon: Icon, active }) => (
            <button
              key={label}
              type="button"
              className={cn(
                'focus-ring flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm transition-colors',
                active
                  ? 'bg-primary/10 font-medium text-primary'
                  : 'text-muted-foreground hover:bg-secondary hover:text-foreground',
              )}
            >
              <Icon className="size-4" />
              {label}
            </button>
          ))}
        </nav>

        <div className="mt-7">
          <div className="section-label mb-2 px-2">Execuções recentes</div>
          {contract ? (
            <button className="focus-ring w-full rounded-xl border border-primary/20 bg-primary/5 p-3 text-left">
              <div className="flex items-start gap-2">
                <span className="mt-1 size-2 shrink-0 rounded-full bg-emerald-500" />
                <div className="min-w-0">
                  <div className="line-clamp-2 text-xs font-medium leading-5">{contract.task.objective}</div>
                  <div className="mt-1 text-[10px] text-muted-foreground">Execução atual</div>
                </div>
              </div>
            </button>
          ) : (
            <div className="rounded-xl border border-dashed border-border p-3 text-xs leading-5 text-muted-foreground">
              As execuções carregadas nesta sessão aparecerão aqui.
            </div>
          )}
        </div>
      </div>

      <div className="border-t border-border px-4 py-3 text-[11px] text-muted-foreground">
        Contrato orchestrator.execution.v1
      </div>
    </aside>
  )
}
