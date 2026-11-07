import { CreditCard, Mail, Download, KeyRound } from 'lucide-react'

const steps = [
  {
    icon: CreditCard,
    title: 'Choisissez une offre',
    description: 'Paiement sécurisé par carte en quelques secondes.',
  },
  {
    icon: Mail,
    title: 'Recevez votre clé',
    description: 'Votre clé de licence unique est envoyée par e-mail immédiatement.',
  },
  {
    icon: Download,
    title: 'Téléchargez le .exe',
    description: "Installez Onyx Client sur Windows 10 ou 11 depuis le lien reçu.",
  },
  {
    icon: KeyRound,
    title: 'Activez et jouez',
    description: "Entrez votre clé au lancement de l'application pour débloquer les macros.",
  },
]

export function HowItWorks() {
  return (
    <section id="fonctionnement" className="scroll-mt-16 border-y border-border bg-card/40 py-20 md:py-28">
      <div className="mx-auto max-w-6xl px-4 md:px-6">
        <div className="max-w-2xl">
          <p className="text-sm font-semibold tracking-widest text-boost uppercase">Fonctionnement</p>
          <h2 className="mt-3 font-display text-3xl font-bold text-balance md:text-4xl">
            Prêt en 4 étapes
          </h2>
        </div>
        <ol className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {steps.map(({ icon: Icon, title, description }, index) => (
            <li key={title} className="flex flex-col gap-3">
              <div className="flex items-center gap-3">
                <span className="font-display text-4xl font-bold text-primary/40" aria-hidden="true">
                  {String(index + 1).padStart(2, '0')}
                </span>
                <Icon className="size-5 text-boost" aria-hidden="true" />
              </div>
              <h3 className="font-display text-lg font-semibold">{title}</h3>
              <p className="text-sm leading-relaxed text-muted-foreground">{description}</p>
            </li>
          ))}
        </ol>

        <div className="mt-14 rounded-xl border border-border bg-background p-5 md:p-6">
          <p className="text-xs font-medium text-muted-foreground">Aperçu de l&apos;activation</p>
          <div className="mt-3 flex flex-col gap-3 sm:flex-row">
            <div
              className="flex-1 rounded-md border border-input bg-secondary/50 px-4 py-3 font-mono text-sm tracking-widest text-muted-foreground"
              aria-label="Exemple de format de clé"
            >
              ONYX-XXXX-XXXX-XXXX
            </div>
            <span className="inline-flex items-center justify-center rounded-md bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground">
              Activer
            </span>
          </div>
        </div>
      </div>
    </section>
  )
}
