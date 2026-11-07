import type { Metadata } from 'next'
import Link from 'next/link'
import { redirect } from 'next/navigation'
import { ArrowLeft } from 'lucide-react'
import { Checkout } from '@/components/checkout'
import { getSession } from '@/lib/auth'
import { getCart } from '@/lib/cart'
import { formatPrice } from '@/lib/products'

export const metadata: Metadata = { title: 'Paiement — Onyx Client' }

export default async function PaiementPage() {
  const session = await getSession()
  if (!session?.user) redirect(`/inscription?redirect=${encodeURIComponent('/paiement')}`)

  const cart = await getCart()
  if (cart.lines.length === 0) redirect('/panier')

  return (
    <main className="mx-auto grid min-h-svh max-w-6xl gap-10 px-4 py-12 md:px-6 lg:grid-cols-[1fr_1.4fr]">
      <section className="flex flex-col gap-6">
        <Link
          href="/panier"
          className="flex w-fit items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="size-4" aria-hidden="true" />
          Modifier le panier
        </Link>
        <div>
          <p className="text-sm font-semibold tracking-widest text-boost uppercase">Votre commande</p>
          <h1 className="mt-2 font-display text-3xl font-bold">Paiement sécurisé</h1>
        </div>
        <ul className="flex flex-col divide-y divide-border rounded-2xl border border-border bg-card">
          {cart.lines.map((line) => (
            <li key={line.product.id} className="flex items-center justify-between gap-4 p-4 text-sm">
              <span>
                <span className="font-semibold text-foreground">{line.quantity} ×</span> Licence {line.product.name}
              </span>
              <span className="font-semibold tabular-nums">{formatPrice(line.subtotalCents)}</span>
            </li>
          ))}
          <li className="flex items-baseline justify-between p-4">
            <span className="text-muted-foreground">Total</span>
            <span className="font-display text-2xl font-bold tabular-nums">{formatPrice(cart.totalCents)}</span>
          </li>
        </ul>
        <p className="rounded-lg border border-border bg-card p-4 text-sm text-muted-foreground">
          Connecté en tant que <span className="font-semibold text-foreground">{session.user.email}</span>. Chaque
          licence reçoit sa propre clé unique, affichée après le paiement et disponible dans votre compte.
        </p>
      </section>
      <section aria-label="Paiement">
        <Checkout />
      </section>
    </main>
  )
}
