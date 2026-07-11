import { Moon, Sun } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { Theme } from '@/hooks/useTheme'

interface ThemeToggleProps {
  theme: Theme
  onToggle: () => void
  className?: string
}

export function ThemeToggle({ theme, onToggle, className }: ThemeToggleProps) {
  const isDark = theme === 'dark'

  return (
    <button
      onClick={onToggle}
      aria-label={isDark ? 'Mudar para tema claro' : 'Mudar para tema escuro'}
      title={isDark ? 'Tema claro' : 'Tema escuro'}
      className={cn(
        'relative flex items-center justify-between gap-1',
        'h-7 w-[52px] rounded-full border px-1',
        'transition-colors duration-300 focus-visible:outline-none',
        isDark
          ? 'border-border bg-secondary hover:border-primary/50'
          : 'border-border bg-secondary hover:border-primary/50',
        className,
      )}
    >
      {/* Track icons */}
      <Sun
        className={cn(
          'w-3.5 h-3.5 transition-all duration-300',
          isDark ? 'text-muted-foreground/40' : 'text-yellow-500',
        )}
      />
      <Moon
        className={cn(
          'w-3.5 h-3.5 transition-all duration-300',
          isDark ? 'text-primary' : 'text-muted-foreground/40',
        )}
      />

      {/* Sliding thumb */}
      <span
        className={cn(
          'absolute top-0.5 h-6 w-6 rounded-full',
          'flex items-center justify-center',
          'shadow-sm transition-all duration-300 ease-in-out',
          isDark
            ? 'left-[26px] bg-primary/90'
            : 'left-0.5 bg-yellow-400',
        )}
      >
        {isDark
          ? <Moon className="w-3 h-3 text-white" />
          : <Sun  className="w-3 h-3 text-yellow-900" />
        }
      </span>
    </button>
  )
}
