import { StrictMode } from "react";
import { createRoot, type Root } from "react-dom/client";

import { ArtifactsPanel } from "@/components/artifacts/ArtifactsPanel";
import { EventLogPanel } from "@/components/event-log/EventLogPanel";
import type { ContractArtifact, ContractEvent } from "@/types/contract";

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


let artifactsRoot: Root | null = null;

function mountArtifacts(artifacts: ContractArtifact[]): void {
  const container = document.getElementById("artifacts-root");
  if (!container) return;

  if (!artifactsRoot) {
    artifactsRoot = createRoot(container);
  }

  artifactsRoot.render(
    <StrictMode>
      <ArtifactsPanel artifacts={artifacts} />
    </StrictMode>,
  );
}

declare global {
  interface Window {
    EventLogBridge?: {
      render: (events: ContractEvent[]) => void;
    };
    ArtifactsBridge?: {
      render: (artifacts: ContractArtifact[]) => void;
    };
  }
}

window.EventLogBridge = {
  render: mountEventLog,
};

window.ArtifactsBridge = {
  render: mountArtifacts,
};

mountEventLog([]);
mountArtifacts([]);
