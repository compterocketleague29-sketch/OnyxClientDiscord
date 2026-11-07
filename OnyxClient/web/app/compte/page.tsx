import type { Metadata } from 'next'
import Link from 'next/link'
import { redirect } from 'next/navigation'
import { ArrowLeft, Download, KeyRound } from 'lucide-react'
import { getMyLicenses } from '@/app/actions/account'
import { KeyChecker } from '@/components/account/key-checker'
import { SignOutButton } from '@/components/account/sign-out-button'
import { CopyKey } from '@/components/copy-key'
import { getSession } from '@/lib/auth'
import { DOWNLOAD_URL } from '@/lib/download'
import { getProduct } from '@/lib/products'

export const metadata: Metadata = { title: 'Mon compte — Onyx Client' }

const dateFormat = new Intl.DateTimeFormat('fr-FR', { dateStyle: 'medium' })

export default async function AccountPage() {
  const session = await getSession()
  if (!session?.user) redirect('/connexion?redirect=/compte')

  const licenses = await getMyLicenses()

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-3xl flex-col gap-8 px-4 py-10 md:px-6">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-col gap-2">
          <Link href="/" className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
            <ArrowLeft className="size-4" aria-hidden="true" />
            Retour au site
          </Link>
          <h1 className="font-display text-3xl font-bold">Mon compte</h1>
          <p className="text-sm text-muted-foreground">{session.user.email}</p>
        </div>
        <div className="flex items-center gap-3">
          {session.user.role === 'admin' && (
            <Link
              href="/admin"
              className="rounded-md border border-border px-4 py-2 text-sm font-semibold transition-colors hover:bg-secondary"
            >
              Panel admin
            </Link>
          )}
          <SignOutButton />
        </div>
      </header>

      <KeyChecker defaultKey={licenses[0]?.key} />

      <section aria-labelledby="keys-title" className="flex flex-col gap-4">
        <div className="flex items-center justify-between gap-4">
          <h2 id="keys-title" className="font-display text-xl font-bold">
            Mes clés
          </h2>
          <a
            href={DOWNLOAD_URL}
            download
            className="flex items-center gap-2 text-sm font-semibold text-primary underline-offset-4 hover:underline"
          >
            <Download className="size-4" aria-hidden="true" />
            Télécharger OnyxClient.exe
          </a>
        </div>

        {licenses.length === 0 ? (
          <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed border-border p-10 text-center">
            <KeyRound className="size-6 text-muted-foreground" aria-hidden="true" />
            <p className="text-sm text-muted-foreground">Vous n&apos;avez pas encore de clé.</p>
            <Link
              href="/#tarifs"
              className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90"
            >
              Voir les offres
            </Link>
          </div>
        ) : (
          <ul className="flex flex-col gap-3">
            {licenses.map((license) => {
              const product = getProduct(license.plan)
              return (
                <li key={license.id} className="flex flex-col gap-3 rounded-xl border border-border bg-card p-5">
                  <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                    <span className="font-semibold">{product?.name ?? license.plan}</span>
                    <span className="text-muted-foreground">Achetée le {dateFormat.format(license.createdAt)}</span>
                  </div>
                  <CopyKey value={license.key} />
                </li>
              )
            })}
          </ul>
        )}
      </section>
    </main>
  )
}
