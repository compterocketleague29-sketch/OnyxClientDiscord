import { redirect } from 'next/navigation'
import { CustomerAuthForm } from '@/components/account/customer-auth-form'
import { getSession } from '@/lib/auth'
import { safeRedirect } from '@/lib/safe-redirect'

export const metadata = { title: 'Connexion — Onyx Client' }

export default async function ConnexionPage({
  searchParams,
}: {
  searchParams: Promise<{ redirect?: string }>
}) {
  const redirectTo = safeRedirect((await searchParams).redirect)
  const session = await getSession()
  if (session?.user) redirect(redirectTo)

  return (
    <main className="flex min-h-svh items-center justify-center px-4">
      <CustomerAuthForm mode="sign-in" redirectTo={redirectTo} />
    </main>
  )
}
