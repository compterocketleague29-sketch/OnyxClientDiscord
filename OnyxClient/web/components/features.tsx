import { Infinity as InfinityIcon, Gauge, Wind, RotateCcw, Keyboard, Gamepad2 } from 'lucide-react'

const features = [
  {
    icon: InfinityIcon,
    title: 'Infinite Wavedash',
    description: 'Enchaînez les wavedashs en continu avec un timing parfait à chaque atterrissage.',
  },
  {
    icon: Gauge,
    title: 'Speedflip',
    description: 'Le kickoff le plus rapide, réglé selon votre côté et votre voiture.',
  },
  {
    icon: Wind,
    title: 'Zap Dash & Chain Dash',
    description: 'Des déplacements au sol ultra rapides sans boost, déclenchés en une touche.',
  },
  {
    icon: RotateCcw,
    title: 'Half-flip parfait',
    description: 'Faites demi-tour instantanément avec un cancel au frame près.',
  },
  {
    icon: Keyboard,
    title: 'Bindings libres',
    description: 'Assignez chaque macro à la touche ou au bouton de votre choix.',
  },
  {
    icon: Gamepad2,
    title: 'Manette & clavier',
    description: 'Compatible manettes Xbox, PlayStation et clavier/souris.',
  },
]

export function Features() {
  return (
    <section id="fonctionnalites" className="scroll-mt-16 py-20 md:py-28">
      <div className="mx-auto max-w-6xl px-4 md:px-6">
        <div className="max-w-2xl">
          <p className="text-sm font-semibold tracking-widest text-boost uppercase">Fonctionnalités</p>
          <h2 className="mt-3 font-display text-3xl font-bold text-balance md:text-4xl">
            Toutes les mécaniques avancées, prêtes à l&apos;emploi
          </h2>
        </div>
        <ul className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {features.map(({ icon: Icon, title, description }) => (
            <li
              key={title}
              className="rounded-xl border border-border bg-card p-6 transition-colors hover:border-primary/50"
            >
              <span className="flex size-10 items-center justify-center rounded-lg bg-primary/15 text-primary">
                <Icon className="size-5" aria-hidden="true" />
              </span>
              <h3 className="mt-4 font-display text-lg font-semibold">{title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{description}</p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}
