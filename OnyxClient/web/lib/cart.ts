import 'server-only'
import { cookies } from 'next/headers'
import { getProduct, PRODUCTS, type PlanId, type Product } from '@/lib/products'

const CART_COOKIE = 'onyx_cart'
export const MAX_QTY_PER_ITEM = 5
export const MAX_ITEMS_TOTAL = 10

export type CartQuantities = Partial<Record<PlanId, number>>

export interface CartLine {
  product: Product
  quantity: number
  subtotalCents: number
}

export interface Cart {
  lines: CartLine[]
  count: number
  totalCents: number
}

// The cookie only ever stores product ids and quantities; prices are always
// recomputed from PRODUCTS so a tampered cookie cannot change what is charged.
export function sanitizeQuantities(raw: unknown): CartQuantities {
  if (!raw || typeof raw !== 'object') return {}
  const result: CartQuantities = {}
  let total = 0
  for (const product of PRODUCTS) {
    const value = (raw as Record<string, unknown>)[product.id]
    if (typeof value !== 'number' || !Number.isInteger(value) || value <= 0) continue
    const quantity = Math.min(value, MAX_QTY_PER_ITEM, MAX_ITEMS_TOTAL - total)
    if (quantity <= 0) break
    result[product.id] = quantity
    total += quantity
  }
  return result
}

export async function readCartQuantities(): Promise<CartQuantities> {
  const store = await cookies()
  const value = store.get(CART_COOKIE)?.value
  if (!value) return {}
  try {
    return sanitizeQuantities(JSON.parse(value))
  } catch {
    return {}
  }
}

export async function writeCartQuantities(quantities: CartQuantities) {
  const store = await cookies()
  const clean = sanitizeQuantities(quantities)
  if (Object.keys(clean).length === 0) {
    store.delete(CART_COOKIE)
    return
  }
  store.set(CART_COOKIE, JSON.stringify(clean), {
    httpOnly: true,
    sameSite: process.env.NODE_ENV === 'development' ? 'none' : 'lax',
    secure: true,
    path: '/',
    maxAge: 60 * 60 * 24 * 7,
  })
}

export function buildCart(quantities: CartQuantities): Cart {
  const lines: CartLine[] = []
  for (const [id, quantity] of Object.entries(quantities)) {
    const product = getProduct(id)
    if (!product || !quantity) continue
    lines.push({ product, quantity, subtotalCents: product.priceInCents * quantity })
  }
  return {
    lines,
    count: lines.reduce((sum, line) => sum + line.quantity, 0),
    totalCents: lines.reduce((sum, line) => sum + line.subtotalCents, 0),
  }
}

export async function getCart() {
  return buildCart(await readCartQuantities())
}

export function serializeCart(quantities: CartQuantities) {
  return Object.entries(quantities)
    .map(([id, quantity]) => `${id}:${quantity}`)
    .join(',')
}

export function parseSerializedCart(value: string): CartQuantities {
  const raw: Record<string, number> = {}
  for (const part of value.split(',')) {
    const [id, quantity] = part.split(':')
    if (id) raw[id] = Number(quantity)
  }
  return sanitizeQuantities(raw)
}
