# Bot Discord et API de licences

Le bot, le client Windows et le site utilisent la même base PostgreSQL. Le bot peut fonctionner sans le site : il crée ses propres paiements Stripe, lie les clés à Discord et laisse l'API FastAPI valider ces clés dans le `.exe`. Le site peut rester en ligne et continuer à utiliser les licences existantes.

## Configuration et secrets

`.env.example` est un modèle sans secrets à garder dans GitHub. Ne committe jamais `.env`, les clés/token Stripe ou Discord, ni les identifiants réels de la base. `.gitignore` exclut déjà les fichiers `.env`.

En local, copie `.env.example` en `.env` dans ce dossier et ajoute les valeurs de développement. Sur Railway, configure les valeurs dans **Variables** pour chaque service; ne crée pas de `.env` dans le dépôt. Au minimum :

- **API** : `DATABASE_URL`, `STRIPE_WEBHOOK_SECRET`.
- **Bot** : `DATABASE_URL`, `DISCORD_BOT_TOKEN`, `STRIPE_SECRET_KEY`, `DISCORD_ADMIN_USER_IDS` et/ou `DISCORD_ADMIN_ROLE_IDS`, `DOWNLOAD_URL`. `DISCORD_GUILD_ID`, `TICKET_CATEGORY_ID` et `TICKET_LOG_CHANNEL_ID` sont facultatifs.

Configure exactement la même `DATABASE_URL` PostgreSQL pour l'API, le bot et le site afin de conserver les licences existantes. `DOWNLOAD_URL` est un lien public, pas un secret. `MACRO_API_URL` est également une adresse publique : elle sert à construire le client et ne doit pas contenir de clé secrète.
`TICKET_CATEGORY_ID` désigne la catégorie où créer les tickets; `TICKET_LOG_CHANNEL_ID` désigne le salon privé où envoyer les transcripts à la fermeture. Active le **mode développeur** dans Discord pour copier ces identifiants. Les membres du staff doivent être administrateurs du serveur ou avoir le rôle indiqué dans `DISCORD_ADMIN_ROLE_IDS`.

Dans Stripe, ajoute un webhook vers `https://<domaine-api-railway>/v1/stripe/webhook` pour l'événement `checkout.session.completed`. Renseigne le secret de signature fourni par Stripe dans les variables Railway de l'API comme `STRIPE_WEBHOOK_SECRET`.

La base doit être la même que celle du site pour retrouver les licences existantes. Au démarrage, l'API ajoute la colonne `discordUserId` si nécessaire; aucune donnée de licence existante n'est remplacée.

## Démarrage sous Windows

Depuis `backend` à la racine du dépôt cloné, ouvre deux terminaux :

```powershell
python -m uvicorn app:app --host 0.0.0.0 --port 8000
python discord_bot.py
```

Publie l'API derrière une URL HTTPS stable. `DISCORD_GUILD_ID` est facultatif; le renseigner synchronise les commandes immédiatement sur ce serveur pendant la mise en place. Sans cette variable, les commandes sont enregistrées globalement et leur propagation peut prendre plus de temps.

Invite l'application Discord sur ton serveur avec les portées `bot` et `applications.commands`. Active également **Message Content Intent** dans le portail développeur Discord pour que les transcripts contiennent les messages. Pour les tickets, le bot a besoin des permissions **Gérer les salons**, **Voir les salons**, **Envoyer des messages**, **Lire l’historique**, **Joindre des fichiers** et **Intégrer des liens**. La commande `/clear` exige **Gérer les messages** pour la personne qui l’utilise et pour le bot.

## Déploiement Railway depuis GitHub

Crée deux services Railway à partir du même dépôt GitHub et définis leur **Root Directory** sur `/backend` pour chacun :

1. **API** — commande de démarrage : `uvicorn app:app --host 0.0.0.0 --port $PORT`. Active un domaine public et configure le health check sur `/health`. Ajoute ses variables listées plus haut.
2. **Bot** — commande de démarrage : `python discord_bot.py`. Ajoute ses variables listées plus haut. Ce service n’a pas besoin de domaine public. Dans les paramètres Railway, configure le redémarrage du service en cas d’échec. Garde une seule réplique du bot pour éviter les doubles tirages de giveaway.

Railway installe les dépendances à partir de `requirements.txt` dans ce dossier. Après avoir déployé l'API, utilise son domaine public dans l'URL du webhook Stripe et lors de la compilation du client.
Le bot reste connecté tant que son service Railway est déployé et actif. Railway peut le relancer après un crash; une disponibilité 24 h/24 dépend aussi de l’état du service et des limites de ton offre Railway.

## Commandes Discord

- `/aide` : présente les commandes de licence, de téléchargement et de support.
- `/acheter` : crée un paiement Stripe pour l'une des cinq offres : 3 jours (4,99 €, 1 PC), 1 semaine (7,99 €, 1 PC), 1 mois (14,99 €, 1 PC), 3 mois (29,99 €, 1 PC) ou à vie (59,99 €, 2 PC). La clé est créée après confirmation du paiement et récupérable avec `/mes-licences`.
- `/mes-licences` : affiche en privé les licences actives liées au compte.
- `/lier-cle` : associe à Discord une clé existante, par exemple achetée sur le site.
- `/telecharger` : affiche un bouton « Télécharger le launcher » aux membres ayant une licence active, sans montrer l'URL.
- `/admin-creer-cle`, `/admin-revoquer-cle`, `/admin-licences` et `/admin-lister-cles` : commandes réservées aux administrateurs; l'inventaire complet des clés est privé et paginé.
- `/ticket-panel` : publie le menu de création de tickets privés (aide, paiement, clé, launcher ou autre). Le salon de tickets peut être choisi avec `TICKET_CATEGORY_ID`.
- `/ticket-close`, `/ticket-add` et `/ticket-transcript` : ferment et archivent un ticket, ajoutent un membre ou fournissent son transcript HTML. Si `TICKET_LOG_CHANNEL_ID` est défini, le transcript est aussi envoyé dans ce salon.
- `/clear` : supprime de 1 à 100 messages dans un salon; permission Discord **Gérer les messages** requise.
- `/giveaway` : lance un tirage au sort avec bouton de participation et tirage automatique. Les participations et échéances sont conservées dans PostgreSQL pour survivre aux redémarrages.

Après le déploiement des mises à jour Discord, utilise `/ticket-panel` à nouveau pour remplacer l'ancien panneau par le menu de catégories.

Le lien du `.exe` peut circuler, mais son utilisation reste protégée par la validation de licence auprès de l'API.

## Construire le client

Le client n'utilise plus l'URL du site comme API par défaut. Depuis PowerShell, dans le dossier `client` à la racine du dépôt cloné :

```powershell
$env:MACRO_API_URL = 'https://<hôte-api>'
.\build.bat
```

Le script inclut cette URL dans `api_url.txt` au sein du `.exe`. La variable `MACRO_API_URL` peut aussi être définie au lancement du client pour remplacer cette valeur.
