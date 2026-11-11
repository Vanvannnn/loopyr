# Loopy

Choisis vélo ou course, indique la distance : Loopy trace autour de ta position une **vraie boucle** qui revient à ton point de départ, **partout dans le monde**. Pendant la sortie, l'app te guide (consignes de direction à l'écran et à la voix) et te suit (carte, chrono, allure ou vitesse, D+ et D− en direct, progression, splits), même téléphone verrouillé. Ensuite, tu retrouves ta sortie, tu l'envoies sur Strava ou tu la partages.

Le projet contient trois parties :

| Dossier | Partie |
|---|---|
| racine, `ui/`, `capteurs/`, `service/` | L'**app Android** (Python, Kivy, buildozer) |
| `serveur/` | Le **serveur** (FastAPI, PostgreSQL) : comptes, profils, activités, communauté, Strava, génération pour le site |
| `website/` | Le **site** : présentation, création de boucle, compte et espace personnel. Servi par le serveur |

Le code métier en Python pur est **partagé** par l'app et le serveur. Il est à la racine :

| Fichier | Rôle |
|---|---|
| `boucles.py` | Génération des boucles : zone dynamique, plusieurs directions, notation, revêtement et confiance. Client du moteur BRouter |
| `profils/` | Profils de calcul écrits pour Loopy : vélo de route et course à pied |
| `gpx.py` | Deux exports distincts : l'itinéraire prévu (sans heure) et l'activité réalisée (horodatée) |
| `course.py`, `journal.py`, `progression.py`, `annonces.py` | La sortie : points GPS, pauses, splits, D+, journal partagé avec le service GPS, annonces vocales |
| `geo.py` | Distances, caps, altitude d'après la boucle, masquage du départ, réduction des tracés |
| `stockage.py` | Activités et boucles enregistrées sur le téléphone (écritures atomiques) |
| `compte.py` | Client du serveur pour l'app (même compte que le site) |

## Démarrer

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn serveur.app:app --reload    # API et site : http://localhost:8000
.venv/bin/python main.py                      # l'app sur PC (sortie simulée, touche D : détour)
.venv/bin/pytest                              # les tests
buildozer android debug                       # l'APK
```

L'app fonctionne **sans compte ni serveur** : génération, sortie, historique et GPX restent sur le téléphone. Le compte ajoute la synchronisation, la communauté et Strava.

## Documentation

- [docs/AUDIT.md](docs/AUDIT.md) : l'existant, la cause de la limite géographique, le plan, le choix du moteur
- [docs/CONFIGURATION.md](docs/CONFIGURATION.md) : variables d'environnement, Strava, e-mails, mise en production, BRouter, tuiles, APK
- [docs/BILAN.md](docs/BILAN.md) : ce qui est terminé, les tests réellement exécutés, ce qui demande une intervention extérieure
- [docs/V05.md](docs/V05.md) : version 0.5, après les essais sur téléphone (crash à l'enregistrement, navigation, dénivelé, GPX, Strava)
- [website/README.md](website/README.md) : le site
- [logo/kit/GUIDE.md](logo/kit/GUIDE.md) : le logo et l'identité Sauge & Pêche

## Données et licences

- Cartes et itinéraires : © les contributeurs [OpenStreetMap](https://www.openstreetmap.org/copyright) (ODbL), attribution affichée dans l'app et le site.
- Calcul des itinéraires : [BRouter](https://github.com/abrensch/brouter) (MIT). `profils/loopy-velo-route.brf` est dérivé de son profil `fastbike`.
- Recherche de lieux : Nominatim (OSM).
- Polices : Barlow Condensed et Atkinson Hyperlegible, sous licence OFL (`polices/`).
