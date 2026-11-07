import { redirect } from 'next/navigation'
import { CustomerAuthForm } from '@/components/account/customer-auth-form'
import { getSession } from '@/lib/auth'
import { safeRedirect } from '@/lib/safe-redirect'

export const metadata = { title: 'Créer un compte — Onyx Client' }

export default async function InscriptionPage({
  searchParams,
}: {
  searchParams: Promise<{ redirect?: string }>
}) {
  const redirectTo = safeRedirect((await searchParams).redirect)
  const session = await getSession()
  if (session?.user) redirect(redirectTo)

  return (
    <main className="flex min-h-svh items-center justify-center px-4">
      <CustomerAuthForm mode="sign-up" redirectTo={redirectTo} />
    </main>
  )
}
