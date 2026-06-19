import { StrictMode } from "react";
import { createRoot, type Root } from "react-dom/client";

import { EventLogPanel } from "@/components/event-log/EventLogPanel";
import type { ContractEvent } from "@/types/contract";

import "./index.css";

let root: Root | null = null;

function mountEventLog(events: ContractEvent[]): void {
  const container = document.getElementById("event-log-root");
  if (!container) return;

  if (!root) {
    root = createRoot(container);
  }

  root.render(
    <StrictMode>
      <EventLogPanel events={events} />
    </StrictMode>,
  );
}

declare global {
  interface Window {
    EventLogBridge?: {
      render: (events: ContractEvent[]) => void;
    };
  }
}

window.EventLogBridge = {
  render: mountEventLog,
};

mountEventLog([]);
