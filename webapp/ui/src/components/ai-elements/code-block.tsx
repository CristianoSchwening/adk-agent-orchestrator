"use client";

import { cn } from "@/lib/utils";
import type { ComponentProps } from "react";

export type CodeBlockProps = ComponentProps<"pre"> & {
  code: string;
  language?: string;
};

export function CodeBlock({
  code,
  className,
  ...props
}: CodeBlockProps) {
  return (
    <pre
      className={cn(
        "overflow-x-auto p-3 font-mono text-xs leading-relaxed",
        className,
      )}
      {...props}
    >
      <code>{code}</code>
    </pre>
  );
}
