export type PlanId = 'semaine' | 'mois' | 'vie'

export interface Product {
  id: PlanId
  name: string
  description: string
  priceInCents: number
  period: string
  durationDays: number | null
  maxDevices: number
  features: string[]
  highlighted: boolean
  badge: string
}

// Source of truth for prices: the checkout server action reads from here,
// never from the client.
export const PRODUCTS: Product[] = [
  {
    id: 'semaine',
    name: '1 semaine',
    description: 'Idéal pour tester toutes les macros.',
    priceInCents: 499,
    period: '/ semaine',
    durationDays: 7,
    maxDevices: 1,
    features: ['Toutes les macros', '1 PC', 'Mises à jour incluses'],
    highlighted: false,
    badge: 'Parfait pour tester',
  },
  {
    id: 'mois',
    name: '1 mois',
    description: 'Le choix préféré de la communauté.',
    priceInCents: 999,
    period: '/ mois',
    durationDays: 30,
    maxDevices: 1,
    features: ['Toutes les macros', '1 PC', 'Mises à jour incluses', 'Support prioritaire Discord'],
    highlighted: true,
    badge: 'Populaire',
  },
  {
    id: 'vie',
    name: 'À vie',
    description: 'Une clé, pour toujours.',
    priceInCents: 2999,
    period: 'paiement unique',
    durationDays: null,
    maxDevices: 2,
    features: [
      'Toutes les macros',
      '2 PC',
      'Mises à jour à vie',
      'Support prioritaire Discord',
      'Accès aux bêtas',
    ],
    highlighted: false,
    badge: 'Rentabilité au max',
  },
]

export function getProduct(id: string) {
  return PRODUCTS.find((product) => product.id === id)
}

export function formatPrice(cents: number) {
  return new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(cents / 100)
}
