import { Check } from 'lucide-react'
import { AddToCartButton } from '@/components/cart/add-to-cart-button'
import { formatPrice, PRODUCTS } from '@/lib/products'
import { cn } from '@/lib/utils'

export function Pricing() {
  return (
    <section id="tarifs" className="scroll-mt-16 py-20 md:py-28">
      <div className="mx-auto max-w-6xl px-4 md:px-6">
        <div className="mx-auto max-w-2xl text-center">
          <p className="text-sm font-semibold tracking-widest text-boost uppercase">Tarifs</p>
          <h2 className="mt-3 font-display text-3xl font-bold text-balance md:text-4xl">
            Choisissez votre clé de licence
          </h2>
          <p className="mt-4 text-muted-foreground">
            Ajoutez une ou plusieurs licences au panier. Chaque licence reçoit sa clé unique dès le paiement.
          </p>
        </div>
        <ul className="mt-12 grid gap-6 lg:grid-cols-3">
          {PRODUCTS.map((plan) => (
            <li
              key={plan.id}
              className={cn(
                'relative flex flex-col rounded-2xl border bg-card p-8',
                plan.highlighted ? 'border-primary shadow-[0_0_40px_-10px] shadow-primary/40' : 'border-border',
              )}
            >
              <span
                className={cn(
                  'absolute -top-3 left-8 rounded-full px-3 py-1 text-xs font-semibold',
                  plan.highlighted
                    ? 'bg-primary text-primary-foreground'
                    : 'border border-primary/50 bg-card text-foreground',
                )}
              >
                {plan.badge}
              </span>
              <h3 className="font-display text-xl font-semibold">{plan.name}</h3>
              <p className="mt-1 text-sm text-muted-foreground">{plan.description}</p>
              <p className="mt-6 flex items-baseline gap-2">
                <span className="font-display text-4xl font-bold">{formatPrice(plan.priceInCents)}</span>
                <span className="text-sm text-muted-foreground">{plan.period}</span>
              </p>
              <ul className="mt-6 flex flex-1 flex-col gap-3 text-sm">
                {plan.features.map((feature) => (
                  <li key={feature} className="flex items-center gap-2">
                    <Check className="size-4 shrink-0 text-boost" aria-hidden="true" />
                    {feature}
                  </li>
                ))}
              </ul>
              <AddToCartButton productId={plan.id} label={plan.name} highlighted={plan.highlighted} />
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}
