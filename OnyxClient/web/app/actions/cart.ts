'use server'

import { revalidatePath } from 'next/cache'
import { MAX_QTY_PER_ITEM, readCartQuantities, writeCartQuantities } from '@/lib/cart'
import { getProduct } from '@/lib/products'

export async function addToCart(productId: string) {
  const product = getProduct(productId)
  if (!product) return { ok: false as const }
  const quantities = await readCartQuantities()
  quantities[product.id] = Math.min((quantities[product.id] ?? 0) + 1, MAX_QTY_PER_ITEM)
  await writeCartQuantities(quantities)
  revalidatePath('/', 'layout')
  return { ok: true as const }
}

export async function setCartQuantity(productId: string, quantity: number) {
  const product = getProduct(productId)
  if (!product || !Number.isInteger(quantity)) return
  const quantities = await readCartQuantities()
  if (quantity <= 0) delete quantities[product.id]
  else quantities[product.id] = Math.min(quantity, MAX_QTY_PER_ITEM)
  await writeCartQuantities(quantities)
  revalidatePath('/', 'layout')
}

export async function clearCart() {
  await writeCartQuantities({})
  revalidatePath('/', 'layout')
}
