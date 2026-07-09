import { cn } from '@/lib/utils'
import type { AgentVisibleResponse } from '@/types/contract'

interface CriterionRow {
  criterion: string
  score: number
  passed: boolean
  feedback: string
}

interface GraderMessageProps {
  response: AgentVisibleResponse
}

export function GraderMessage({ response: r }: GraderMessageProps) {
  const meta       = r.metadata as Record<string, unknown>
  const passed     = meta.passed as boolean
  const score      = meta.overall_score as number | undefined
  const threshold  = meta.threshold as number | undefined
  const scores     = meta.criterion_scores as Record<string, number> | undefined
  const borderColor = passed ? 'border-green-500/40' : 'border-red-500/40'
  const bgColor     = passed ? 'bg-green-500/5'      : 'bg-red-500/5'
  const icon        = passed ? '✅' : '❌'
  const label       = passed ? 'RUBRIC PASSED' : 'RUBRIC FAILED — RETRY'

  // Parse criterion rows from content (fallback: build from scores map)
  const lines  = r.content.split('\n')
  const header = lines[0] ?? ''

  const criteriaRows: CriterionRow[] = []
  if (scores) {
    for (const [criterion, s] of Object.entries(scores)) {
      const psd = threshold !== undefined ? s >= threshold : s >= 0.70
      criteriaRows.push({
        criterion,
        score: s,
        passed: psd,
        feedback: lines.find(l => l.includes(criterion))?.replace(/^[✅❌]\s*\S+:\s*\d+%\s*—?\s*/, '') ?? '',
      })
    }
  }

  return (
    <div className={cn('w-full rounded-xl border', borderColor, bgColor, 'px-4 py-3 my-1')}>
      {/* Header row */}
      <div className="flex items-center gap-2 mb-2">
        <span className="text-base">{icon}</span>
        <span className={cn(
          'text-[11px] font-bold uppercase tracking-widest',
          passed ? 'text-green-400' : 'text-red-400',
        )}>
          {label}
        </span>
        {score !== undefined && (
          <span className={cn(
            'ml-auto text-[11px] font-semibold px-2 py-0.5 rounded-full border',
            passed
              ? 'border-green-500/30 bg-green-500/10 text-green-400'
              : 'border-red-500/30   bg-red-500/10   text-red-400',
          )}>
            {(score * 100).toFixed(0)}% {threshold !== undefined ? `≥ ${(threshold * 100).toFixed(0)}%` : ''}
          </span>
        )}
        <span className="text-[10px] text-muted-foreground ml-1">rubric_grader · internal</span>
      </div>

      {/* Overall feedback */}
      <p className="text-xs text-foreground/80 leading-relaxed mb-2">{header}</p>

      {/* Criterion table */}
      {criteriaRows.length > 0 && (
        <div className="grid grid-cols-1 gap-0.5">
          {criteriaRows.map(row => (
            <div
              key={row.criterion}
              className={cn(
                'flex items-center gap-2 px-2 py-1 rounded-md text-[11px]',
                row.passed ? 'bg-green-500/5' : 'bg-red-500/5',
              )}
            >
              <span>{row.passed ? '✅' : '❌'}</span>
              <span className="font-semibold w-24 flex-shrink-0 capitalize">{row.criterion}</span>
              <span className={cn(
                'font-bold w-10 flex-shrink-0',
                row.passed ? 'text-green-400' : 'text-red-400',
              )}>
                {(row.score * 100).toFixed(0)}%
              </span>
              {row.feedback && (
                <span className="text-muted-foreground truncate">{row.feedback}</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
