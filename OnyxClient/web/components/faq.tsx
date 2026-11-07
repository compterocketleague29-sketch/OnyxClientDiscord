import { ChevronDown } from 'lucide-react'

const questions = [
  {
    q: 'Comment je reçois ma clé ?',
    a: "Juste après le paiement, votre clé de licence et le lien de téléchargement du .exe sont envoyés à l'adresse e-mail utilisée lors de l'achat.",
  },
  {
    q: 'Sur combien de PC puis-je utiliser ma clé ?',
    a: "Les offres semaine et mois sont liées à 1 PC. L'offre à vie permet 2 PC. Vous pouvez réinitialiser la liaison depuis le support.",
  },
  {
    q: 'Est-ce compatible manette ?',
    a: 'Oui, Onyx Client fonctionne avec les manettes Xbox, PlayStation et en clavier/souris.',
  },
  {
    q: 'Y a-t-il un risque de bannissement ?',
    a: "L'utilisation de macros peut aller à l'encontre des conditions d'utilisation du jeu, surtout en parties classées et en tournoi. Nous recommandons de les utiliser en freeplay, en entraînement ou en parties privées. Vous restez responsable de votre utilisation.",
  },
  {
    q: 'Puis-je être remboursé ?',
    a: "Une clé non activée peut être remboursée sous 48 h. Contactez-nous sur Discord avec votre numéro de commande.",
  },
]

export function Faq() {
  return (
    <section id="faq" className="scroll-mt-16 border-t border-border py-20 md:py-28">
      <div className="mx-auto max-w-3xl px-4 md:px-6">
        <p className="text-sm font-semibold tracking-widest text-boost uppercase">FAQ</p>
        <h2 className="mt-3 font-display text-3xl font-bold md:text-4xl">Questions fréquentes</h2>
        <div className="mt-10 flex flex-col gap-3">
          {questions.map(({ q, a }) => (
            <details key={q} className="group rounded-xl border border-border bg-card px-5 open:border-primary/40">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 py-4 font-medium [&::-webkit-details-marker]:hidden">
                {q}
                <ChevronDown
                  className="size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180"
                  aria-hidden="true"
                />
              </summary>
              <p className="pb-5 text-sm leading-relaxed text-muted-foreground">{a}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  )
}
