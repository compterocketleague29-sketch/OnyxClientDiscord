'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { ShieldCheck } from 'lucide-react'
import { authClient } from '@/lib/auth-client'

const inputClass =
  'w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring'

export function AdminAuthForm({ mode }: { mode: 'sign-in' | 'sign-up' }) {
  const router = useRouter()
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)
  const isSignUp = mode === 'sign-up'

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setPending(true)
    const form = new FormData(event.currentTarget)
    const email = String(form.get('email'))
    const password = String(form.get('password'))

    const { error } = isSignUp
      ? await authClient.signUp.email({ email, password, name: String(form.get('name') || 'Admin') })
      : await authClient.signIn.email({ email, password })

    setPending(false)
    if (error) {
      setError(isSignUp ? 'Impossible de créer le compte.' : 'Identifiants incorrects.')
      return
    }
    router.push('/admin')
    router.refresh()
  }

  return (
    <form onSubmit={onSubmit} className="flex w-full max-w-sm flex-col gap-4 rounded-2xl border border-border bg-card p-8">
      <div className="flex flex-col items-center gap-2 text-center">
        <span className="flex size-10 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <ShieldCheck className="size-5" aria-hidden="true" />
        </span>
        <h1 className="font-display text-xl font-bold">
          {isSignUp ? 'Créer le compte admin' : 'Espace admin'}
        </h1>
        <p className="text-sm text-muted-foreground">
          {isSignUp
            ? 'Premier lancement : ce compte sera le seul administrateur.'
            : 'Connectez-vous pour gérer les clés.'}
        </p>
      </div>
      {isSignUp && (
        <label className="flex flex-col gap-1.5 text-sm">
          Nom
          <input name="name" autoComplete="name" className={inputClass} />
        </label>
      )}
      <label className="flex flex-col gap-1.5 text-sm">
        E-mail
        <input name="email" type="email" required autoComplete="email" className={inputClass} />
      </label>
      <label className="flex flex-col gap-1.5 text-sm">
        Mot de passe
        <input
          name="password"
          type="password"
          required
          minLength={8}
          autoComplete={isSignUp ? 'new-password' : 'current-password'}
          className={inputClass}
        />
      </label>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      <button
        type="submit"
        disabled={pending}
        className="rounded-md bg-primary px-4 py-2.5 font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-60"
      >
        {pending ? 'Patientez…' : isSignUp ? 'Créer le compte' : 'Se connecter'}
      </button>
    </form>
  )
}
