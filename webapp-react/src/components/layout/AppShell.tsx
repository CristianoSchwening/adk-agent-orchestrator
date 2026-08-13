import { Menu, PanelRight, X } from 'lucide-react'
import { useState } from 'react'
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

  return (
    <div className="h-dvh overflow-hidden bg-background text-foreground">
      <div className="grid h-full min-h-0 lg:grid-cols-[224px_minmax(0,1fr)] 2xl:grid-cols-[224px_minmax(0,1fr)_336px]">
        <NavigationSidebar contract={contract} onNewExecution={onNewExecution} className="hidden lg:flex" />

        {navigationOpen && (
          <div className="fixed inset-0 z-50 flex lg:hidden">
            <button className="absolute inset-0 bg-black/30" onClick={() => setNavigationOpen(false)} aria-label="Fechar navegação" />
            <div className="relative w-[280px] max-w-[85vw]">
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
            <button className="absolute inset-0 bg-black/30" onClick={() => setInspectorOpen(false)} aria-label="Fechar painel" />
            <div className="relative h-full w-[360px] max-w-[92vw] bg-background">
              <ExecutionInspector contract={contract} />
              <Button variant="ghost" size="icon" className="absolute right-2 top-2" onClick={() => setInspectorOpen(false)}><X className="size-4" /></Button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
