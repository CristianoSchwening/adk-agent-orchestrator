import { useEffect, useMemo, useRef, useState } from "react";

import {
  buildEventLogEntries,
  filterEventLogEntries,
} from "@/lib/event-log-model";
import type { ContractEvent, EventFilter } from "@/types/contract";

import { SimpleEventCard } from "./SimpleEventCard";
import { ToolEventCard } from "./ToolEventCard";

const FILTERS: { id: EventFilter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "model", label: "Model" },
  { id: "tool_call", label: "Tools" },
  { id: "error", label: "Errors" },
];

interface EventLogPanelProps {
  events: ContractEvent[];
}

export function EventLogPanel({ events }: EventLogPanelProps) {
  const [filter, setFilter] = useState<EventFilter>("all");
  const [autoScroll, setAutoScroll] = useState(true);
  const listRef = useRef<HTMLDivElement>(null);

  const entries = useMemo(() => {
    const allEntries = buildEventLogEntries(events);
    return filterEventLogEntries(allEntries, filter);
  }, [events, filter]);

  useEffect(() => {
    if (!autoScroll || !listRef.current) return;
    listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [entries, autoScroll]);

  return (
    <div className="dark overflow-hidden rounded-xl border border-[#2e3250] bg-[#1a1d27] text-foreground">
      <div className="flex items-center gap-2 border-[#2e3250] border-b px-[18px] py-[14px]">
        <div className="flex size-5 items-center justify-center rounded-md bg-blue-500/15 text-sm">
          📡
        </div>
        <span className="font-semibold text-[13px] text-foreground uppercase tracking-wide">
          Event Log
        </span>
        <div className="ml-auto flex items-center gap-2">
          <span className="text-[11px] text-muted-foreground">
            {entries.length} events
          </span>
          <button
            type="button"
            className="rounded-lg border border-transparent px-2 py-1 text-[12px] text-muted-foreground transition hover:bg-[#22263a] hover:text-foreground"
            style={{ color: autoScroll ? "#818cf8" : undefined }}
            title="Auto-scroll"
            onClick={() => setAutoScroll((value) => !value)}
          >
            ↓
          </button>
        </div>
      </div>

      <div className="flex flex-wrap gap-1 border-[#2e3250] border-b px-[14px] py-2">
        {FILTERS.map(({ id, label }) => (
          <button
            key={id}
            type="button"
            className={`rounded-lg px-[14px] py-1.5 font-medium text-[12px] transition ${
              filter === id
                ? "border border-indigo-400/40 bg-indigo-500/20 text-[#818cf8]"
                : "border border-transparent text-muted-foreground hover:bg-[#22263a] hover:text-foreground"
            }`}
            onClick={() => setFilter(id)}
          >
            {label}
          </button>
        ))}
      </div>

      <div
        ref={listRef}
        className="max-h-[500px] space-y-2 overflow-y-auto p-3"
      >
        {entries.length === 0 ? (
          <div className="py-10 text-center text-muted-foreground">
            <div className="mb-2 text-2xl">📡</div>
            <div className="text-sm">
              {events.length === 0
                ? "No events yet"
                : "No events match the filter"}
            </div>
          </div>
        ) : (
          entries.map((entry) =>
            entry.kind === "tool" ? (
              <ToolEventCard
                key={entry.invocation.id}
                invocation={entry.invocation}
              />
            ) : (
              <SimpleEventCard key={entry.event.event_id} event={entry.event} />
            ),
          )
        )}
      </div>
    </div>
  );
}
