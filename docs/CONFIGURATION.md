# Installation, lancement et configuration

## 1. Développement sur PC

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt

# le serveur (API + site) : http://localhost:8000
.venv/bin/uvicorn serveur.app:app --reload

# l'app (autre terminal) : elle parle au serveur de http://localhost:8000 par défaut
.venv/bin/python main.py

# les tests (logique, moteur avec un faux routeur, serveur, client de l'app)
.venv/bin/pytest
```

Sur PC il n'y a pas de GPS. Choisis le départ sur la carte ou cherche un lieu ; la sortie est simulée le long de la boucle (touche **D** : faire un détour).

Documentation interactive de l'API : http://localhost:8000/api/docs

## 2. Variables d'environnement du serveur

Aucun secret n'est écrit dans le code. Mets ces valeurs dans l'environnement du service, ou dans un fichier `.env` que tu charges toi-même. `.env` est ignoré par git.

| Variable | Rôle | Défaut |
|---|---|---|
| `LOOPY_URL_PUBLIQUE` | Adresse publique du serveur, par exemple `https://loopy.example.org`. Sert aux liens envoyés par e-mail et au retour OAuth de Strava. En `https://`, les cookies sont marqués `Secure`. | `http://localhost:8000` |
| `LOOPY_DONNEES` | Dossier de la base SQLite (`loopy.db`) et des photos de profil. **À sauvegarder.** | `serveur/donnees` |
| `LOOPY_BROUTER` | Moteur d'itinéraires BRouter, utilisé par le site (voir §5) | `https://brouter.de/brouter` |
| `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET` | Application Strava (voir §3). Sans elles, tout fonctionne sauf l'envoi vers Strava, qui l'explique à l'utilisateur. | vide |
| `SMTP_HOTE`, `SMTP_PORT`, `SMTP_UTILISATEUR`, `SMTP_MOT_DE_PASSE`, `SMTP_EXPEDITEUR` | Envoi des e-mails de nouveau mot de passe (STARTTLS, port 587 par défaut). Sans eux, le lien est écrit dans le journal du serveur : pratique en développement, **pas en production**. | vide |

## 3. Strava : créer l'application

1. Connecte-toi sur https://www.strava.com/settings/api et crée une application.
2. **Authorization Callback Domain** : le domaine de `LOOPY_URL_PUBLIQUE`, sans `https://` ni chemin, par exemple `loopy.example.org`. En développement, `localhost` est autorisé d'office.
3. Copie le *Client ID* et le *Client Secret* dans `STRAVA_CLIENT_ID` et `STRAVA_CLIENT_SECRET`, puis redémarre le serveur.
4. Adresse de retour utilisée par Loopy : `{LOOPY_URL_PUBLIQUE}/api/strava/retour`.
5. Permissions demandées : `activity:write,activity:read`. La première sert à envoyer, la seconde à suivre l'envoi. Si l'utilisateur décoche `activity:write`, Loopy lui explique qu'il manque la permission.

Une nouvelle application Strava est en **mode « single player »** : seul son créateur peut s'y connecter. Pour ouvrir l'envoi à d'autres comptes, demande une hausse de capacité depuis la page de l'API Strava. Limites par défaut : 200 requêtes par 15 minutes et 2 000 par jour.

Fonctionnement :
1. L'utilisateur relie Strava, depuis son espace web ou depuis Profil dans l'app (la page s'ouvre dans le navigateur).
2. Sur une activité terminée, il touche « Envoyer vers Strava ».
3. Le serveur produit le GPX horodaté et l'envoie (`POST /api/v3/uploads`, `data_type=gpx`, `sport_type=Run` ou `Ride`).
4. Il suit ensuite le traitement asynchrone (`GET /api/v3/uploads/:id`, toutes les 2 s au plus).
5. Les erreurs de Strava, un doublon par exemple, sont affichées telles quelles.

## 4. Mettre le serveur en production

- Mets-le derrière un proxy HTTPS : Caddy, nginx ou Traefik. **La géolocalisation du site n'est disponible qu'en HTTPS**, sauf sur `localhost`.
- Lance `uvicorn serveur.app:app --host 127.0.0.1 --port 8000 --workers 1`. Un seul processus, car le limiteur de débit est en mémoire. Au-delà, remplace-le par un limiteur partagé (Redis par exemple).
- Sauvegarde régulièrement `LOOPY_DONNEES`. Copie à chaud possible avec `sqlite3 loopy.db ".backup sauvegarde.db"`.
- L'app Android se règle dans **Profil > L'app > Adresse du serveur Loopy**, avec l'adresse `https://…` du serveur.

## 5. Moteur d'itinéraires : sa propre instance BRouter

Le serveur public `brouter.de` est fait pour un usage léger : il refuse temporairement les clients trop actifs. **Pour une app publique, héberge ta propre instance** :

```bash
git clone https://github.com/abrensch/brouter && cd brouter
./gradlew clean build fatJar
mkdir -p misc/segments4
# données mondiales par tuiles de 5° x 5° (en Europe, ~100 à 300 Mo par tuile) :
wget -P misc/segments4 https://brouter.de/brouter/segments4/W5_N40.rd5   # exemple : sud-ouest de la France
./misc/scripts/standalone/server.sh    # écoute sur le port 17777
```

Les commandes exactes de construction peuvent changer d'une version à l'autre : suis le README du dépôt BRouter, ou son image Docker.

Puis :
- côté serveur, `LOOPY_BROUTER=http://127.0.0.1:17777/brouter` ;
- côté app, Profil > L'app > Moteur d'itinéraires.

Nos profils `profils/*.brf` sont envoyés automatiquement au moteur (`POST /brouter/profile`). Rien d'autre à installer. Les fichiers `.rd5` se mettent à jour chaque semaine sur brouter.de.

## 6. Tuiles de carte

L'app et le site affichent les tuiles d'OpenStreetMap (`tile.openstreetmap.org`). Elles sont gratuites, avec une [politique d'usage](https://operations.osmfoundation.org/policies/tiles/) : identification de l'app (faite), attribution visible (faite) et **pas d'usage intensif**. Pour une app publique très utilisée, prends un fournisseur de tuiles avec une clé : MapTiler, Stadia Maps, Thunderforest, ou ton propre serveur. Il suffit de changer l'adresse :
- l'app : `URL_TUILES` dans `ui/carte.py` ;
- le site : `website/assets/js/carte.js`.

## 7. Construire l'APK

```bash
buildozer android debug
```

Le fichier `buildozer.spec` ajoute pour cette version :
- les permissions `INTERNET` et `ACCESS_NETWORK_STATE` ;
- `openssl` et `certifi`, pour un HTTPS avec des certificats à jour ;
- les profils `.brf`.

Le serveur, le site et les outils ne sont pas embarqués.
