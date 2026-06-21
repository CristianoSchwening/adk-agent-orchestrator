import { ExternalLink } from "lucide-react";

import {
  Attachment,
  AttachmentHoverCard,
  AttachmentHoverCardContent,
  AttachmentHoverCardTrigger,
  AttachmentInfo,
  AttachmentPreview,
  Attachments,
  getMediaCategory,
} from "@/components/ai-elements/attachments";
import type { ContractArtifact } from "@/types/contract";

interface ArtifactsPanelProps {
  artifacts: ContractArtifact[];
}

const CATEGORY_LABELS: Record<string, string> = {
  image: "Image",
  video: "Video",
  audio: "Audio",
  document: "Document",
  source: "Source",
  unknown: "File",
};

function formatBytes(size?: number | null) {
  if (size == null) return null;
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function toAttachmentData(artifact: ContractArtifact) {
  return {
    id: artifact.artifact_id,
    name: artifact.name,
    mimeType: artifact.mime_type ?? undefined,
    uri: artifact.uri ?? undefined,
    sizeBytes: artifact.size_bytes ?? undefined,
  };
}

export function ArtifactsPanel({ artifacts }: ArtifactsPanelProps) {
  if (artifacts.length === 0) return null;

  return (
    <div className="dark overflow-hidden rounded-xl border border-[#2e3250] bg-[#1a1d27] text-foreground">
      <div className="flex items-center gap-2 border-[#2e3250] border-b px-[18px] py-[14px]">
        <div className="flex size-5 items-center justify-center rounded-md bg-emerald-500/15 text-sm">
          📎
        </div>
        <span className="font-semibold text-[13px] text-foreground uppercase tracking-wide">
          Artifacts
        </span>
        <span className="ml-auto text-[11px] text-muted-foreground">
          {artifacts.length} files
        </span>
      </div>

      <div className="p-3">
        <Attachments variant="list">
          {artifacts.map((artifact) => {
            const data = toAttachmentData(artifact);
            const category = getMediaCategory(data);
            const size = formatBytes(artifact.size_bytes);

            return (
              <AttachmentHoverCard key={artifact.artifact_id}>
                <AttachmentHoverCardTrigger>
                  <Attachment data={data} className="transition hover:border-indigo-400/50 hover:bg-[#22263a]">
                    <AttachmentPreview />
                    <AttachmentInfo showMediaType />
                    <div className="flex shrink-0 items-center gap-2 pr-2 text-[11px] text-muted-foreground">
                      <span className="rounded-full border border-border bg-background/60 px-2 py-0.5">
                        {CATEGORY_LABELS[category] ?? CATEGORY_LABELS.unknown}
                      </span>
                      {size ? <span>{size}</span> : null}
                      {artifact.uri ? (
                        <a
                          aria-label={`Open ${artifact.name}`}
                          className="text-indigo-300 transition hover:text-indigo-200"
                          href={artifact.uri}
                          rel="noreferrer"
                          target="_blank"
                        >
                          <ExternalLink className="size-3.5" />
                        </a>
                      ) : null}
                    </div>
                  </Attachment>
                </AttachmentHoverCardTrigger>
                <AttachmentHoverCardContent>
                  <div className="mb-2 overflow-hidden rounded-lg border border-border bg-background/60">
                    <Attachment data={data}>
                      <AttachmentPreview className="aspect-video size-auto w-full rounded-none" />
                    </Attachment>
                  </div>
                  <div className="truncate font-semibold text-sm">{artifact.name}</div>
                  <div className="mt-1 flex flex-wrap gap-2 text-[11px] text-muted-foreground">
                    <span>{CATEGORY_LABELS[category] ?? CATEGORY_LABELS.unknown}</span>
                    {artifact.mime_type ? <span>{artifact.mime_type}</span> : null}
                    {size ? <span>{size}</span> : null}
                  </div>
                  {artifact.uri ? (
                    <div className="mt-2 truncate font-mono text-[11px] text-indigo-300">
                      {artifact.uri}
                    </div>
                  ) : null}
                </AttachmentHoverCardContent>
              </AttachmentHoverCard>
            );
          })}
        </Attachments>
      </div>
    </div>
  );
}
