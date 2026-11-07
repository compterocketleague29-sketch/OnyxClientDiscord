import 'server-only'
import { randomInt } from 'node:crypto'
import { asc, eq, sql } from 'drizzle-orm'
import { db } from '@/lib/db'
import { licenseKeys } from '@/lib/db/schema'
import { parseSerializedCart } from '@/lib/cart'
import { getProduct, type PlanId } from '@/lib/products'
import { stripe } from '@/lib/stripe'

const ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'

type Executor = Pick<typeof db, 'insert'>

export function generateLicenseKey() {
  const groups = Array.from({ length: 4 }, () =>
    Array.from({ length: 4 }, () => ALPHABET[randomInt(ALPHABET.length)]).join(''),
  )
  return `ONYX-${groups.join('-')}`
}

export async function createLicenseKey(
  input: {
    plan: PlanId
    email?: string | null
    note?: string | null
    source: 'stripe' | 'admin'
    stripeSessionId?: string
    amountCents?: number | null
    userId?: string | null
  },
  executor: Executor = db,
) {
  for (let attempt = 0; attempt < 5; attempt++) {
    const [row] = await executor
      .insert(licenseKeys)
      .values({
        key: generateLicenseKey(),
        plan: input.plan,
        email: input.email ?? null,
        note: input.note ?? null,
        source: input.source,
        stripeSessionId: input.stripeSessionId ?? null,
        amountCents: input.amountCents ?? null,
        userId: input.userId ?? null,
      })
      .onConflictDoNothing()
      .returning()
    if (row) return row
  }
  throw new Error('Impossible de générer une clé unique')
}

/**
 * Idempotent: a paid Stripe session produces one key per purchased unit,
 * exactly once. The advisory lock serializes concurrent refreshes of the
 * success page so they cannot both generate keys. Only the buyer can see them.
 */
export async function fulfillCheckoutSession(sessionId: string, userId: string) {
  return db.transaction(async (tx) => {
    await tx.execute(sql`select pg_advisory_xact_lock(hashtext(${sessionId}))`)

    const existing = await tx
      .select()
      .from(licenseKeys)
      .where(eq(licenseKeys.stripeSessionId, sessionId))
      .orderBy(asc(licenseKeys.id))
    if (existing.length > 0) {
      return existing.every((row) => row.userId === userId) ? existing : null
    }

    const session = await stripe.checkout.sessions.retrieve(sessionId)
    if (session.payment_status !== 'paid') return null
    if (session.metadata?.userId !== userId) return null

    const quantities = session.metadata?.cart
      ? parseSerializedCart(session.metadata.cart)
      : session.metadata?.plan
        ? parseSerializedCart(`${session.metadata.plan}:1`)
        : {}

    const created = []
    for (const [id, quantity] of Object.entries(quantities)) {
      const product = getProduct(id)
      if (!product || !quantity) continue
      for (let i = 0; i < quantity; i++) {
        created.push(
          await createLicenseKey(
            {
              plan: product.id,
              email: session.customer_details?.email ?? null,
              source: 'stripe',
              stripeSessionId: session.id,
              amountCents: product.priceInCents,
              userId,
            },
            tx,
          ),
        )
      }
    }
    return created.length > 0 ? created : null
  })
}
