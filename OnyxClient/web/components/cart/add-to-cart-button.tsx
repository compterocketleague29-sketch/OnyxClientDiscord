'use client'

import { useState, useTransition } from 'react'
import { Check, ShoppingCart } from 'lucide-react'
import { addToCart } from '@/app/actions/cart'
import { cn } from '@/lib/utils'

export function AddToCartButton({
  productId,
  label,
  highlighted,
}: {
  productId: string
  label: string
  highlighted: boolean
}) {
  const [isPending, startTransition] = useTransition()
  const [added, setAdded] = useState(false)

  function handleClick() {
    startTransition(async () => {
      const result = await addToCart(productId)
      if (result.ok) {
        setAdded(true)
        setTimeout(() => setAdded(false), 1800)
      }
    })
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={isPending}
      className={cn(
        'mt-8 flex items-center justify-center gap-2 rounded-md px-4 py-3 font-semibold transition-opacity hover:opacity-90 disabled:opacity-60',
        highlighted
          ? 'bg-primary text-primary-foreground'
          : 'border border-border bg-secondary text-secondary-foreground',
      )}
    >
      {added ? (
        <Check className="size-4" aria-hidden="true" />
      ) : (
        <ShoppingCart className="size-4" aria-hidden="true" />
      )}
      <span aria-live="polite">{added ? 'Ajouté au panier' : `Ajouter au panier — ${label}`}</span>
    </button>
  )
}
