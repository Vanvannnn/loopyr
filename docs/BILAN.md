# Bilan de la refonte (version 0.4, novembre 2026)

## Ce qui est terminé et vérifié

| Fonction | Où | Vérification |
|---|---|---|
| Boucles **partout dans le monde**, depuis la position réelle, sans zone codée en dur | `boucles.py`, `profils/` | Générations réelles (§ Tests) |
| Zone de recherche **dynamique**, corrigée d'après la distance réellement obtenue, affichée sur la carte | `boucles.generer` | Tests unitaires et réels |
| Départ par GPS, par point choisi sur la carte, ou par lieu cherché si le GPS est refusé ou absent | app : `ui/ecran_accueil.py` ; site : `creer.html` | Parcours de l'app piloté sur PC ; recherche testée en réel |
| Bouton « Ma position » (relance du GPS) et gestion d'un refus d'autorisation | app : accueil ; site : messages par cas d'erreur | Relu ; **non testé sur téléphone** (voir plus bas) |
| Écran de départ « Vélo / Course », puis distance libre avec suggestions propres à chaque sport | app et site | Parcours piloté, captures |
| Deux profils de calcul distincts (vélo de route, course à pied) et notation propre au sport | `profils/*.brf`, `boucles.qualite` | Tests, et profils réels (§ Tests) |
| Plusieurs propositions variées, classées ; explication si aucune boucle n'est satisfaisante, ou si la distance exacte est impossible | `boucles.generer` | Tests unitaires (aller-retour refusé, moteur en échec) |
| Revêtement et **indicateur de confiance** : étiqueté dans OSM, déduit du type de route, ou inconnu | `boucles.revetement`, `resume_voies` | Tests ; affiché dans l'app et le site |
| **GPX de l'itinéraire** (tracé seul, sans heure, `boucle_10km_velo.gpx`) | `gpx.gpx_itineraire`, `commun.js` | Test de structure ; aucune balise `<time>` |
| **GPX de l'activité** (points horodatés, un segment par pause, type `running` ou `cycling`) | `gpx.gpx` | Tests de structure et d'heures |
| Comptes (inscription, connexion, déconnexion, mot de passe oublié, réinitialisation) : **un seul système** pour l'app et le site | `serveur/app.py`, `compte.py` | Tests serveur et client contre un vrai serveur |
| Profil : photo, présentation, sport favori, préférences, statistiques, visibilité, masquage du départ, suppression du compte | serveur, site, app | Tests serveur |
| Historique : activités réellement faites, boucles enregistrées, favorites, bien distinguées | app : Historique ; site : espace | Parcours piloté, tests |
| Synchronisation des sorties et des boucles avec le compte, renvoi automatique de ce qui a été fait hors connexion | `main.synchroniser_*` | Parcours piloté : la sortie simulée apparaît dans le fil |
| Communauté : suivre, profils publics, fil, j'aime, commentaires, boucles partagées, sorties publiques, recherche de sportifs | serveur, site, app (fil, j'aime) | Tests serveur |
| Confidentialité : visibilité par activité (tout le monde, abonnés, moi seul), profil privé, **300 m masqués au début et à la fin** des tracés montrés aux autres | `geo.rogner`, `trace_publique` | Tests (tracé rogné, accès refusés) |
| **Strava** : OAuth côté serveur, rafraîchissement des jetons, envoi du GPX horodaté, suivi du traitement, erreurs, révocation | `serveur/strava.py` | Tests avec un **faux Strava** qui reproduit les réponses documentées |
| Refonte de l'app : navigation à cinq onglets (Accueil, Créer, Historique, Communauté, Profil), carte sur tuiles OSM avec cache disque, nouveaux écrans | `ui/` | Parcours complet piloté et capturé sur PC (WSLg) |
| Site web : page d'accueil animée, création de boucle, compte, espace personnel, communauté | `website/` | Captures en largeur ordinateur et mobile ; génération par l'API testée en réel |
| Sécurité : mots de passe scrypt, jetons hachés, cookie HttpOnly SameSite et anti-CSRF, limites de débit, contrôle des images envoyées, en-têtes de sécurité, aucun secret dans l'app ni le site | `serveur/` | Tests (CSRF, limites, formats d'image) |

## Tests réellement exécutés

`.venv/bin/pytest` : **60 tests passent**. Ils couvrent la logique de course, le moteur (avec un faux routeur), le GPX, le stockage, le serveur, le client de l'app contre un vrai serveur uvicorn et le faux Strava.

Générations **réelles** avec le serveur public BRouter, le 8 novembre 2026 (distance obtenue, toutes les boucles fermées sur le départ) :

| Départ | Sport | Demandé | Obtenu (meilleure) | Remarques |
|---|---|---|---|---|
| Pessac | course | 5 km | 5,05 km | 67 % chemins, 0 % grands axes |
| Pessac | course | 21 km | 21,02 km | |
| Pessac | vélo | 50 km | 51,3 km | revêtu à 99 % |
| **Pessac** | **vélo** | **100 km** | **98,6 km** | 3 boucles (98,6 / 101,7 / 100,3 km), revêtues à 96–100 %, zone de 24 km, en 9 s |
| Bordeaux | vélo | 20 km | 19,7 km | |
| Toulouse (via l'API du site) | vélo | 25 km | 25,2 km | en 5 s |
| Paris | course | 10 km | 9,96 km | 98 % chemins et voies piétonnes |
| Paris | vélo | 50 km | 49,0 km | 36 % pistes cyclables |
| Amsterdam | course | 8 km | 8,14 km | |
| Montréal | vélo | 30 km | 29,4 km | revêtu à 100 %, 48 % pistes cyclables |
| Kyoto | course | 10 km | 9,87 km | |

Parcours complet de l'app sur PC (vraie app Kivy pilotée par script, dossier de données temporaire) :
1. accueil, puis Créer, puis Vélo, puis 20 km depuis Pessac ;
2. 3 boucles réelles, enregistrement, boucle B ;
3. historique des boucles ;
4. départ, décompte, sortie simulée, fin, enregistrement, détail ;
5. création d'un compte, profil connecté, communauté (la sortie synchronisée apparaît dans le fil) ;
6. thème nuit.

Aucune erreur.

## Ce qui n'a pas pu être vérifié ici

- **Sur un vrai téléphone Android.** Je n'ai ni appareil ni APK construit dans cet environnement. À vérifier : GPS et autorisations, HTTPS avec `openssl` et `certifi`, ouverture du navigateur pour Strava, export GPX. La partie GPS et service n'a pas changé ; le réseau est nouveau sur Android.
- **Envoi réel vers Strava.** Il faut une application Strava (identifiants) : tout le circuit est testé contre un faux Strava conforme à la documentation officielle, pas contre strava.com.
- **Envoi réel des e-mails.** Sans SMTP configuré, le lien de réinitialisation est écrit dans le journal du serveur (c'est ce que vérifie le test).
- **Ouverture des GPX dans un logiciel tiers.** La structure GPX 1.1 est vérifiée par les tests, pas l'import dans Garmin Connect ou dans l'éditeur d'itinéraires de Strava.
- **Interaction réelle avec le site** (formulaires remplis à la main, géolocalisation d'un navigateur). Le rendu a été capturé, et les appels à l'API sont couverts par les tests du serveur.

## Ce qui demande une intervention extérieure

1. **Créer l'application Strava** et renseigner `STRAVA_CLIENT_ID` et `STRAVA_CLIENT_SECRET` (voir `docs/CONFIGURATION.md` §3). Puis demander à Strava de sortir du mode « single player » pour ouvrir l'envoi à d'autres comptes.
2. **Héberger le serveur en HTTPS** avec un nom de domaine (`LOOPY_URL_PUBLIQUE`). Indispensable pour la géolocalisation du site et pour Strava.
3. **Un serveur d'e-mails (SMTP)** pour les mots de passe oubliés.
4. **Une instance BRouter propre** avant d'ouvrir l'app au public. Le serveur public limite les clients actifs, ce que j'ai constaté pendant les tests.
5. **Un fournisseur de tuiles** si l'usage devient important (politique d'usage d'OpenStreetMap).
6. **Construire et tester l'APK** sur téléphone (`buildozer android debug`).

## Changements à connaître

- **Le dénivelé visé au mètre près est remplacé** par une préférence de relief (peu importe, plat, vallonné). Le D+ est toujours calculé et affiché, avec les altitudes du moteur, partout dans le monde. Il guide le classement des boucles au lieu d'être une cible exacte.
- **`data.db`, `core.py` et `prepare_data.py` sont retirés** : ils sont remplacés par la génération mondiale. Ils restent dans l'historique git.
- **Génération hors connexion** : générer une **nouvelle** boucle demande du réseau, car le calcul se fait sur le moteur. Une boucle enregistrée, la sortie et l'historique restent utilisables hors connexion, et la carte d'une zone déjà vue reste en cache.
- **Annonces vocales** : elles restent annoncées à chaque kilomètre, y compris à vélo.
- **Limites connues** :
  - le limiteur de débit du serveur est en mémoire (un seul processus) ;
  - les jetons Strava sont stockés en clair dans la base du serveur (à chiffrer si la base est exposée) ;
  - le cache de tuiles de l'app n'est pas plafonné en taille.
