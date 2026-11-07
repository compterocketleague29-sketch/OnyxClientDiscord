import Link from 'next/link'
import { redirect } from 'next/navigation'
import { CircleAlert, CircleCheck, Download } from 'lucide-react'
import { ClearCartOnMount } from '@/components/cart/clear-cart-on-mount'
import { CopyKey } from '@/components/copy-key'
import { getSession } from '@/lib/auth'
import { DOWNLOAD_URL } from '@/lib/download'
import { fulfillCheckoutSession } from '@/lib/license'
import { getProduct } from '@/lib/products'

export const metadata = { title: 'Merci pour votre achat — Onyx Client' }

export default async function MerciPage({
  searchParams,
}: {
  searchParams: Promise<{ session_id?: string }>
}) {
  const { session_id: sessionId } = await searchParams
  const session = await getSession()
  if (!session?.user) {
    redirect(`/connexion?redirect=${encodeURIComponent(`/merci?session_id=${sessionId ?? ''}`)}`)
  }
  const licenses = sessionId
    ? await fulfillCheckoutSession(sessionId, session.user.id).catch((error) => {
        console.error('Fulfillment failed', error)
        return null
      })
    : null

  if (!licenses) {
    return (
      <main className="mx-auto flex min-h-svh max-w-lg flex-col items-center justify-center gap-4 px-4 text-center">
        <CircleAlert className="size-10 text-destructive" aria-hidden="true" />
        <h1 className="font-display text-2xl font-bold">Paiement non confirmé</h1>
        <p className="text-muted-foreground">
          Nous n&apos;avons pas pu confirmer votre paiement. Si vous avez été débité, contactez le
          support sur Discord avec votre reçu Stripe.
        </p>
        <Link href="/panier" className="rounded-md bg-primary px-4 py-2 font-semibold text-primary-foreground">
          Retour au panier
        </Link>
      </main>
    )
  }

  const plural = licenses.length > 1

  return (
    <main className="mx-auto flex min-h-svh max-w-xl flex-col justify-center gap-8 px-4 py-12">
      <ClearCartOnMount />
      <div className="flex flex-col items-center gap-3 text-center">
        <CircleCheck className="size-12 text-boost" aria-hidden="true" />
        <h1 className="font-display text-3xl font-bold">Paiement confirmé</h1>
        <p className="text-muted-foreground">
          {plural
            ? `Voici vos ${licenses.length} clés de licence. Chacune est unique et s'active sur son propre PC.`
            : 'Voici votre clé de licence. Conservez-la précieusement, elle est unique.'}
        </p>
      </div>

      <ul className="flex flex-col gap-4">
        {licenses.map((license) => (
          <li key={license.id} className="flex flex-col gap-2">
            <p className="text-sm font-semibold text-muted-foreground">
              Licence {getProduct(license.plan)?.name ?? license.plan}
            </p>
            <CopyKey value={license.key} />
          </li>
        ))}
      </ul>

      <ol className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-6 text-sm">
        <li>
          <span className="font-semibold text-foreground">1.</span> Téléchargez OnyxClient.exe
        </li>
        <li>
          <span className="font-semibold text-foreground">2.</span> Lancez le logiciel et collez votre clé
        </li>
        <li>
          <span className="font-semibold text-foreground">3.</span> La clé se lie à votre PC à la
          première activation
        </li>
      </ol>

      <a
        href={DOWNLOAD_URL}
        download
        className="flex items-center justify-center gap-2 rounded-md bg-primary px-4 py-3 font-semibold text-primary-foreground transition-opacity hover:opacity-90"
      >
        <Download className="size-4" aria-hidden="true" />
        Télécharger OnyxClient.exe
      </a>
      <Link
        href="/compte"
        className="text-center text-sm font-semibold text-foreground underline-offset-4 hover:underline"
      >
        Voir toutes mes clés dans mon compte
      </Link>
    </main>
  )
}
