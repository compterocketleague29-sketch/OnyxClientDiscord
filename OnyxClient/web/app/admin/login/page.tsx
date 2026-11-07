import { redirect } from 'next/navigation'
import { AdminAuthForm } from '@/components/admin/auth-form'
import { getSession } from '@/lib/auth'

export const metadata = { title: 'Connexion admin — Onyx Client' }

export default async function AdminLoginPage() {
  const session = await getSession()
  if (session?.user) redirect(session.user.role === 'admin' ? '/admin' : '/compte')

  return (
    <main className="flex min-h-svh items-center justify-center px-4">
      <AdminAuthForm mode="sign-in" />
    </main>
  )
}
