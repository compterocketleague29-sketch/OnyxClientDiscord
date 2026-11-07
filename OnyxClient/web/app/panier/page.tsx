import type { Metadata } from 'next'
import Link from 'next/link'
import { ArrowLeft, ShoppingCart } from 'lucide-react'
import { CartLineControls } from '@/components/cart/cart-line-controls'
import { getSession } from '@/lib/auth'
import { getCart, MAX_QTY_PER_ITEM } from '@/lib/cart'
import { formatPrice } from '@/lib/products'

export const metadata: Metadata = { title: 'Panier — Onyx Client' }

export default async function PanierPage() {
  const [cart, session] = await Promise.all([getCart(), getSession()])
  const checkoutHref = session?.user
    ? '/paiement'
    : `/inscription?redirect=${encodeURIComponent('/paiement')}`

  return (
    <main className="mx-auto flex min-h-svh max-w-3xl flex-col gap-8 px-4 py-12 md:px-6">
      <Link
        href="/#tarifs"
        className="flex w-fit items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="size-4" aria-hidden="true" />
        Continuer mes achats
      </Link>

      <div>
        <p className="text-sm font-semibold tracking-widest text-boost uppercase">Panier</p>
        <h1 className="mt-2 font-display text-3xl font-bold">
          {cart.count > 0
            ? `${cart.count} licence${cart.count > 1 ? 's' : ''} dans votre panier`
            : 'Votre panier est vide'}
        </h1>
      </div>

      {cart.lines.length === 0 ? (
        <div className="flex flex-col items-center gap-4 rounded-2xl border border-border bg-card p-10 text-center">
          <ShoppingCart className="size-10 text-muted-foreground" aria-hidden="true" />
          <p className="text-muted-foreground">Ajoutez une ou plusieurs licences pour commencer.</p>
          <Link
            href="/#tarifs"
            className="rounded-md bg-primary px-4 py-2 font-semibold text-primary-foreground transition-opacity hover:opacity-90"
          >
            Voir les offres
          </Link>
        </div>
      ) : (
        <>
          <ul className="flex flex-col divide-y divide-border rounded-2xl border border-border bg-card">
            {cart.lines.map((line) => (
              <li
                key={line.product.id}
                className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="flex flex-col gap-1">
                  <p className="font-display text-lg font-semibold">Licence {line.product.name}</p>
                  <p className="text-sm text-muted-foreground">
                    {formatPrice(line.product.priceInCents)} {line.product.period} · 1 clé unique par licence
                  </p>
                </div>
                <div className="flex items-center justify-between gap-6">
                  <CartLineControls
                    productId={line.product.id}
                    productName={line.product.name}
                    quantity={line.quantity}
                    max={MAX_QTY_PER_ITEM}
                  />
                  <p className="w-20 text-right font-semibold tabular-nums">{formatPrice(line.subtotalCents)}</p>
                </div>
              </li>
            ))}
          </ul>

          <div className="flex flex-col gap-4 rounded-2xl border border-border bg-card p-6">
            <div className="flex items-baseline justify-between">
              <span className="text-muted-foreground">Total</span>
              <span className="font-display text-3xl font-bold tabular-nums">{formatPrice(cart.totalCents)}</span>
            </div>
            <p className="text-sm text-muted-foreground">
              {session?.user
                ? `Connecté en tant que ${session.user.email}. Vos clés s'afficheront après le paiement.`
                : 'Un compte est nécessaire pour commander : vos clés y seront enregistrées.'}
            </p>
            <Link
              href={checkoutHref}
              className="rounded-md bg-primary px-4 py-3 text-center font-semibold text-primary-foreground transition-opacity hover:opacity-90"
            >
              {session?.user ? 'Passer au paiement' : 'Créer un compte et payer'}
            </Link>
            <p className="text-xs leading-relaxed text-muted-foreground">
              En passant au paiement, vous acceptez les{' '}
              <Link href="/cgv" className="text-foreground underline underline-offset-4">
                CGV
              </Link>{' '}
              et les{' '}
              <Link href="/cgu" className="text-foreground underline underline-offset-4">
                CGU
              </Link>
              , demandez la livraison immédiate de vos clés et renoncez à votre droit de rétractation dès leur
              délivrance.
            </p>
          </div>
        </>
      )}
    </main>
  )
}
