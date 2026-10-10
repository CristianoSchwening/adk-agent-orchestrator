import { useState } from 'react'
import { Button } from '@/components/ui/button'
import type { HumanDecision, HumanRequest } from '@/types/contract'
import { readStoredValue, writeStoredValue } from '@/lib/storage'

export const decisionLabels: Record<HumanDecision, string> = {
  approved: 'Aprovar', rejected: 'Rejeitar', needs_changes: 'Solicitar alterações',
  clarification: 'Enviar resposta',
}

export interface HumanInteractionProps {
  humanRequests?: HumanRequest[]
  sending?: boolean
  responseError?: string | null
  onHumanResponse?: (requestId: string, decision: HumanDecision, comment: string,
                     key: string) => Promise<boolean>
}

export function HumanRequestMessage({ request, sending, responseError, onHumanResponse }: {
  request: HumanRequest
} & HumanInteractionProps) {
  const draftKey = `adk-human-draft-${request.request_id}`
  const [comment, setComment] = useState(() => readStoredValue(draftKey) ?? '')
  const [validation, setValidation] = useState<string | null>(null)
  const pending = request.status === 'pending'
  const send = async (decision: HumanDecision) => {
    const text = comment.trim()
    if (decision !== 'approved' && !text) {
      setValidation('Escreva sua resposta ou o motivo da decisão.')
      return
    }
    setValidation(null)
    const ok = await onHumanResponse?.(request.request_id, decision, text, request.request_id)
    if (ok) { setComment(''); writeStoredValue(draftKey, null) }
  }

  return (
    <article className="space-y-3" aria-label="Interação com você">
      <div className="rounded-xl border border-primary/25 bg-primary/5 p-4">
        <div className="mb-2 text-xs font-semibold">Orquestrador · {pending ? 'Aguardando sua resposta' : 'Solicitação respondida'}</div>
        <p className="text-sm font-medium">{request.message}</p>
        <p className="mt-3 whitespace-pre-wrap break-words text-sm leading-6">{request.candidate}</p>
        {request.criteria.length > 0 && <ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-muted-foreground">
          {request.criteria.map((criterion, index) => <li key={index}>{criterion}</li>)}
        </ul>}
      </div>
      {pending ? (
        <div className="ml-4 rounded-xl border border-border bg-background p-3">
          <label htmlFor={`human-${request.request_id}`} className="mb-2 block text-xs font-semibold">Sua resposta</label>
          <textarea id={`human-${request.request_id}`} value={comment} onChange={e => {
            setComment(e.target.value); writeStoredValue(draftKey, e.target.value)
          }}
            disabled={sending} rows={3} placeholder={request.kind === 'approval' ? 'Comentário ou alterações desejadas…' : 'Escreva a informação solicitada…'}
            className="focus-ring w-full resize-y rounded-lg border border-border bg-background p-3 text-sm"
            aria-describedby={(validation || responseError) ? `error-${request.request_id}` : undefined} />
          {(validation || responseError) && <p id={`error-${request.request_id}`} role="alert" className="mt-2 text-sm text-destructive">{validation || responseError}</p>}
          <div className="mt-3 flex flex-wrap gap-2">
            {(request.kind === 'approval' ? ['approved', 'needs_changes', 'rejected'] as const : ['clarification'] as const).map(decision => (
              <Button key={decision} variant={decision === 'approved' ? 'default' : 'outline'} disabled={sending || !onHumanResponse}
                onClick={() => void send(decision)}>{decisionLabels[decision]}</Button>
            ))}
          </div>
          {sending && <p role="status" className="mt-2 text-xs text-muted-foreground">Enviando sua resposta e retomando a execução…</p>}
        </div>
      ) : request.response && (
        <div className="ml-8 rounded-xl bg-secondary p-4 text-sm">
          <div className="mb-2 text-xs font-semibold">Você · {{ approved: 'Aprovado', rejected: 'Rejeitado', needs_changes: 'Alterações solicitadas', clarification: 'Resposta enviada' }[request.response.decision]}</div>
          <p className="whitespace-pre-wrap break-words">{request.response.comment || 'Aprovo esta proposta.'}</p>
        </div>
      )}
    </article>
  )
}
