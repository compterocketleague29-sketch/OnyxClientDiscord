import Link from 'next/link'
import { DISCORD_URL } from '@/lib/site'

export function SiteFooter() {
  return (
    <footer className="border-t border-border py-10">
      <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 text-sm text-muted-foreground md:flex-row md:items-center md:justify-between md:px-6">
        <div className="flex flex-col gap-2">
          <p>&copy; {new Date().getFullYear()} Onyx Client. Tous droits réservés.</p>
          <nav aria-label="Informations légales" className="flex gap-4">
            <Link href="/cgv" className="transition-colors hover:text-foreground">
              CGV
            </Link>
            <Link href="/cgu" className="transition-colors hover:text-foreground">
              CGU
            </Link>
            <a
              href={DISCORD_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="transition-colors hover:text-foreground"
            >
              Discord
            </a>
          </nav>
        </div>
        <p className="max-w-md text-xs leading-relaxed">
          Onyx Client n&apos;est ni affilié ni approuvé par Psyonix ou Epic Games. Rocket League est une
          marque déposée de Psyonix LLC.
        </p>
      </div>
    </footer>
  )
}
