# Loopy

Application Android (Kivy) qui génère, **hors-ligne**, des boucles de course d'une distance et d'un
dénivelé voulus, puis suit la course : carte centrée sur toi, chrono, allure, vitesse,
D+, progression sur la boucle, splits par km annoncés à la voix, et export GPX.

## Démarrage

```bash
# 1. Données de la zone (une fois, sur PC avec internet) -> data.db
pip install -r requirements-data.txt
python prepare_data.py --lat 44.823 --lon -0.445 --rayon 5000

# 2. Test sur PC : un coureur simulé suit la boucle (touche D : détour hors du parcours)
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python main.py
.venv/bin/pytest            # tests de la logique (sans Kivy)

# 3. APK (Linux ou WSL) -> bin/
buildozer android debug
```

## Organisation

| Fichier | Rôle |
|---|---|
| `core.py` | Carte (data.db) et génération de boucles : Dijkstra aller/retour, poids des pentes ajusté au D+ voulu |
| `course.py` | Une course : points horodatés, pauses, splits, vitesse, D+ |
| `journal.py` | Course en cours dans un fichier sqlite partagé avec le service GPS ; rejouable après un crash |
| `progression.py` | Position sur la boucle, km restants, détection de sortie du parcours |
| `annonces.py` | Annonces vocales (splits, sortie du parcours) |
| `gpx.py`, `stockage.py` | Export GPX ; historique (un fichier JSON par activité, écritures atomiques) |
| `geo.py` | Distances, caps, projection locale |
| `service/suivi.py` | Service Android en premier plan : GPS + annonces, même écran éteint |
| `capteurs/` | GPS de l'app, boussole, voix, partage, simulateur PC |
| `ui/` | Écrans Kivy (préparation, course, historique, détail), widget carte, thèmes jour/nuit et animations (`ui/widgets.py`), symbole du logo (`ui/logo.py`) |
| `polices/` | Barlow Condensed (chiffres) et Atkinson Hyperlegible (texte), licence OFL |
| `logo/` | Kit du logo dans `logo/kit/` (SVG, icônes, guide `GUIDE.md`) ; `python logo/kit/construire.py` le refait, avec l'icône et l'écran de lancement Android (`logo/icone.png`, `logo/lancement.png`). Outils de dev : `pip install skia-pathops fonttools cairosvg pillow` |

Pendant une course, le service (ou le simulateur sur PC) écrit chaque position dans le journal ;
l'écran de course relit ce journal toutes les 0,5 s. Si l'app est tuée, la course continue dans le
service et est proposée à la reprise au prochain lancement.

## Mettre une course sur Strava

Profil → toucher une course → **Exporter GPX** : le fichier est enregistré dans
`Téléchargements/Loopy` et le menu Partager s'ouvre. L'app mobile Strava n'importe pas de fichiers :
l'import se fait sur **strava.com → (+) → Importer une activité → Fichier**.

L'upload direct via l'API Strava (`POST /api/v3/uploads`, `data_type=gpx`) pourra s'ajouter plus tard :
le GPX est déjà au bon format et chaque activité a un champ `strava_id` prévu pour ça.
