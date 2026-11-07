'use client'

import { useState } from 'react'
import { Check, Copy } from 'lucide-react'
import { cn } from '@/lib/utils'

export function CopyKey({ value, compact = false }: { value: string; compact?: boolean }) {
  const [copied, setCopied] = useState(false)

  async function copy() {
    await navigator.clipboard.writeText(value)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  if (compact) {
    return (
      <button
        type="button"
        onClick={copy}
        className="flex items-center gap-2 font-mono text-xs text-foreground transition-colors hover:text-boost"
        aria-label={`Copier la clé ${value}`}
      >
        {value}
        {copied ? (
          <Check className="size-3.5 text-boost" aria-hidden="true" />
        ) : (
          <Copy className="size-3.5 text-muted-foreground" aria-hidden="true" />
        )}
      </button>
    )
  }

  return (
    <div className="flex items-center gap-3 rounded-2xl border border-primary/60 bg-card p-4 shadow-[0_0_40px_-12px] shadow-primary/50">
      <code className="flex-1 truncate text-center font-mono text-lg font-semibold tracking-wider md:text-xl">
        {value}
      </code>
      <button
        type="button"
        onClick={copy}
        className={cn(
          'flex items-center gap-2 rounded-md px-3 py-2 text-sm font-semibold transition-colors',
          copied ? 'bg-boost text-background' : 'bg-secondary text-secondary-foreground hover:bg-muted',
        )}
      >
        {copied ? <Check className="size-4" aria-hidden="true" /> : <Copy className="size-4" aria-hidden="true" />}
        {copied ? 'Copiée' : 'Copier'}
      </button>
    </div>
  )
}
