import { Check, Clipboard, FileCheck2 } from 'lucide-react'
import { useState } from 'react'
import { Button } from '@/components/ui/button'

interface FinalResponsePanelProps {
  response: string | null
}

export function FinalResponsePanel({ response }: FinalResponsePanelProps) {
  const [copied, setCopied] = useState(false)
  if (!response) return null

  const copy = async () => {
    await navigator.clipboard.writeText(response)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1800)
  }

  return (
    <section className="surface-panel overflow-hidden">
      <div className="flex items-center gap-3 border-b border-border px-5 py-4">
        <span className="flex size-8 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-600">
          <FileCheck2 className="size-4" />
        </span>
        <div>
          <h2 className="text-sm font-semibold">Resposta consolidada</h2>
          <p className="text-[11px] text-muted-foreground">Resultado final publicado pelo orquestrador</p>
        </div>
        <Button variant="ghost" size="sm" className="ml-auto" onClick={copy}>
          {copied ? <Check className="size-4 text-emerald-500" /> : <Clipboard className="size-4" />}
          {copied ? 'Copiada' : 'Copiar'}
        </Button>
      </div>
      <div className="prose-response whitespace-pre-wrap px-6 py-5 text-sm leading-7 text-foreground/90">{response}</div>
    </section>
  )
}
