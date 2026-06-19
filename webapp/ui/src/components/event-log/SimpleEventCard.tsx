import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { formatTime } from "@/lib/format";
import type { ContractEvent } from "@/types/contract";

function eventTypeLabel(event: ContractEvent): string {
  if (event.severity === "error") return "ERROR";
  if (event.severity === "warning") return "WARNING";
  if (event.type === "final_response") return "FINAL";
  if (event.type === "model") return "MODEL";
  return event.type.toUpperCase();
}

function badgeVariant(event: ContractEvent): "default" | "secondary" | "destructive" | "outline" {
  if (event.severity === "error") return "destructive";
  if (event.severity === "warning") return "outline";
  if (event.type === "final_response") return "default";
  return "secondary";
}

interface SimpleEventCardProps {
  event: ContractEvent;
}

export function SimpleEventCard({ event }: SimpleEventCardProps) {
  return (
    <Card className="border-border/80 bg-card py-3 shadow-none">
      <CardHeader className="flex flex-row items-center justify-between gap-2 px-3 pb-2">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={badgeVariant(event)}>{eventTypeLabel(event)}</Badge>
          <span className="font-mono text-muted-foreground text-xs">
            {formatTime(event.timestamp)}
          </span>
          <span className="text-cyan-400 text-xs">{event.source}</span>
          {event.subtask_id ? (
            <span className="text-muted-foreground text-xs">{event.subtask_id}</span>
          ) : null}
        </div>
      </CardHeader>
      <CardContent className="px-3 pt-0">
        <p className="whitespace-pre-wrap font-mono text-foreground text-xs leading-relaxed">
          {event.message}
        </p>
      </CardContent>
    </Card>
  );
}
