import { createInterface } from 'node:readline/promises'
import { stdin, stdout } from 'node:process'
import { Pool } from 'pg'

function readSecret(prompt) {
  if (!stdin.isTTY || typeof stdin.setRawMode !== 'function') {
    throw new Error('Lance cette commande dans un terminal interactif.')
  }

  stdout.write(prompt)
  stdin.setRawMode(true)
  stdin.resume()

  return new Promise((resolve, reject) => {
    let value = ''

    function finish(error) {
      stdin.setRawMode(false)
      stdin.pause()
      stdin.removeListener('data', onData)
      stdout.write('\n')
      if (error) reject(error)
      else resolve(value)
    }

    function onData(buffer) {
      for (const character of buffer.toString('utf8')) {
        if (character === '\u0003') {
          finish(new Error('Opération annulée.'))
          return
        }
        if (character === '\r' || character === '\n') {
          finish()
          return
        }
        if (character === '\u007f' || character === '\b') {
          value = value.slice(0, -1)
        } else if (character >= ' ') {
          value += character
        }
      }
    }

    stdin.on('data', onData)
  })
}

async function main() {
  const siteUrl = new URL(process.env.BETTER_AUTH_URL || 'https://www.onyxclient.store')
  if (siteUrl.protocol !== 'https:' && siteUrl.hostname !== 'localhost') {
    throw new Error('BETTER_AUTH_URL doit utiliser HTTPS.')
  }
  const origin = siteUrl.origin
  const reader = createInterface({ input: stdin, output: stdout })
  const emails = []
  try {
    emails.push((await reader.question('Adresse e-mail du premier administrateur : ')).trim().toLowerCase())
    emails.push((await reader.question('E-mail du second admin : ')).trim().toLowerCase())
  } finally {
    reader.close()
  }

  if (emails.some((email) => !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))) {
    throw new Error('Saisis deux adresses e-mail valides.')
  }
  if (emails[0] === emails[1]) {
    throw new Error('Les deux adresses e-mail doivent être différentes.')
  }

  const databaseUrl =
    process.env.DATABASE_URL?.trim() ||
    (await readSecret('DATABASE_URL Supabase (saisie masquée) : '))
  if (!/^postgres(?:ql)?:\/\//i.test(databaseUrl)) {
    throw new Error('DATABASE_URL doit être une URI PostgreSQL valide.')
  }

  const pool = new Pool({ connectionString: databaseUrl })
  try {
    const { rows } = await pool.query(
      'SELECT lower("email") AS email FROM "user" WHERE lower("email") = ANY($1::text[])',
      [emails],
    )
    const existing = new Set(rows.map((row) => row.email))

    for (let index = 0; index < emails.length; index += 1) {
      const email = emails[index]
      if (!existing.has(email)) {
        const password = await readSecret(`Mot de passe pour ${email} (8 caractères minimum, masqué) : `)
        if (password.length < 8) {
          throw new Error('Le mot de passe doit contenir au moins 8 caractères.')
        }

        const response = await fetch(new URL('/api/auth/sign-up/email', origin), {
          method: 'POST',
          headers: {
            'content-type': 'application/json',
            origin,
            referer: `${origin}/admin/login`,
          },
          body: JSON.stringify({ name: `Admin ${index + 1}`, email, password }),
        })
        const result = await response.json().catch(() => null)
        if (!response.ok) {
          throw new Error(
            `Création du compte ${email} impossible (HTTP ${response.status})` +
              (result?.message ? ` : ${result.message}` : '.'),
          )
        }
      }

      const promoted = await pool.query(
        'UPDATE "user" SET "role" = $1 WHERE lower("email") = $2 RETURNING "email", "role"',
        ['admin', email],
      )
      if (promoted.rowCount !== 1) {
        throw new Error(`Le compte ${email} a été créé, mais son rôle admin n’a pas pu être défini.`)
      }
      stdout.write(`Compte admin prêt : ${promoted.rows[0].email}\n`)
    }
  } finally {
    await pool.end()
  }
}

main().catch((error) => {
  console.error(`Échec : ${error.message}`)
  process.exitCode = 1
})
