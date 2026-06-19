import {
  Tool,
  ToolContent,
  ToolHeader,
  ToolInput,
  ToolOutput,
} from "@/components/ai-elements/tool";
import { formatTime } from "@/lib/format";
import type { ToolInvocation } from "@/lib/event-log-model";

interface ToolEventCardProps {
  invocation: ToolInvocation;
}

export function ToolEventCard({ invocation }: ToolEventCardProps) {
  const { state, toolName, input, output, responseEvent } = invocation;
  const defaultOpen = state === "output-available" || state === "output-error";

  return (
    <div className="space-y-1">
      <Tool defaultOpen={defaultOpen} className="mb-0 bg-card">
        <ToolHeader
          type="dynamic-tool"
          toolName={toolName}
          state={state}
          title={toolName}
        />
        <ToolContent>
          {Object.keys(input).length > 0 ? <ToolInput input={input} /> : null}
          <ToolOutput
            output={output}
            errorText={
              state === "output-error" ? responseEvent?.message : undefined
            }
          />
        </ToolContent>
      </Tool>
      <div className="flex flex-wrap gap-2 px-1 font-mono text-[11px] text-muted-foreground">
        <span>{formatTime(invocation.timestamp)}</span>
        <span className="text-cyan-400">{invocation.source}</span>
        {invocation.subtaskId ? <span>{invocation.subtaskId}</span> : null}
      </div>
    </div>
  );
}
