/* eslint-disable react-refresh/only-export-components */
import * as React from "react";
import {
  ImagePlus,
  Loader2,
  Paperclip,
  Plus,
  Send,
  Square,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

export type PromptInputAttachment = {
  id: string;
  file: File;
  name: string;
  filename: string;
  mediaType: string;
  type: string;
  size: number;
  url?: string;
};

export type PromptInputMessage = {
  text: string;
  files?: PromptInputAttachment[];
};

type PromptInputError = {
  code: "max_files" | "max_file_size" | "accept";
  message: string;
};

type PromptInputContextValue = {
  text: string;
  setText: (text: string) => void;
  files: PromptInputAttachment[];
  add: (files: FileList | File[]) => void;
  remove: (id: string) => void;
  clear: () => void;
  openFileDialog: () => void;
  inputRef: React.RefObject<HTMLInputElement | null>;
  accept?: string;
  multiple?: boolean;
};

const PromptInputContext = React.createContext<PromptInputContextValue | null>(null);

const toAttachment = (file: File): PromptInputAttachment => ({
  id: `${file.name}-${file.lastModified}-${crypto.randomUUID()}`,
  file,
  name: file.name,
  filename: file.name,
  mediaType: file.type || "application/octet-stream",
  type: file.type || "application/octet-stream",
  size: file.size,
  url: file.type.startsWith("image/") || file.type.startsWith("video/") ? URL.createObjectURL(file) : undefined,
});

const matchesAccept = (file: File, accept?: string) => {
  if (!accept) return true;
  const rules = accept.split(",").map((rule) => rule.trim()).filter(Boolean);
  if (!rules.length) return true;

  return rules.some((rule) => {
    if (rule.endsWith("/*")) return file.type.startsWith(rule.slice(0, -1));
    if (rule.startsWith(".")) return file.name.toLowerCase().endsWith(rule.toLowerCase());
    return file.type === rule;
  });
};

function usePromptInputContext() {
  const context = React.useContext(PromptInputContext);
  if (!context) {
    throw new Error("PromptInput components must be used inside <PromptInput />");
  }
  return context;
}

export function usePromptInputAttachments() {
  const { files, add, remove, clear, openFileDialog } = usePromptInputContext();
  return { files, add, remove, clear, openFileDialog };
}

export function PromptInput({
  children,
  className,
  onSubmit,
  accept,
  multiple = false,
  globalDrop = false,
  maxFiles = 8,
  maxFileSize = 20 * 1024 * 1024,
  onError,
  ...props
}: Omit<React.ComponentProps<"form">, "onSubmit"> & {
  onSubmit?: (message: PromptInputMessage, event: React.FormEvent<HTMLFormElement>) => void;
  accept?: string;
  multiple?: boolean;
  globalDrop?: boolean;
  maxFiles?: number;
  maxFileSize?: number;
  onError?: (error: PromptInputError) => void;
}) {
  const [text, setText] = React.useState("");
  const [files, setFiles] = React.useState<PromptInputAttachment[]>([]);
  const inputRef = React.useRef<HTMLInputElement>(null);

  React.useEffect(() => () => {
    files.forEach((file) => {
      if (file.url) URL.revokeObjectURL(file.url);
    });
  }, [files]);

  const report = React.useCallback((error: PromptInputError) => onError?.(error), [onError]);

  const add = React.useCallback((incoming: FileList | File[]) => {
    const nextFiles = Array.from(incoming);
    const accepted: PromptInputAttachment[] = [];

    for (const file of nextFiles) {
      if (!matchesAccept(file, accept)) {
        report({ code: "accept", message: `${file.name} is not an accepted file type.` });
        continue;
      }
      if (file.size > maxFileSize) {
        report({ code: "max_file_size", message: `${file.name} exceeds the upload limit.` });
        continue;
      }
      accepted.push(toAttachment(file));
    }

    setFiles((current) => {
      const combined = multiple ? [...current, ...accepted] : accepted.slice(0, 1);
      if (combined.length > maxFiles) {
        report({ code: "max_files", message: `You can attach up to ${maxFiles} files.` });
      }
      return combined.slice(0, maxFiles);
    });
  }, [accept, maxFileSize, maxFiles, multiple, report]);

  const remove = React.useCallback((id: string) => {
    setFiles((current) => current.filter((file) => {
      if (file.id === id && file.url) URL.revokeObjectURL(file.url);
      return file.id !== id;
    }));
  }, []);

  const clear = React.useCallback(() => {
    setFiles((current) => {
      current.forEach((file) => {
        if (file.url) URL.revokeObjectURL(file.url);
      });
      return [];
    });
  }, []);

  React.useEffect(() => {
    if (!globalDrop) return undefined;

    const onDragOver = (event: DragEvent) => {
      event.preventDefault();
    };
    const onDrop = (event: DragEvent) => {
      event.preventDefault();
      if (event.dataTransfer?.files.length) add(event.dataTransfer.files);
    };

    document.addEventListener("dragover", onDragOver);
    document.addEventListener("drop", onDrop);
    return () => {
      document.removeEventListener("dragover", onDragOver);
      document.removeEventListener("drop", onDrop);
    };
  }, [add, globalDrop]);

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onSubmit?.({ text: text.trim(), files }, event);
    setText("");
    clear();
    if (inputRef.current) inputRef.current.value = "";
  };

  return (
    <PromptInputContext.Provider
      value={{ text, setText, files, add, remove, clear, openFileDialog: () => inputRef.current?.click(), inputRef, accept, multiple }}
    >
      <form
        className={cn("rounded-2xl border border-border bg-card/95 p-2 shadow-2xl shadow-black/20", className)}
        onSubmit={handleSubmit}
        {...props}
      >
        <input
          ref={inputRef}
          accept={accept}
          className="hidden"
          multiple={multiple}
          type="file"
          onChange={(event) => event.target.files && add(event.target.files)}
        />
        {children}
      </form>
    </PromptInputContext.Provider>
  );
}

export function PromptInputHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("px-2 pb-2", className)} {...props} />;
}

export function PromptInputBody({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("relative", className)} {...props} />;
}

export function PromptInputTextarea({ className, onChange, onKeyDown, ...props }: React.ComponentProps<"textarea">) {
  const { text, setText } = usePromptInputContext();

  return (
    <textarea
      className={cn("min-h-24 w-full resize-none rounded-xl border-0 bg-transparent px-3 py-3 text-sm text-foreground outline-none placeholder:text-muted-foreground", className)}
      value={props.value ?? text}
      onChange={(event) => {
        setText(event.target.value);
        onChange?.(event);
      }}
      onKeyDown={(event) => {
        if (event.key === "Enter" && !event.shiftKey) {
          event.preventDefault();
          event.currentTarget.form?.requestSubmit();
        }
        onKeyDown?.(event);
      }}
      {...props}
    />
  );
}

export function PromptInputFooter({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex items-center justify-between gap-2 pt-2", className)} {...props} />;
}

export function PromptInputTools({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex min-w-0 flex-wrap items-center gap-1", className)} {...props} />;
}

export function PromptInputButton({ className, tooltip, title, ...props }: React.ComponentProps<typeof Button> & { tooltip?: string | { content: React.ReactNode; shortcut?: string } }) {
  const tooltipTitle = typeof tooltip === "string" ? tooltip : typeof tooltip?.content === "string" ? `${tooltip.content}${tooltip.shortcut ? ` (${tooltip.shortcut})` : ""}` : title;
  return <Button className={cn("gap-1.5", className)} size="sm" title={tooltipTitle} type="button" variant="ghost" {...props} />;
}

export function PromptInputSubmit({ className, status = "ready", ...props }: React.ComponentProps<typeof Button> & { status?: string }) {
  const isLoading = status === "streaming" || status === "submitted";
  return (
    <Button aria-label={isLoading ? "Stop generation" : "Send message"} className={className} size="icon" type="submit" {...props}>
      {isLoading ? <Square className="size-4" /> : status === "loading" ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}
    </Button>
  );
}

export const PromptInputSelect = Select;
export const PromptInputSelectTrigger = SelectTrigger;
export const PromptInputSelectContent = SelectContent;
export const PromptInputSelectItem = SelectItem;
export const PromptInputSelectValue = SelectValue;

export function PromptInputActionMenu({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("group/menu relative", className)} {...props} />;
}

export function PromptInputActionMenuTrigger(props: React.ComponentProps<typeof PromptInputButton>) {
  return (
    <PromptInputButton tooltip="Add context" {...props}>
      <Plus className="size-4" />
    </PromptInputButton>
  );
}

export function PromptInputActionMenuContent({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("absolute bottom-full left-0 z-20 mb-2 hidden min-w-52 rounded-xl border border-border bg-popover p-1 text-popover-foreground shadow-xl group-focus-within/menu:block group-hover/menu:block", className)} {...props} />
  );
}

export function PromptInputActionMenuItem({ className, ...props }: React.ComponentProps<"button">) {
  return <button className={cn("flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm hover:bg-accent", className)} type="button" {...props} />;
}

export function PromptInputActionAddAttachments({ label = "Attach files", ...props }: React.ComponentProps<typeof PromptInputActionMenuItem> & { label?: string }) {
  const attachments = usePromptInputAttachments();
  return (
    <PromptInputActionMenuItem onClick={attachments.openFileDialog} {...props}>
      <Paperclip className="size-4" />
      {label}
    </PromptInputActionMenuItem>
  );
}

export function PromptInputActionAddScreenshot({ label = "Add screenshot", ...props }: React.ComponentProps<typeof PromptInputActionMenuItem> & { label?: string }) {
  const attachments = usePromptInputAttachments();
  return (
    <PromptInputActionMenuItem onClick={attachments.openFileDialog} {...props}>
      <ImagePlus className="size-4" />
      {label}
    </PromptInputActionMenuItem>
  );
}
