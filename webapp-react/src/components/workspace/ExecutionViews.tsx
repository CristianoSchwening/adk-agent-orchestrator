import { Activity, MessagesSquare, Network } from 'lucide-react'
import { ActivityTimeline } from './ActivityTimeline'
import { ProgressivePanel } from '@/components/progressive/ProgressivePanel'
import { cn } from '@/lib/utils'
import type { ExecutionContractDTO } from '@/types/contract'
import { useStoredState } from '@/hooks/useStoredState'

type ExecutionView = 'timeline' | 'chat' | 'dag'

const VIEWS = [
  { id: 'timeline' as const, label: 'Timeline', icon: Activity },
  { id: 'chat' as const, label: 'Chat', icon: MessagesSquare },
  { id: 'dag' as const, label: 'DAG', icon: Network },
]

export function ExecutionViews({ contract }: { contract: ExecutionContractDTO }) {
  const [view, setView] = useStoredState<ExecutionView>('adk-execution-view', 'timeline')
  const hasResponses = contract.progressive_agent_responses.length > 0

  return (
    <section className="surface-panel overflow-hidden">
      <div className="flex items-center gap-1 overflow-x-auto border-b border-border px-3 py-2" role="tablist" aria-label="Visualizacoes da execucao">
        {VIEWS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={view === id}
            aria-controls={`execution-view-${id}`}
            disabled={!hasResponses && id !== 'timeline'}
            onClick={() => setView(id)}
            className={cn(
              'focus-ring flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40',
              view === id ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:bg-secondary hover:text-foreground',
            )}
          >
            <Icon className="size-3.5" />
            {label}
          </button>
        ))}
        <span className="ml-auto whitespace-nowrap pr-2 text-[10px] text-muted-foreground">
          {contract.events.length} eventos · {contract.progressive_agent_responses.length} respostas
        </span>
      </div>

      <div id={`execution-view-${view}`} role="tabpanel">
        {view === 'timeline' && <ActivityTimeline events={contract.events} responses={contract.progressive_agent_responses} />}
        {view === 'chat' && <ProgressivePanel responses={contract.progressive_agent_responses} forcedView="chat" showViewToggle={false} />}
        {view === 'dag' && <ProgressivePanel responses={contract.progressive_agent_responses} forcedView="dag" showViewToggle={false} />}
      </div>
    </section>
  )
}
