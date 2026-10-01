import { formatTime, humanizeStatus } from '@/lib/format'
import type { ExecutionContractDTO, TaskRunDTO } from '@/types/contract'

const criterionLabels = { passed: 'Aprovado', failed: 'Reprovado', unverifiable: 'Não verificável' }
const outputLabels = {
  not_recorded: 'Conteúdo não registrado', absent: 'Saída ausente',
  empty: 'Saída vazia', present: 'Conteúdo produzido',
}

function failureLabel(task: TaskRunDTO) {
  if (task.error === 'evaluation_failed' || task.evaluation_error) return 'Erro do avaliador'
  if (task.error === 'replan:acceptance_criteria_failed') return 'Conteúdo reprovado'
  if (task.error?.startsWith('replan:')) return 'Replanejamento solicitado'
  if (task.error) return 'Falha de execução'
  return humanizeStatus(task.status)
}

function TaskDiagnostic({ task, title }: { task: TaskRunDTO; title?: string }) {
  const evaluation = task.evaluation
  const catalog = new Map(evaluation?.criteria_catalog.map(item => [item.criterion_id, item.text]) ?? [])
  const outputStatus = task.output_status ?? 'not_recorded'
  return <div className="min-w-0 space-y-2 rounded-lg bg-secondary/60 p-3 text-xs">
    <div className="font-medium break-words">{title ?? task.task_id}</div>
    <p className={task.status === 'failed' ? 'text-destructive' : 'text-muted-foreground'}>
      {failureLabel(task)} · tentativa {task.attempt} · {formatTime(task.updated_at)}
    </p>
    {task.error && <p className="break-words text-muted-foreground">{task.error}</p>}
    {task.evaluation_error && <p className="whitespace-pre-wrap break-words">{task.evaluation_error}</p>}
    {evaluation ? <>
      <p className="whitespace-pre-wrap break-words">{evaluation.rationale}</p>
      <p className="text-muted-foreground">Avaliado às {formatTime(task.evaluated_at)}</p>
      <ul className="space-y-2" aria-label="Avaliação por critério">
        {evaluation.criteria.map(criterion => <li key={criterion.criterion_id} className="space-y-1 border-l-2 border-border pl-2">
          <p className="font-medium break-words">{catalog.get(criterion.criterion_id) ?? criterion.criterion_id}</p>
          <p className={criterion.status === 'passed' ? 'text-emerald-600' : 'text-destructive'}>{criterionLabels[criterion.status]}</p>
          <p className="whitespace-pre-wrap break-words">{criterion.rationale}</p>
          <blockquote className="whitespace-pre-wrap break-words text-muted-foreground">Evidência: {criterion.evidence}</blockquote>
        </li>)}
      </ul>
    </> : <p className="text-muted-foreground">{task.evaluation_error ? 'Avaliação não concluída.' : 'Diagnóstico não registrado.'}</p>}
    <p className="text-muted-foreground">{outputLabels[outputStatus]}</p>
    {outputStatus !== 'not_recorded' && <details>
      <summary className="focus-ring cursor-pointer rounded py-1 font-medium">Ver conteúdo produzido</summary>
      <pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap break-words rounded border border-border p-2 text-[11px]">
        {typeof task.execution_output === 'string' ? task.execution_output : JSON.stringify(task.execution_output, null, 2) ?? 'Saída ausente'}
      </pre>
    </details>}
  </div>
}

export function RunDiagnostics({ contract }: { contract: ExecutionContractDTO }) {
  const runs = [...(contract.task_run_history ?? []), ...(contract.task_run ? [contract.task_run] : [])]
    .filter((run, index, all) => all.findIndex(other => other.run_id === run.run_id) === index)
  const plans = [...(contract.task_plan_history ?? []), ...(contract.task_plan ? [contract.task_plan] : [])]
  if (!runs.length) return <p className="text-xs text-muted-foreground">Nenhuma tentativa registrada.</p>
  return <div className="space-y-3">
    {runs.map((run, index) => {
      const plan = plans.find(item => item.plan_id === run.plan_id)
      return <details key={run.run_id} open={run.run_id === contract.task_run?.run_id} className="rounded-lg border border-border p-2">
        <summary className="focus-ring cursor-pointer rounded text-xs font-semibold">
          {plan ? `Revisão ${plan.revision}` : `Execução ${index + 1}`} · {humanizeStatus(run.status)}
        </summary>
        <div className="mt-3 space-y-3">
          <p className="break-all text-[10px] text-muted-foreground">{run.run_id}</p>
          {run.terminal_error?.code === 'replan_limit_exhausted' && <p role="status" className="rounded border border-destructive p-2 text-xs text-destructive">
            Limite de replanejamento esgotado: {run.terminal_error.used} de {run.terminal_error.limit} revisões utilizadas. A última reprovação está preservada abaixo.
          </p>}
          {run.replan_request && <p className="whitespace-pre-wrap break-words text-xs"><strong>Motivo do replanejamento: </strong>{run.replan_request.rationale}</p>}
          {run.tasks.map(task => <TaskDiagnostic key={task.task_id} task={task} title={plan?.tasks.find(item => item.task_id === task.task_id)?.title} />)}
        </div>
      </details>
    })}
  </div>
}
