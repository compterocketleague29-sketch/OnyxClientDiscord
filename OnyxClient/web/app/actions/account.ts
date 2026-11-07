'use server'

import { desc, eq } from 'drizzle-orm'
import { getSession } from '@/lib/auth'
import { db } from '@/lib/db'
import { licenseKeys } from '@/lib/db/schema'
import { getProduct } from '@/lib/products'

async function getUserId() {
  const session = await getSession()
  if (!session?.user) throw new Error('Unauthorized')
  return session.user.id
}

export async function getMyLicenses() {
  const userId = await getUserId()
  return db
    .select({
      id: licenseKeys.id,
      key: licenseKeys.key,
      plan: licenseKeys.plan,
      status: licenseKeys.status,
      hwid: licenseKeys.hwid,
      activatedAt: licenseKeys.activatedAt,
      expiresAt: licenseKeys.expiresAt,
      createdAt: licenseKeys.createdAt,
    })
    .from(licenseKeys)
    .where(eq(licenseKeys.userId, userId))
    .orderBy(desc(licenseKeys.createdAt))
}

export type KeyCheckResult =
  | { ok: false; message: string }
  | {
      ok: true
      state: 'valid' | 'not_activated' | 'expired' | 'revoked'
      planName: string
      expiresAt: string | null
      devicesUsed: number
      maxDevices: number
    }

/** Read-only status check: never binds a device or starts the license timer. */
export async function checkLicenseKey(_: KeyCheckResult | null, formData: FormData): Promise<KeyCheckResult> {
  await getUserId()

  const raw = formData.get('key')
  const key = typeof raw === 'string' ? raw.trim().toUpperCase() : ''
  if (!key || key.length > 64) return { ok: false, message: 'Entrez une clé valide.' }

  const [license] = await db.select().from(licenseKeys).where(eq(licenseKeys.key, key)).limit(1)
  if (!license) return { ok: false, message: 'Cette clé n’existe pas. Vérifiez la saisie.' }

  const product = getProduct(license.plan)
  const devicesUsed = license.hwid ? license.hwid.split(',').length : 0
  const base = {
    ok: true as const,
    planName: product?.name ?? license.plan,
    expiresAt: license.expiresAt?.toISOString() ?? null,
    devicesUsed,
    maxDevices: product?.maxDevices ?? 1,
  }

  if (license.status !== 'active') return { ...base, state: 'revoked' }
  if (license.expiresAt && license.expiresAt < new Date()) return { ...base, state: 'expired' }
  if (!license.activatedAt) return { ...base, state: 'not_activated' }
  return { ...base, state: 'valid' }
}
