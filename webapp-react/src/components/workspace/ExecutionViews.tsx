import { Activity, ListTree, MessagesSquare, Network } from 'lucide-react'
import { ActivityTimeline } from './ActivityTimeline'
import { OperationalEventLog } from './event-log/OperationalEventLog'
import { ProgressivePanel } from '@/components/progressive/ProgressivePanel'
import { cn } from '@/lib/utils'
import type { ExecutionContractDTO } from '@/types/contract'
import { useStoredState } from '@/hooks/useStoredState'
import { useEffect } from 'react'
import type { HumanInteractionProps } from '@/components/progressive/HumanRequestMessage'

type ExecutionView = 'timeline' | 'chat' | 'dag' | 'event-log'

const VIEWS = [
  { id: 'timeline' as const, label: 'Timeline', icon: Activity },
  { id: 'chat' as const, label: 'Chat', icon: MessagesSquare },
  { id: 'dag' as const, label: 'DAG', icon: Network },
  { id: 'event-log' as const, label: 'Event Log', icon: ListTree },
]

export function ExecutionViews({ contract, ...humanProps }: { contract: ExecutionContractDTO } & HumanInteractionProps) {
  const [view, setView] = useStoredState<ExecutionView>('adk-execution-view', 'timeline')
  const hasResponses = contract.progressive_agent_responses.length > 0 || !!contract.human_requests?.length
  const pendingId = contract.human_requests?.find(item => item.status === 'pending')?.request_id
  useEffect(() => { if (pendingId) setView('chat') }, [pendingId, setView])

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
            disabled={!hasResponses && id !== 'timeline' && id !== 'event-log'}
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
        {view === 'chat' && <ProgressivePanel responses={contract.progressive_agent_responses} forcedView="chat" showViewToggle={false}
          humanRequests={contract.human_requests} {...humanProps} />}
        {view === 'dag' && <ProgressivePanel responses={contract.progressive_agent_responses} forcedView="dag" showViewToggle={false} />}
        {view === 'event-log' && <OperationalEventLog events={contract.events} />}
      </div>
    </section>
  )
}
