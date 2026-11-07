import Image from 'next/image'
import { Download, KeyRound } from 'lucide-react'

const stats = [
  { value: '< 1 ms', label: "Latence d'input" },
  { value: '12+', label: 'Macros incluses' },
  { value: '100%', label: 'Personnalisable' },
]

export function Hero() {
  return (
    <section className="relative overflow-hidden">
      <div className="absolute inset-0 -z-10">
        <Image
          src="/images/hero-car.png"
          alt=""
          fill
          priority
          className="object-cover opacity-40"
        />
        <div className="absolute inset-0 bg-gradient-to-b from-background/60 via-background/80 to-background" />
      </div>

      <div className="mx-auto flex max-w-6xl items-center gap-12 px-4 pt-24 pb-20 md:px-6 md:pt-32 md:pb-28">
      <div className="flex flex-1 flex-col items-start gap-8">
        <span className="rounded-full border border-boost/40 bg-boost/10 px-3 py-1 text-xs font-medium text-boost">
          Version 2.4 disponible — Windows 10 / 11
        </span>
        <h1 className="max-w-3xl font-display text-4xl leading-tight font-bold text-balance md:text-6xl">
          Des mécaniques <span className="text-primary">pro</span> en une seule touche.
        </h1>
        <p className="max-w-xl text-lg leading-relaxed text-pretty text-muted-foreground">
          Infinite wavedash, speedflip, zap dash, half-flip… Onyx Client exécute les inputs au
          frame près. Téléchargez l&apos;application, entrez votre clé et c&apos;est parti.
        </p>
        <div className="flex flex-wrap gap-3">
          <a
            href="#tarifs"
            className="inline-flex items-center gap-2 rounded-md bg-primary px-6 py-3 font-semibold text-primary-foreground transition-opacity hover:opacity-90"
          >
            <KeyRound className="size-4" aria-hidden="true" />
            Obtenir ma clé
          </a>
          <a
            href="#fonctionnement"
            className="inline-flex items-center gap-2 rounded-md border border-border bg-secondary/60 px-6 py-3 font-semibold transition-colors hover:bg-secondary"
          >
            <Download className="size-4" aria-hidden="true" />
            Comment ça marche
          </a>
        </div>
        <dl className="mt-6 grid w-full max-w-xl grid-cols-3 gap-4 border-t border-border pt-6">
          {stats.map((stat) => (
            <div key={stat.label}>
              <dt className="text-xs text-muted-foreground md:text-sm">{stat.label}</dt>
              <dd className="font-display text-2xl font-bold md:text-3xl">{stat.value}</dd>
            </div>
          ))}
        </dl>
      </div>
      <Image
        src="/images/onyx-logo.png"
        alt="Logo Onyx Client"
        width={420}
        height={420}
        priority
        className="hidden w-96 shrink-0 mix-blend-lighten lg:block"
      />
      </div>
    </section>
  )
}
