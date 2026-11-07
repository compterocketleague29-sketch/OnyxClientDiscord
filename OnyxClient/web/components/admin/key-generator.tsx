'use client'

import { useActionState } from 'react'
import { KeyRound } from 'lucide-react'
import { generateKeys, type GenerateState } from '@/app/actions/admin'
import { CopyKey } from '@/components/copy-key'
import { PRODUCTS } from '@/lib/products'

const fieldClass =
  'w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring'

export function KeyGenerator() {
  const [state, action, pending] = useActionState<GenerateState, FormData>(generateKeys, {})

  return (
    <section aria-labelledby="generator-title" className="rounded-2xl border border-border bg-card p-6">
      <div className="flex items-center gap-2">
        <KeyRound className="size-5 text-boost" aria-hidden="true" />
        <h2 id="generator-title" className="font-display text-lg font-semibold">
          Générateur de clés
        </h2>
      </div>
      <p className="mt-1 text-sm text-muted-foreground">
        Les achats Stripe génèrent une clé automatiquement. Utilisez ce formulaire pour des clés
        offertes, des giveaways ou des ventes manuelles.
      </p>
      <form action={action} className="mt-5 grid gap-4 md:grid-cols-[1fr_7rem_1.3fr_1.3fr_auto] md:items-end">
        <label className="flex flex-col gap-1.5 text-sm">
          Offre
          <select name="plan" defaultValue="mois" className={fieldClass}>
            {PRODUCTS.map((product) => (
              <option key={product.id} value={product.id}>
                {product.name}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1.5 text-sm">
          Quantité
          <input name="quantity" type="number" min={1} max={50} defaultValue={1} className={fieldClass} />
        </label>
        <label className="flex flex-col gap-1.5 text-sm">
          E-mail client (optionnel)
          <input name="email" type="email" className={fieldClass} />
        </label>
        <label className="flex flex-col gap-1.5 text-sm">
          Note (optionnel)
          <input name="note" placeholder="Giveaway Discord…" className={fieldClass} />
        </label>
        <button
          type="submit"
          disabled={pending}
          className="rounded-md bg-primary px-4 py-2 font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-60"
        >
          {pending ? 'Génération…' : 'Générer'}
        </button>
      </form>
      {state.error && (
        <p role="alert" className="mt-4 text-sm text-destructive">
          {state.error}
        </p>
      )}
      {state.keys && state.keys.length > 0 && (
        <div className="mt-5 flex flex-col gap-2" aria-live="polite">
          <p className="text-sm font-medium">
            {state.keys.length} clé{state.keys.length > 1 ? 's' : ''} générée{state.keys.length > 1 ? 's' : ''} :
          </p>
          <ul className="flex flex-col gap-2">
            {state.keys.map((key) => (
              <li key={key}>
                <CopyKey value={key} />
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}
