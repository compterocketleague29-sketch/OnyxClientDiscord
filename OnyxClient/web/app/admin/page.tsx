import { redirect } from 'next/navigation'
import { desc } from 'drizzle-orm'
import { AdminHeader } from '@/components/admin/admin-header'
import { AdminStats } from '@/components/admin/admin-stats'
import { KeyGenerator } from '@/components/admin/key-generator'
import { KeysTable } from '@/components/admin/keys-table'
import { getSession } from '@/lib/auth'
import { db } from '@/lib/db'
import { licenseKeys } from '@/lib/db/schema'

export const metadata = { title: 'Admin — Onyx Client' }

export default async function AdminPage() {
  const session = await getSession()
  if (!session?.user) redirect('/admin/login')
  if (session.user.role !== 'admin') redirect('/compte')

  const keys = await db.select().from(licenseKeys).orderBy(desc(licenseKeys.createdAt)).limit(500)

  return (
    <div className="min-h-svh">
      <AdminHeader email={session.user.email} />
      <main className="mx-auto flex max-w-6xl flex-col gap-8 px-4 py-8 md:px-6">
        <AdminStats keys={keys} />
        <KeyGenerator />
        <KeysTable keys={keys} />
      </main>
    </div>
  )
}
