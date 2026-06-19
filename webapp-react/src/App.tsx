import { CheckCircle2, Circle, ArrowLeft, Box } from 'lucide-react'
import { cn } from '@/lib/utils'

const STACK = [
  { label: 'React',       version: '18.3',  status: 'ready', icon: '⚛️'  },
  { label: 'TypeScript',  version: '5.6',   status: 'ready', icon: '🔷'  },
  { label: 'Vite',        version: '5.4',   status: 'ready', icon: '⚡'  },
  { label: 'Tailwind',    version: '3.4',   status: 'ready', icon: '🎨'  },
  { label: 'shadcn/ui',   version: 'ready', status: 'ready', icon: '🧩'  },
  { label: 'AI Elements', version: 'next',  status: 'next',  icon: '🤖'  },
]

const STAGES = [
  { n: 0, label: 'Foundation',             status: 'done',    desc: 'React + Vite + Tailwind + shadcn/ui' },
  { n: 1, label: 'Progressive Responses',  status: 'pending', desc: 'AI Elements Message + DAG hover cards' },
  { n: 2, label: 'Event Log',              status: 'pending', desc: 'AI Elements Tool components' },
  { n: 3, label: 'Artifacts panel',        status: 'pending', desc: 'AI Elements Attachments' },
  { n: 4, label: 'Input bar',              status: 'pending', desc: 'AI Elements PromptInput' },
  { n: 5, label: 'Full shell migration',   status: 'pending', desc: 'shadcn layout + decommission HTML' },
]

export default function App() {
  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col">

      {/* Header */}
      <header className="border-b border-border px-6 h-14 flex items-center justify-between sticky top-0 bg-card z-50">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-purple-500 flex items-center justify-center text-base">🤖</div>
          <div>
            <div className="text-sm font-bold">ADK Orchestrator</div>
            <div className="text-[11px] text-muted-foreground">React — Stage 0</div>
          </div>
        </div>
        <a
          href="/"
          className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Back to current app
        </a>
      </header>

      <main className="flex-1 max-w-3xl mx-auto w-full px-6 py-12 flex flex-col gap-8">

        {/* Hero */}
        <div className="text-center flex flex-col items-center gap-4">
          <div className="w-16 h-16 rounded-2xl bg-primary/10 border border-primary/30 flex items-center justify-center text-3xl">
            ✅
          </div>
          <div>
            <h1 className="text-2xl font-bold mb-2">Estágio 0 — Fundação pronta</h1>
            <p className="text-muted-foreground text-sm leading-relaxed max-w-md">
              Pipeline React + Vite configurado e servido pelo FastAPI em{' '}
              <code className="text-primary bg-primary/10 px-1.5 py-0.5 rounded text-xs">/app</code>.
              O app vanilla HTML original continua intacto em{' '}
              <code className="text-primary bg-primary/10 px-1.5 py-0.5 rounded text-xs">/</code>.
            </p>
          </div>
        </div>

        {/* Stack cards */}
        <section>
          <h2 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-3">
            Stack instalada
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {STACK.map(s => (
              <div
                key={s.label}
                className={cn(
                  'rounded-xl border p-4 flex items-center gap-3 transition-colors',
                  s.status === 'ready'
                    ? 'border-border bg-card'
                    : 'border-dashed border-border/50 bg-card/50 opacity-60',
                )}
              >
                <span className="text-xl">{s.icon}</span>
                <div className="min-w-0">
                  <div className="text-sm font-semibold truncate">{s.label}</div>
                  <div className="text-[11px] text-muted-foreground">v{s.version}</div>
                </div>
                {s.status === 'ready' ? (
                  <CheckCircle2 className="w-4 h-4 text-green-500 ml-auto flex-shrink-0" />
                ) : (
                  <Circle className="w-4 h-4 text-muted-foreground/40 ml-auto flex-shrink-0" />
                )}
              </div>
            ))}
          </div>
        </section>

        {/* Roadmap */}
        <section>
          <h2 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-3">
            Roadmap de migração
          </h2>
          <div className="flex flex-col gap-2">
            {STAGES.map((s, i) => (
              <div
                key={s.n}
                className={cn(
                  'flex items-start gap-4 rounded-xl border p-4 transition-colors',
                  s.status === 'done'
                    ? 'border-primary/40 bg-primary/5'
                    : 'border-border bg-card opacity-70',
                )}
              >
                <div className={cn(
                  'w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5',
                  s.status === 'done'
                    ? 'bg-primary text-white'
                    : 'bg-muted text-muted-foreground',
                )}>
                  {s.status === 'done' ? '✓' : s.n}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-semibold">{s.label}</div>
                  <div className="text-xs text-muted-foreground mt-0.5">{s.desc}</div>
                </div>
                {s.status === 'done' && (
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-green-500/10 text-green-400 border border-green-500/20 flex-shrink-0">
                    done
                  </span>
                )}
                {s.status === 'pending' && i === 1 && (
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-yellow-500/10 text-yellow-400 border border-yellow-500/20 flex-shrink-0">
                    next
                  </span>
                )}
              </div>
            ))}
          </div>
        </section>

        {/* Infra detail */}
        <section className="rounded-xl border border-border bg-card p-5 text-xs text-muted-foreground space-y-2">
          <div className="font-semibold text-foreground text-sm mb-3 flex items-center gap-2">
            <Box className="w-4 h-4" /> Como funciona
          </div>
          <div className="flex gap-2"><span className="text-primary font-mono">GET /</span><span>→ vanilla HTML (webapp/index.html) — inalterado</span></div>
          <div className="flex gap-2"><span className="text-primary font-mono">GET /app/*</span><span>→ este app React (webapp-react/dist/) — em paralelo</span></div>
          <div className="flex gap-2"><span className="text-primary font-mono">POST /api/*</span><span>→ FastAPI backend Python — compartilhado por ambos</span></div>
        </section>

      </main>
    </div>
  )
}
