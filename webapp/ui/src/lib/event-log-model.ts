import type { ToolUIPart } from "ai";

import type { ContractEvent, EventFilter } from "@/types/contract";

import { tryParseJson } from "./format";

export type ToolState = ToolUIPart["state"];

export interface ToolInvocation {
  id: string;
  toolName: string;
  callEvent?: ContractEvent;
  responseEvent?: ContractEvent;
  state: ToolState;
  input: Record<string, unknown>;
  output?: Record<string, unknown>;
  timestamp: string;
  source: string;
  subtaskId?: string | null;
}

export type EventLogEntry =
  | { kind: "tool"; invocation: ToolInvocation; sortKey: string }
  | { kind: "simple"; event: ContractEvent; sortKey: string };

function normalizeEventType(type: string): string {
  if (type === "tool_result") return "tool_response";
  return type;
}

function isToolResponse(type: string): boolean {
  const normalized = normalizeEventType(type);
  return normalized === "tool_response";
}

function isToolCall(type: string): boolean {
  return type === "tool_call";
}

function getToolName(event: ContractEvent): string {
  const metadata = event.metadata ?? {};
  const tool = metadata.tool;
  if (typeof tool === "string" && tool.length > 0) return tool;
  return "unknown";
}

function getInvocationId(event: ContractEvent): string | undefined {
  const id = event.metadata?.invocation_id;
  return typeof id === "string" && id.length > 0 ? id : undefined;
}

function buildStructuredPayload(
  event: ContractEvent,
  role: "input" | "output",
): Record<string, unknown> {
  const metadata = { ...(event.metadata ?? {}) };
  const parsed = tryParseJson(event.message);
  const base: Record<string, unknown> = {
    tool: getToolName(event),
    message: event.message,
    source: event.source,
    ...metadata,
  };

  if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
    return { ...base, ...(parsed as Record<string, unknown>) };
  }

  if (parsed !== null) {
    return { ...base, [role === "input" ? "args" : "result"]: parsed };
  }

  return base;
}

function deriveToolState(
  callEvent: ContractEvent | undefined,
  responseEvent: ContractEvent | undefined,
): ToolState {
  if (!callEvent) {
    if (responseEvent?.severity === "error") return "output-error";
    return "output-available";
  }

  if (!responseEvent) return "input-available";

  if (responseEvent.severity === "error") return "output-error";

  const message = responseEvent.message.toLowerCase();
  if (
    message.includes("error") ||
    message.includes("fail") ||
    message.includes("denied")
  ) {
    return "output-error";
  }

  return "output-available";
}

function pairKey(event: ContractEvent): string {
  return getInvocationId(event) ?? getToolName(event);
}

export function buildToolInvocations(events: ContractEvent[]): ToolInvocation[] {
  const sorted = [...events].sort((a, b) =>
    a.timestamp.localeCompare(b.timestamp),
  );

  const pendingByKey = new Map<string, ContractEvent[]>();
  const invocations: ToolInvocation[] = [];

  for (const event of sorted) {
    if (isToolCall(event.type)) {
      const key = pairKey(event);
      const queue = pendingByKey.get(key) ?? [];
      queue.push(event);
      pendingByKey.set(key, queue);
      continue;
    }

    if (!isToolResponse(event.type)) continue;

    const key = pairKey(event);
    const queue = pendingByKey.get(key);
    const callEvent = queue?.shift();
    if (queue && queue.length === 0) pendingByKey.delete(key);

    const toolName = getToolName(callEvent ?? event);
    const state = deriveToolState(callEvent, event);

    invocations.push({
      id: callEvent?.event_id ?? event.event_id,
      toolName,
      callEvent,
      responseEvent: event,
      state,
      input: callEvent ? buildStructuredPayload(callEvent, "input") : {},
      output: buildStructuredPayload(event, "output"),
      timestamp: callEvent?.timestamp ?? event.timestamp,
      source: callEvent?.source ?? event.source,
      subtaskId: callEvent?.subtask_id ?? event.subtask_id,
    });
  }

  for (const [, queue] of pendingByKey) {
    for (const callEvent of queue) {
      invocations.push({
        id: callEvent.event_id,
        toolName: getToolName(callEvent),
        callEvent,
        state: "input-available",
        input: buildStructuredPayload(callEvent, "input"),
        timestamp: callEvent.timestamp,
        source: callEvent.source,
        subtaskId: callEvent.subtask_id,
      });
    }
  }

  return invocations.sort((a, b) => a.timestamp.localeCompare(b.timestamp));
}

function isSimpleEvent(event: ContractEvent): boolean {
  const type = normalizeEventType(event.type);
  return !isToolCall(type) && !isToolResponse(type);
}

export function buildEventLogEntries(events: ContractEvent[]): EventLogEntry[] {
  const toolInvocations = buildToolInvocations(events);
  const pairedCallIds = new Set(
    toolInvocations.flatMap((inv) =>
      [inv.callEvent?.event_id, inv.responseEvent?.event_id].filter(Boolean),
    ),
  );

  const entries: EventLogEntry[] = [];

  for (const invocation of toolInvocations) {
    entries.push({
      kind: "tool",
      invocation,
      sortKey: invocation.timestamp,
    });
  }

  for (const event of events) {
    if (pairedCallIds.has(event.event_id)) continue;
    if (!isSimpleEvent(event)) continue;
    entries.push({
      kind: "simple",
      event,
      sortKey: event.timestamp,
    });
  }

  return entries.sort((a, b) => a.sortKey.localeCompare(b.sortKey));
}

export function filterEventLogEntries(
  entries: EventLogEntry[],
  filter: EventFilter,
): EventLogEntry[] {
  if (filter === "all") return entries;

  if (filter === "model") {
    return entries.filter(
      (entry) =>
        entry.kind === "simple" &&
        (entry.event.type === "model" || entry.event.type === "final_response"),
    );
  }

  if (filter === "tool_call") {
    return entries.filter((entry) => entry.kind === "tool");
  }

  if (filter === "error") {
    return entries.filter((entry) => {
      if (entry.kind === "tool") {
        return (
          entry.invocation.state === "output-error" ||
          entry.invocation.responseEvent?.severity === "error" ||
          entry.invocation.responseEvent?.severity === "warning" ||
          entry.invocation.callEvent?.severity === "error" ||
          entry.invocation.callEvent?.severity === "warning"
        );
      }
      return (
        entry.event.severity === "error" || entry.event.severity === "warning"
      );
    });
  }

  return entries;
}
