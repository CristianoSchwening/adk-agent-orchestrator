import { Menu, PanelRight, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { NavigationSidebar } from './NavigationSidebar'
import { ExecutionInspector } from './ExecutionInspector'
import type { ExecutionContractDTO } from '@/types/contract'

interface AppShellProps {
  contract: ExecutionContractDTO | null
  onNewExecution: () => void
  topbar: React.ReactNode
  children: React.ReactNode
  composer: React.ReactNode
}

export function AppShell({ contract, onNewExecution, topbar, children, composer }: AppShellProps) {
  const [navigationOpen, setNavigationOpen] = useState(false)
  const [inspectorOpen, setInspectorOpen] = useState(false)
  const navigationDialogRef = useRef<HTMLDivElement>(null)
  const inspectorDialogRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!navigationOpen && !inspectorOpen) return

    const dialog = navigationOpen ? navigationDialogRef.current : inspectorDialogRef.current
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
    dialog?.focus()
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setNavigationOpen(false)
        setInspectorOpen(false)
        return
      }
      if (event.key !== 'Tab' || !dialog) return
      const focusable = Array.from(dialog.querySelectorAll<HTMLElement>(
        'button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      ))
      if (!focusable.length) {
        event.preventDefault()
        dialog.focus()
        return
      }
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      document.body.style.overflow = ''
      previousFocus?.focus()
    }
  }, [navigationOpen, inspectorOpen])

  return (
    <div className="h-dvh overflow-hidden bg-background text-foreground">
      <div className="grid h-full min-h-0 lg:grid-cols-[224px_minmax(0,1fr)] 2xl:grid-cols-[224px_minmax(0,1fr)_336px]">
        <NavigationSidebar contract={contract} onNewExecution={onNewExecution} className="hidden lg:flex" />

        {navigationOpen && (
          <div className="fixed inset-0 z-50 flex lg:hidden">
            <button type="button" tabIndex={-1} className="absolute inset-0 bg-black/30" onClick={() => setNavigationOpen(false)} aria-label="Fechar navegação" />
            <div ref={navigationDialogRef} role="dialog" aria-modal="true" aria-label="Navegação" tabIndex={-1} className="relative w-[280px] max-w-[85vw] outline-none">
              <NavigationSidebar contract={contract} onNewExecution={() => { onNewExecution(); setNavigationOpen(false) }} />
              <Button variant="ghost" size="icon" className="absolute right-2 top-2" onClick={() => setNavigationOpen(false)}><X className="size-4" /></Button>
            </div>
          </div>
        )}

        <div className="flex min-h-0 min-w-0 flex-col bg-card">
          <div className="flex h-16 shrink-0 items-center border-b border-border px-3 sm:px-5">
            <Button variant="ghost" size="icon" className="mr-2 lg:hidden" onClick={() => setNavigationOpen(true)} aria-label="Abrir navegação"><Menu className="size-5" /></Button>
            <div className="min-w-0 flex-1">{topbar}</div>
            <Button variant="ghost" size="icon" className="2xl:hidden" onClick={() => setInspectorOpen(true)} aria-label="Abrir painel de orquestração"><PanelRight className="size-5" /></Button>
          </div>
          <main className="min-h-0 flex-1 overflow-y-auto bg-card">{children}</main>
          <div className="shrink-0 bg-gradient-to-t from-card via-card to-transparent pt-3">{composer}</div>
        </div>

        <div className="hidden min-h-0 2xl:block">
          <ExecutionInspector contract={contract} />
        </div>

        {inspectorOpen && (
          <div className="fixed inset-0 z-50 flex justify-end 2xl:hidden">
            <button type="button" tabIndex={-1} className="absolute inset-0 bg-black/30" onClick={() => setInspectorOpen(false)} aria-label="Fechar painel" />
            <div ref={inspectorDialogRef} role="dialog" aria-modal="true" aria-label="Painel de orquestração" tabIndex={-1} className="relative h-full w-[360px] max-w-[92vw] bg-background outline-none">
              <ExecutionInspector contract={contract} />
              <Button variant="ghost" size="icon" className="absolute right-2 top-2" onClick={() => setInspectorOpen(false)}><X className="size-4" /></Button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
