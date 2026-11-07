import Link from 'next/link'
import { ArrowLeft } from 'lucide-react'
import { SiteFooter } from '@/components/site-footer'

export type LegalSection = {
  title: string
  paragraphs: string[]
}

export function LegalPage({
  eyebrow,
  title,
  updatedAt,
  intro,
  sections,
  otherDoc,
}: {
  eyebrow: string
  title: string
  updatedAt: string
  intro: string
  sections: LegalSection[]
  otherDoc: { href: string; label: string }
}) {
  return (
    <>
      <main className="mx-auto flex max-w-3xl flex-col gap-10 px-4 py-12 md:px-6">
        <Link
          href="/"
          className="flex w-fit items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="size-4" aria-hidden="true" />
          Retour à l&apos;accueil
        </Link>

        <header className="flex flex-col gap-3">
          <p className="text-sm font-semibold tracking-widest text-boost uppercase">{eyebrow}</p>
          <h1 className="font-display text-3xl font-bold text-balance md:text-4xl">{title}</h1>
          <p className="text-sm text-muted-foreground">Dernière mise à jour : {updatedAt}</p>
          <p className="leading-relaxed text-muted-foreground text-pretty">{intro}</p>
        </header>

        <nav aria-label="Sommaire" className="rounded-2xl border border-border bg-card p-5">
          <p className="mb-3 text-sm font-semibold">Sommaire</p>
          <ol className="flex flex-col gap-1.5 text-sm">
            {sections.map((section, index) => (
              <li key={section.title}>
                <a
                  href={`#article-${index + 1}`}
                  className="text-muted-foreground transition-colors hover:text-foreground"
                >
                  Article {index + 1} — {section.title}
                </a>
              </li>
            ))}
          </ol>
        </nav>

        <div className="flex flex-col gap-8">
          {sections.map((section, index) => (
            <section key={section.title} id={`article-${index + 1}`} className="scroll-mt-24">
              <h2 className="font-display text-xl font-semibold">
                Article {index + 1} — {section.title}
              </h2>
              <div className="mt-3 flex flex-col gap-3">
                {section.paragraphs.map((paragraph) => (
                  <p key={paragraph} className="leading-relaxed text-muted-foreground">
                    {paragraph}
                  </p>
                ))}
              </div>
            </section>
          ))}
        </div>

        <p className="border-t border-border pt-6 text-sm text-muted-foreground">
          Voir aussi :{' '}
          <Link href={otherDoc.href} className="text-boost underline-offset-4 hover:underline">
            {otherDoc.label}
          </Link>
        </p>
      </main>
      <SiteFooter />
    </>
  )
}
