/* eslint-disable react-refresh/only-export-components */
import * as React from "react";
import {
  FileAudio,
  FileText,
  FileVideo,
  Image as ImageIcon,
  Link,
  Paperclip,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type AttachmentData = {
  id?: string;
  type?: string;
  mediaType?: string;
  mimeType?: string;
  filename?: string;
  name?: string;
  url?: string;
  uri?: string;
  size?: number;
  sizeBytes?: number;
  title?: string;
  sourceType?: string;
};

type AttachmentContextValue = {
  data?: AttachmentData;
  onRemove?: () => void;
};

const AttachmentContext = React.createContext<AttachmentContextValue>({});

function useAttachment() {
  return React.useContext(AttachmentContext);
}

export function getMediaCategory(data?: AttachmentData) {
  if (!data) return "unknown";
  if (data.type === "source" || data.sourceType) return "source";

  const mediaType = (data.mediaType || data.mimeType || data.type || "").toLowerCase();
  if (mediaType.startsWith("image/")) return "image";
  if (mediaType.startsWith("video/")) return "video";
  if (mediaType.startsWith("audio/")) return "audio";
  if (
    mediaType.includes("pdf") ||
    mediaType.includes("document") ||
    mediaType.includes("text/") ||
    mediaType.includes("json") ||
    mediaType.includes("markdown") ||
    mediaType.includes("xml")
  ) {
    return "document";
  }
  return "unknown";
}

export function getAttachmentLabel(data?: AttachmentData) {
  if (!data) return "Attachment";
  return data.filename || data.name || data.title || data.uri || data.url || "Attachment";
}

function getAttachmentUrl(data?: AttachmentData) {
  return data?.url || data?.uri;
}

function CategoryIcon({ category, className }: { category: string; className?: string }) {
  const iconClassName = cn("size-5", className);
  if (category === "image") return <ImageIcon className={iconClassName} />;
  if (category === "video") return <FileVideo className={iconClassName} />;
  if (category === "audio") return <FileAudio className={iconClassName} />;
  if (category === "document") return <FileText className={iconClassName} />;
  if (category === "source") return <Link className={iconClassName} />;
  return <Paperclip className={iconClassName} />;
}

export function Attachments({
  className,
  variant = "grid",
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { variant?: "grid" | "inline" | "list" }) {
  return (
    <div
      data-slot="attachments"
      data-variant={variant}
      className={cn(
        "group/attachments gap-2",
        variant === "grid" && "grid grid-cols-[repeat(auto-fill,minmax(9rem,1fr))]",
        variant === "inline" && "flex flex-wrap",
        variant === "list" && "flex flex-col",
        className,
      )}
      {...props}
    />
  );
}

export function Attachment({
  className,
  data,
  onRemove,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & AttachmentContextValue) {
  return (
    <AttachmentContext.Provider value={{ data, onRemove }}>
      <div
        data-slot="attachment"
        className={cn(
          "group/attachment relative flex min-w-0 overflow-hidden rounded-lg border border-border bg-muted/40 text-sm",
          "group-data-[variant=grid]/attachments:flex-col",
          "group-data-[variant=inline]/attachments:w-fit group-data-[variant=inline]/attachments:items-center group-data-[variant=inline]/attachments:gap-2 group-data-[variant=inline]/attachments:px-2 group-data-[variant=inline]/attachments:py-1.5",
          "group-data-[variant=list]/attachments:items-center group-data-[variant=list]/attachments:gap-3 group-data-[variant=list]/attachments:p-2",
          className,
        )}
        {...props}
      />
    </AttachmentContext.Provider>
  );
}

export function AttachmentPreview({
  className,
  fallbackIcon,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { fallbackIcon?: React.ReactNode }) {
  const { data } = useAttachment();
  const category = getMediaCategory(data);
  const url = getAttachmentUrl(data);
  const label = getAttachmentLabel(data);

  return (
    <div
      data-slot="attachment-preview"
      className={cn(
        "flex shrink-0 items-center justify-center overflow-hidden bg-background/70 text-muted-foreground",
        "group-data-[variant=grid]/attachments:aspect-video group-data-[variant=grid]/attachments:w-full",
        "group-data-[variant=inline]/attachments:size-6 group-data-[variant=inline]/attachments:rounded-md",
        "group-data-[variant=list]/attachments:size-12 group-data-[variant=list]/attachments:rounded-md",
        className,
      )}
      {...props}
    >
      {category === "image" && url ? (
        <img src={url} alt={label} className="size-full object-cover" loading="lazy" />
      ) : category === "video" && url ? (
        <video src={url} className="size-full object-cover" muted preload="metadata" />
      ) : fallbackIcon ? (
        fallbackIcon
      ) : (
        <CategoryIcon category={category} />
      )}
    </div>
  );
}

export function AttachmentInfo({
  className,
  showMediaType = false,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { showMediaType?: boolean }) {
  const { data } = useAttachment();
  const mediaType = data?.mediaType || data?.mimeType || data?.type;
  return (
    <div data-slot="attachment-info" className={cn("min-w-0 flex-1 px-2 py-2", className)} {...props}>
      <div className="truncate font-medium text-foreground text-xs">{getAttachmentLabel(data)}</div>
      {showMediaType && mediaType ? (
        <div className="truncate text-[11px] text-muted-foreground">{mediaType}</div>
      ) : null}
    </div>
  );
}

export function AttachmentRemove({
  className,
  label = "Remove",
  ...props
}: React.ComponentProps<typeof Button> & { label?: string }) {
  const { onRemove } = useAttachment();
  if (!onRemove) return null;
  return (
    <Button
      aria-label={label}
      className={cn("absolute right-1 top-1 opacity-0 transition group-hover/attachment:opacity-100", className)}
      size="icon-xs"
      type="button"
      variant="secondary"
      onClick={onRemove}
      {...props}
    >
      <X className="size-3" />
    </Button>
  );
}

export function AttachmentHoverCard({ children, className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("group/attachment-hover relative", className)} {...props}>{children}</div>;
}

export function AttachmentHoverCardTrigger({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("cursor-default", className)} {...props} />;
}

export function AttachmentHoverCardContent({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "pointer-events-none absolute right-0 top-full z-50 mt-2 hidden w-72 rounded-xl border border-border bg-popover p-3 text-popover-foreground shadow-xl group-hover/attachment-hover:block",
        className,
      )}
      {...props}
    />
  );
}

export function AttachmentEmpty({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("py-8 text-center text-muted-foreground text-sm", className)} {...props} />
  );
}
