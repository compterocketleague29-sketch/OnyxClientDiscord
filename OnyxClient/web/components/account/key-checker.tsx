'use client'

import { useActionState } from 'react'
import { CircleAlert, CircleCheck, CircleDashed, CircleX, Loader2 } from 'lucide-react'
import { checkLicenseKey, type KeyCheckResult } from '@/app/actions/account'

const states = {
  valid: { label: 'Clé active', icon: CircleCheck, tone: 'text-primary', text: 'Cette clé fonctionne dans le logiciel.' },
  not_activated: {
    label: 'Prête à activer',
    icon: CircleDashed,
    tone: 'text-primary',
    text: 'Clé valide, pas encore utilisée. La durée démarre à la première activation dans OnyxClient.exe.',
  },
  expired: { label: 'Expirée', icon: CircleX, tone: 'text-destructive', text: 'La durée de cette clé est terminée.' },
  revoked: { label: 'Désactivée', icon: CircleX, tone: 'text-destructive', text: 'Cette clé a été désactivée par le support.' },
} as const

const dateFormat = new Intl.DateTimeFormat('fr-FR', { dateStyle: 'long', timeStyle: 'short' })

export function KeyChecker({ defaultKey = '' }: { defaultKey?: string }) {
  const [result, action, pending] = useActionState<KeyCheckResult | null, FormData>(checkLicenseKey, null)

  return (
    <section aria-labelledby="checker-title" className="flex flex-col gap-5 rounded-xl border border-border bg-card p-6">
      <div className="flex flex-col gap-1">
        <h2 id="checker-title" className="font-display text-xl font-bold">
          Aperçu de l&apos;activation
        </h2>
        <p className="text-sm leading-relaxed text-muted-foreground">
          Vérifiez qu&apos;une clé fonctionne avant de lancer le logiciel. La vérification n&apos;active pas la clé.
        </p>
      </div>

      <form action={action} className="flex flex-col gap-3 sm:flex-row">
        <label htmlFor="key" className="sr-only">
          Clé de licence
        </label>
        <input
          id="key"
          name="key"
          required
          defaultValue={defaultKey}
          placeholder="ONYX-XXXX-XXXX-XXXX-XXXX"
          autoComplete="off"
          spellCheck={false}
          className="h-11 flex-1 rounded-md border border-input bg-background px-3 font-mono text-sm uppercase tracking-wider outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
        <button
          type="submit"
          disabled={pending}
          className="flex h-11 items-center justify-center gap-2 rounded-md bg-primary px-5 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-60"
        >
          {pending && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
          Vérifier
        </button>
      </form>

      <div aria-live="polite">
        {result && !result.ok && (
          <p className="flex items-center gap-2 text-sm text-destructive">
            <CircleAlert className="size-4 shrink-0" aria-hidden="true" />
            {result.message}
          </p>
        )}
        {result?.ok && <KeyStatus result={result} />}
      </div>
    </section>
  )
}

function KeyStatus({ result }: { result: Extract<KeyCheckResult, { ok: true }> }) {
  const state = states[result.state]
  const Icon = state.icon
  return (
    <div className="flex flex-col gap-4 rounded-lg border border-border bg-background p-4">
      <div className="flex items-start gap-3">
        <Icon className={`mt-0.5 size-5 shrink-0 ${state.tone}`} aria-hidden="true" />
        <div className="flex flex-col gap-1">
          <p className={`font-semibold ${state.tone}`}>{state.label}</p>
          <p className="text-sm leading-relaxed text-muted-foreground">{state.text}</p>
        </div>
      </div>
      <dl className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-3">
        <div className="flex flex-col gap-0.5">
          <dt className="text-muted-foreground">Offre</dt>
          <dd className="font-semibold">{result.planName}</dd>
        </div>
        <div className="flex flex-col gap-0.5">
          <dt className="text-muted-foreground">Expiration</dt>
          <dd className="font-semibold">
            {result.expiresAt
              ? dateFormat.format(new Date(result.expiresAt))
              : result.state === 'not_activated'
                ? 'À la 1re activation'
                : 'Jamais (à vie)'}
          </dd>
        </div>
        <div className="flex flex-col gap-0.5">
          <dt className="text-muted-foreground">PC liés</dt>
          <dd className="font-semibold">
            {result.devicesUsed} / {result.maxDevices}
          </dd>
        </div>
      </dl>
    </div>
  )
}
