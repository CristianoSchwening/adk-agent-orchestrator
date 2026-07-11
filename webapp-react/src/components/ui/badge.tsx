import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold transition-colors select-none',
  {
    variants: {
      variant: {
        default:    'border-transparent bg-primary text-primary-foreground',
        secondary:  'border-transparent bg-secondary text-secondary-foreground',
        outline:    'border-border text-foreground',
        published:  'border-green-500/30  bg-green-500/10  text-green-400',
        superseded: 'border-border        bg-muted/40      text-muted-foreground',
        draft:      'border-yellow-500/30 bg-yellow-500/10 text-yellow-400',
        failed:     'border-red-500/30    bg-red-500/10    text-red-400',
        internal:   'border-purple-500/30 bg-purple-500/10 text-purple-400',
        user_visible:'border-cyan-500/30  bg-cyan-500/10   text-cyan-400',
      },
    },
    defaultVariants: { variant: 'default' },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />
}

export { Badge, badgeVariants }
