import { Ban, RotateCcw, Trash2, Unplug } from 'lucide-react'
import { deleteKey, resetHwid, setKeyStatus } from '@/app/actions/admin'
import { CopyKey } from '@/components/copy-key'
import type { LicenseKey } from '@/lib/db/schema'
import { getProduct } from '@/lib/products'
import { cn } from '@/lib/utils'

const dateFormat = new Intl.DateTimeFormat('fr-FR', { dateStyle: 'short', timeStyle: 'short' })

function getState(key: LicenseKey) {
  if (key.status === 'revoked') return { label: 'Révoquée', className: 'bg-destructive/15 text-destructive' }
  if (key.expiresAt && key.expiresAt < new Date()) return { label: 'Expirée', className: 'bg-muted text-muted-foreground' }
  if (key.activatedAt) return { label: 'Activée', className: 'bg-boost/15 text-boost' }
  return { label: 'Non utilisée', className: 'bg-primary/15 text-primary' }
}

const iconButton =
  'flex size-8 items-center justify-center rounded-md border border-border text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground'

export function KeysTable({ keys }: { keys: LicenseKey[] }) {
  return (
    <section aria-labelledby="keys-title" className="rounded-2xl border border-border bg-card">
      <div className="flex items-center justify-between p-6 pb-4">
        <h2 id="keys-title" className="font-display text-lg font-semibold">
          Clés de licence
        </h2>
        <span className="text-sm text-muted-foreground">{keys.length} au total</span>
      </div>
      {keys.length === 0 ? (
        <p className="px-6 pb-8 text-sm text-muted-foreground">
          Aucune clé pour le moment. Elles apparaîtront ici dès le premier achat.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-y border-border text-xs text-muted-foreground uppercase">
              <tr>
                <th scope="col" className="px-6 py-3 font-medium">Clé</th>
                <th scope="col" className="px-3 py-3 font-medium">Offre</th>
                <th scope="col" className="px-3 py-3 font-medium">Statut</th>
                <th scope="col" className="px-3 py-3 font-medium">Client</th>
                <th scope="col" className="px-3 py-3 font-medium">PC liés</th>
                <th scope="col" className="px-3 py-3 font-medium">Expire</th>
                <th scope="col" className="px-6 py-3 text-right font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {keys.map((key) => {
                const state = getState(key)
                const devices = key.hwid ? key.hwid.split(',').length : 0
                return (
                  <tr key={key.id} className="align-middle">
                    <td className="px-6 py-3">
                      <CopyKey value={key.key} compact />
                      <span className="mt-0.5 block text-xs text-muted-foreground">
                        {key.source === 'stripe' ? 'Achat Stripe' : 'Générée manuellement'} ·{' '}
                        {dateFormat.format(key.createdAt)}
                      </span>
                    </td>
                    <td className="px-3 py-3">{getProduct(key.plan)?.name ?? key.plan}</td>
                    <td className="px-3 py-3">
                      <span className={cn('rounded-full px-2 py-0.5 text-xs font-medium', state.className)}>
                        {state.label}
                      </span>
                    </td>
                    <td className="max-w-48 truncate px-3 py-3 text-muted-foreground" title={key.note ?? undefined}>
                      {key.email ?? key.note ?? '—'}
                    </td>
                    <td className="px-3 py-3 text-muted-foreground">
                      {devices}/{getProduct(key.plan)?.maxDevices ?? 1}
                    </td>
                    <td className="px-3 py-3 text-muted-foreground">
                      {key.expiresAt
                        ? dateFormat.format(key.expiresAt)
                        : key.plan === 'vie'
                          ? 'Jamais'
                          : 'À l’activation'}
                    </td>
                    <td className="px-6 py-3">
                      <div className="flex justify-end gap-2">
                        <form action={setKeyStatus}>
                          <input type="hidden" name="id" value={key.id} />
                          <input type="hidden" name="status" value={key.status === 'active' ? 'revoked' : 'active'} />
                          <button
                            type="submit"
                            className={iconButton}
                            aria-label={key.status === 'active' ? `Révoquer ${key.key}` : `Réactiver ${key.key}`}
                            title={key.status === 'active' ? 'Révoquer' : 'Réactiver'}
                          >
                            {key.status === 'active' ? (
                              <Ban className="size-4" aria-hidden="true" />
                            ) : (
                              <RotateCcw className="size-4" aria-hidden="true" />
                            )}
                          </button>
                        </form>
                        <form action={resetHwid}>
                          <input type="hidden" name="id" value={key.id} />
                          <button
                            type="submit"
                            className={iconButton}
                            disabled={devices === 0}
                            aria-label={`Délier les PC de ${key.key}`}
                            title="Réinitialiser les PC liés"
                          >
                            <Unplug className="size-4" aria-hidden="true" />
                          </button>
                        </form>
                        <form action={deleteKey}>
                          <input type="hidden" name="id" value={key.id} />
                          <button
                            type="submit"
                            className={cn(iconButton, 'hover:border-destructive hover:text-destructive')}
                            aria-label={`Supprimer ${key.key}`}
                            title="Supprimer"
                          >
                            <Trash2 className="size-4" aria-hidden="true" />
                          </button>
                        </form>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
