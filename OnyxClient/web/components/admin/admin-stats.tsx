import type { LicenseKey } from '@/lib/db/schema'
import { formatPrice } from '@/lib/products'

export function AdminStats({ keys }: { keys: LicenseKey[] }) {
  const revenue = keys.reduce((sum, key) => sum + (key.amountCents ?? 0), 0)
  const sold = keys.filter((key) => key.source === 'stripe').length
  const activated = keys.filter((key) => key.activatedAt).length
  const active = keys.filter(
    (key) => key.status === 'active' && (!key.expiresAt || key.expiresAt > new Date()),
  ).length

  const stats = [
    { label: 'Revenus', value: formatPrice(revenue) },
    { label: 'Clés vendues', value: sold },
    { label: 'Clés actives', value: active },
    { label: 'Activées sur PC', value: activated },
  ]

  return (
    <dl className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      {stats.map((stat) => (
        <div key={stat.label} className="rounded-xl border border-border bg-card p-5">
          <dt className="text-sm text-muted-foreground">{stat.label}</dt>
          <dd className="mt-1 font-display text-2xl font-bold">{stat.value}</dd>
        </div>
      ))}
    </dl>
  )
}
