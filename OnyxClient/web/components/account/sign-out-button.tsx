'use client'

import { useRouter } from 'next/navigation'
import { authClient } from '@/lib/auth-client'

export function SignOutButton() {
  const router = useRouter()
  return (
    <button
      type="button"
      onClick={async () => {
        await authClient.signOut()
        router.push('/')
        router.refresh()
      }}
      className="rounded-md px-4 py-2 text-sm font-semibold text-muted-foreground transition-colors hover:text-foreground"
    >
      Déconnexion
    </button>
  )
}
