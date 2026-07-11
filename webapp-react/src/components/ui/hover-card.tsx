import * as HoverCardPrimitive from '@radix-ui/react-hover-card'
import { cn } from '@/lib/utils'

const HoverCard = HoverCardPrimitive.Root
const HoverCardTrigger = HoverCardPrimitive.Trigger

const HoverCardContent = ({
  className,
  align = 'center',
  sideOffset = 6,
  ...props
}: React.ComponentPropsWithoutRef<typeof HoverCardPrimitive.Content>) => (
  <HoverCardPrimitive.Content
    align={align}
    sideOffset={sideOffset}
    className={cn(
      'z-50 w-72 rounded-xl border border-border bg-card p-4 text-foreground shadow-xl',
      'data-[state=open]:animate-in data-[state=closed]:animate-out',
      'data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
      'data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95',
      className,
    )}
    {...props}
  />
)

export { HoverCard, HoverCardTrigger, HoverCardContent }
