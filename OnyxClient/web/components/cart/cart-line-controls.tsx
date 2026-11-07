'use client'

import { useTransition } from 'react'
import { Minus, Plus, Trash2 } from 'lucide-react'
import { setCartQuantity } from '@/app/actions/cart'

export function CartLineControls({
  productId,
  productName,
  quantity,
  max,
}: {
  productId: string
  productName: string
  quantity: number
  max: number
}) {
  const [isPending, startTransition] = useTransition()
  const update = (next: number) => startTransition(() => setCartQuantity(productId, next))

  return (
    <div className="flex items-center gap-3">
      <div className="flex items-center rounded-md border border-border" aria-busy={isPending}>
        <button
          type="button"
          onClick={() => update(quantity - 1)}
          disabled={isPending}
          className="flex size-9 items-center justify-center text-muted-foreground transition-colors hover:text-foreground disabled:opacity-50"
          aria-label={`Retirer une licence ${productName}`}
        >
          <Minus className="size-4" aria-hidden="true" />
        </button>
        <span className="w-8 text-center font-semibold tabular-nums" aria-label={`Quantité : ${quantity}`}>
          {quantity}
        </span>
        <button
          type="button"
          onClick={() => update(quantity + 1)}
          disabled={isPending || quantity >= max}
          className="flex size-9 items-center justify-center text-muted-foreground transition-colors hover:text-foreground disabled:opacity-50"
          aria-label={`Ajouter une licence ${productName}`}
        >
          <Plus className="size-4" aria-hidden="true" />
        </button>
      </div>
      <button
        type="button"
        onClick={() => update(0)}
        disabled={isPending}
        className="flex size-9 items-center justify-center rounded-md text-muted-foreground transition-colors hover:text-destructive disabled:opacity-50"
        aria-label={`Supprimer ${productName} du panier`}
      >
        <Trash2 className="size-4" aria-hidden="true" />
      </button>
    </div>
  )
}
