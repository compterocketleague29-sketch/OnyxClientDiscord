'use server'

import { headers } from 'next/headers'
import { revalidatePath } from 'next/cache'
import { eq } from 'drizzle-orm'
import { auth } from '@/lib/auth'
import { db } from '@/lib/db'
import { licenseKeys } from '@/lib/db/schema'
import { createLicenseKey } from '@/lib/license'
import { getProduct } from '@/lib/products'

async function requireAdmin() {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session?.user || session.user.role !== 'admin') throw new Error('Unauthorized')
  return session.user
}

export type GenerateState = { error?: string; keys?: string[] }

export async function generateKeys(_prev: GenerateState, formData: FormData): Promise<GenerateState> {
  await requireAdmin()

  const product = getProduct(String(formData.get('plan') ?? ''))
  if (!product) return { error: 'Offre invalide' }

  const quantity = Number(formData.get('quantity') ?? 1)
  if (!Number.isInteger(quantity) || quantity < 1 || quantity > 50) {
    return { error: 'La quantité doit être comprise entre 1 et 50' }
  }

  const email = String(formData.get('email') ?? '').trim().slice(0, 200) || null
  const note = String(formData.get('note') ?? '').trim().slice(0, 300) || null

  const keys: string[] = []
  for (let i = 0; i < quantity; i++) {
    const row = await createLicenseKey({ plan: product.id, email, note, source: 'admin' })
    keys.push(row.key)
  }

  revalidatePath('/admin')
  return { keys }
}

function parseId(formData: FormData) {
  const id = Number(formData.get('id'))
  if (!Number.isInteger(id) || id < 1) throw new Error('ID invalide')
  return id
}

export async function setKeyStatus(formData: FormData) {
  await requireAdmin()
  const status = formData.get('status') === 'revoked' ? 'revoked' : 'active'
  await db.update(licenseKeys).set({ status }).where(eq(licenseKeys.id, parseId(formData)))
  revalidatePath('/admin')
}

export async function resetHwid(formData: FormData) {
  await requireAdmin()
  await db.update(licenseKeys).set({ hwid: null }).where(eq(licenseKeys.id, parseId(formData)))
  revalidatePath('/admin')
}

export async function deleteKey(formData: FormData) {
  await requireAdmin()
  await db.delete(licenseKeys).where(eq(licenseKeys.id, parseId(formData)))
  revalidatePath('/admin')
}
