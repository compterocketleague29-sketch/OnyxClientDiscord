# Bot Discord et API de licences

Le bot, le client Windows et le site utilisent la même base PostgreSQL. Le bot peut fonctionner sans le site : il crée ses propres paiements Stripe, lie les clés à Discord et laisse l'API FastAPI valider ces clés dans le `.exe`. Le site peut rester en ligne et continuer à utiliser les licences existantes.

## Configuration et secrets

`.env.example` est un modèle sans secrets à garder dans GitHub. Ne committe jamais `.env`, les clés/token Stripe ou Discord, ni les identifiants réels de la base. `.gitignore` exclut déjà les fichiers `.env`.

En local, copie `.env.example` en `.env` dans ce dossier et ajoute les valeurs de développement. Sur Railway, configure les valeurs dans **Variables** pour chaque service; ne crée pas de `.env` dans le dépôt. Au minimum :

- **API** : `DATABASE_URL`, `STRIPE_WEBHOOK_SECRET`.
- **Bot** : `DATABASE_URL`, `DISCORD_BOT_TOKEN`, `STRIPE_SECRET_KEY`, `DISCORD_ADMIN_USER_IDS` et/ou `DISCORD_ADMIN_ROLE_IDS`, `DOWNLOAD_URL`. `DISCORD_GUILD_ID` est facultatif.

Configure exactement la même `DATABASE_URL` PostgreSQL pour l'API, le bot et le site afin de conserver les licences existantes. `DOWNLOAD_URL` est un lien public, pas un secret. `MACRO_API_URL` est également une adresse publique : elle sert à construire le client et ne doit pas contenir de clé secrète.

Dans Stripe, ajoute un webhook vers `https://<domaine-api-railway>/v1/stripe/webhook` pour l'événement `checkout.session.completed`. Renseigne le secret de signature fourni par Stripe dans les variables Railway de l'API comme `STRIPE_WEBHOOK_SECRET`.

La base doit être la même que celle du site pour retrouver les licences existantes. Au démarrage, l'API ajoute la colonne `discordUserId` si nécessaire; aucune donnée de licence existante n'est remplacée.

## Démarrage sous Windows

Depuis `OnyxClient/backend` dans le dépôt cloné, ouvre deux terminaux :

```powershell
python -m uvicorn app:app --host 0.0.0.0 --port 8000
python discord_bot.py
```

Publie l'API derrière une URL HTTPS stable. `DISCORD_GUILD_ID` est facultatif; le renseigner synchronise les commandes immédiatement sur ce serveur pendant la mise en place. Sans cette variable, les commandes sont enregistrées globalement et leur propagation peut prendre plus de temps.

Invite l'application Discord sur ton serveur avec les autorisations `bot` et `applications.commands`.

## Déploiement Railway depuis GitHub

Dans ce dépôt, les fichiers de l'application se trouvent sous `OnyxClient/`. Crée deux services Railway à partir du même dépôt GitHub et définis leur **Root Directory** sur `/OnyxClient/backend` pour chacun :

1. **API** — commande de démarrage : `uvicorn app:app --host 0.0.0.0 --port $PORT`. Active un domaine public et configure le health check sur `/health`. Ajoute ses variables listées plus haut.
2. **Bot** — commande de démarrage : `python discord_bot.py`. Ajoute ses variables listées plus haut. Ce service doit rester actif pour répondre aux commandes Discord.

Railway installe les dépendances à partir de `requirements.txt` dans ce dossier. Après avoir déployé l'API, utilise son domaine public dans l'URL du webhook Stripe et lors de la compilation du client.

## Commandes Discord

- `/acheter` : crée un paiement Stripe pour l'une des trois offres. La clé est créée après confirmation du paiement et récupérable avec `/mes-licences`.
- `/mes-licences` : affiche en privé les licences actives liées au compte.
- `/lier-cle` : associe à Discord une clé existante, par exemple achetée sur le site.
- `/telecharger` : fournit le lien de téléchargement aux membres ayant une licence active.
- `/admin-creer-cle`, `/admin-revoquer-cle` et `/admin-licences` : commandes réservées aux identifiants utilisateur ou rôles configurés.

Le lien du `.exe` peut circuler, mais son utilisation reste protégée par la validation de licence auprès de l'API.

## Construire le client

Le client n'utilise plus l'URL du site comme API par défaut. Depuis PowerShell, dans le dossier `OnyxClient/client` du dépôt cloné :

```powershell
$env:MACRO_API_URL = 'https://<hôte-api>'
.\build.bat
```

Le script inclut cette URL dans `api_url.txt` au sein du `.exe`. La variable `MACRO_API_URL` peut aussi être définie au lancement du client pour remplacer cette valeur.
