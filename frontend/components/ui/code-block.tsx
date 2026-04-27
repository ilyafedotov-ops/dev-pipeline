"use client";

import { useState } from "react";

import { Check, Copy } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface CodeBlockProps {
  code: string | object;
  language?: string;
  title?: string;
  className?: string;
  maxHeight?: string;
  wrapLongLines?: boolean;
}

export function CodeBlock({
  code,
  language = "json",
  title,
  className,
  maxHeight = "400px",
  wrapLongLines = false,
}: CodeBlockProps) {
  const [copied, setCopied] = useState(false);
  const codeString = typeof code === "string" ? code : JSON.stringify(code, null, 2);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(codeString);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={cn("bg-muted/50 rounded-lg border", className)}>
      {title && (
        <div className="flex items-center justify-between border-b px-4 py-2">
          <span className="text-muted-foreground text-sm font-medium">{title}</span>
          <Button variant="ghost" size="sm" onClick={handleCopy}>
            {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
          </Button>
        </div>
      )}
      <pre
        className={cn(
          "overflow-auto p-4 text-sm",
          !title && "relative",
          wrapLongLines && "whitespace-pre-wrap break-words"
        )}
        style={{ maxHeight }}
      >
        {!title && (
          <Button variant="ghost" size="sm" className="absolute top-2 right-2" onClick={handleCopy}>
            {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
          </Button>
        )}
        <code
          className={cn(`language-${language} text-foreground`, wrapLongLines && "break-words")}
        >
          {codeString}
        </code>
      </pre>
    </div>
  );
}
