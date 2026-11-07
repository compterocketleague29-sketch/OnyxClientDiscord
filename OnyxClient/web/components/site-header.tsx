import Link from 'next/link'
import Image from 'next/image'
import { MessagesSquare, ShoppingCart, UserRound } from 'lucide-react'
import { DISCORD_URL } from '@/lib/site'
import { getSession } from '@/lib/auth'
import { getCart } from '@/lib/cart'

const links = [
  { href: '#fonctionnalites', label: 'Fonctionnalités' },
  { href: '#fonctionnement', label: 'Fonctionnement' },
  { href: '#tarifs', label: 'Tarifs' },
  { href: '#faq', label: 'FAQ' },
]

export async function SiteHeader() {
  const [session, cart] = await Promise.all([getSession(), getCart()])
  return (
    <header className="sticky top-0 z-50 border-b border-border bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 md:px-6">
        <a href="#" className="flex items-center gap-2 font-display text-lg font-bold tracking-wide">
          <Image
            src="/images/onyx-logo.png"
            alt=""
            width={40}
            height={40}
            className="size-10 mix-blend-lighten"
          />
          Onyx Client
        </a>
        <nav aria-label="Navigation principale" className="hidden md:block">
          <ul className="flex items-center gap-8 text-sm text-muted-foreground">
            {links.map((link) => (
              <li key={link.href}>
                <a href={link.href} className="transition-colors hover:text-foreground">
                  {link.label}
                </a>
              </li>
            ))}
          </ul>
        </nav>
        <div className="flex items-center gap-2">
          <a
            href={DISCORD_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 rounded-md px-3 py-2 text-sm font-semibold text-muted-foreground transition-colors hover:text-foreground"
          >
            <MessagesSquare className="size-4" aria-hidden="true" />
            <span className="hidden sm:inline">Discord</span>
            <span className="sr-only sm:hidden">Discord</span>
          </a>
          <Link
            href={session?.user ? '/compte' : '/connexion'}
            className="flex items-center gap-2 rounded-md px-3 py-2 text-sm font-semibold text-muted-foreground transition-colors hover:text-foreground"
          >
            <UserRound className="size-4" aria-hidden="true" />
            <span className="hidden sm:inline">{session?.user ? 'Mon compte' : 'Connexion'}</span>
            <span className="sr-only sm:hidden">{session?.user ? 'Mon compte' : 'Connexion'}</span>
          </Link>
          <Link
            href="/panier"
            className="flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90"
          >
            <ShoppingCart className="size-4" aria-hidden="true" />
            Panier
            {cart.count > 0 && (
              <span className="flex min-w-5 items-center justify-center rounded-full bg-primary-foreground px-1.5 text-xs font-bold text-primary tabular-nums">
                {cart.count}
                <span className="sr-only"> article{cart.count > 1 ? 's' : ''}</span>
              </span>
            )}
          </Link>
        </div>
      </div>
    </header>
  )
}
