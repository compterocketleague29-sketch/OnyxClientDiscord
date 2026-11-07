'use server'

import { randomUUID } from 'node:crypto'
import { headers } from 'next/headers'
import { getSession } from '@/lib/auth'
import { buildCart, readCartQuantities, serializeCart } from '@/lib/cart'
import { stripe } from '@/lib/stripe'

async function getOrigin() {
  const h = await headers()
  const origin = h.get('origin')
  if (origin) return origin
  const host = h.get('x-forwarded-host') ?? h.get('host')
  const proto = h.get('x-forwarded-proto') ?? 'https'
  return `${proto}://${host}`
}

export async function startCheckoutSession() {
  const session = await getSession()
  if (!session?.user) throw new Error('Connexion requise')

  const quantities = await readCartQuantities()
  const cart = buildCart(quantities)
  if (cart.lines.length === 0) throw new Error('Panier vide')

  const origin = await getOrigin()

  const checkout = await stripe.checkout.sessions.create(
    {
      customer_email: session.user.email,
      client_reference_id: session.user.id,
      ui_mode: 'embedded_page',
      redirect_on_completion: 'always',
      return_url: `${origin}/merci?session_id={CHECKOUT_SESSION_ID}`,
      line_items: cart.lines.map((line) => ({
        price_data: {
          currency: 'eur',
          product_data: {
            name: `Licence Onyx Client — ${line.product.name}`,
            description: line.product.description,
          },
          unit_amount: line.product.priceInCents,
        },
        quantity: line.quantity,
      })),
      mode: 'payment',
      metadata: { cart: serializeCart(quantities), userId: session.user.id },
    },
    { idempotencyKey: randomUUID() },
  )

  if (!checkout.client_secret) throw new Error('Session de paiement invalide')
  return checkout.client_secret
}
