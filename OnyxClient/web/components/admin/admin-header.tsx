'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import Image from 'next/image'
import { LogOut } from 'lucide-react'
import { authClient } from '@/lib/auth-client'

export function AdminHeader({ email }: { email: string }) {
  const router = useRouter()

  async function signOut() {
    await authClient.signOut()
    router.push('/admin/login')
    router.refresh()
  }

  return (
    <header className="border-b border-border bg-card/50">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 md:px-6">
        <Link href="/" className="flex items-center gap-2 font-display text-lg font-bold">
          <Image
            src="/images/onyx-logo.png"
            alt=""
            width={40}
            height={40}
            className="size-10 mix-blend-lighten"
          />
          Onyx Client <span className="text-sm font-medium text-muted-foreground">/ admin</span>
        </Link>
        <div className="flex items-center gap-4">
          <span className="hidden text-sm text-muted-foreground sm:inline">{email}</span>
          <button
            type="button"
            onClick={signOut}
            className="flex items-center gap-2 rounded-md border border-border px-3 py-1.5 text-sm transition-colors hover:bg-secondary"
          >
            <LogOut className="size-4" aria-hidden="true" />
            Déconnexion
          </button>
        </div>
      </div>
    </header>
  )
}
