# Audit du projet existant et choix techniques

## 1. Ce qui existait (version 0.3, commit `1d2e83c`)

| Élément | Constat |
|---|---|
| Langage, cadre | Python 3.11, **Kivy 2.3** (app Android construite avec buildozer). Pas de serveur ni de site. |
| Architecture | Logique métier en Python pur et testée (`course.py`, `journal.py`, `progression.py`, `gpx.py`, `stockage.py`, `geo.py`) ; écrans dans `ui/` ; capteurs Android dans `capteurs/` ; service GPS en premier plan (`service/suivi.py`) qui enregistre la sortie même écran éteint. Bonne base, gardée telle quelle. |
| Cartographie | Fond « maison » : les rues de `data.db` dessinées en traits, sans tuiles. |
| Génération des boucles | `core.py` : Dijkstra aller, puis retour pénalisé, sur un graphe chargé en mémoire depuis `data.db`. |
| **Limite géographique** | **Cause trouvée** : `data.db` est préparé une fois sur PC par `prepare_data.py` (osmnx) pour **un cercle de 5 km autour de Pessac** (44.823, -0.445), puis embarqué dans l'APK. Hors de ce cercle, l'app ramenait le départ « au centre de la zone ». La distance maximale était bornée à 4 × le rayon, soit 20 km. Le réseau embarqué était le réseau piéton (`network_type="walk"`) : aucun profil vélo. |
| Téléchargement GPX | Export de l'**activité réalisée** (points horodatés, un segment par pause) vers Téléchargements/Loopy, puis partage. **Pas d'export de l'itinéraire prévu.** |
| Comptes, profil | Aucun compte. Un « profil » local : l'historique des courses. |
| Strava | Aucune intégration. Un champ `strava_id` réservé dans chaque activité. |
| Données | Fichiers JSON locaux, écritures atomiques, migration de l'ancien format. Solide. |
| Performances | Chargement du graphe entier au démarrage, plusieurs secondes sur téléphone ; mémoire proportionnelle à la zone. Impossible à étendre au monde. |
| Sécurité | Pas de réseau, donc peu de surface. Aucune permission `INTERNET`. |

**Conservé et amélioré** : suivi de sortie (service GPS, pauses, splits, voix, reprise après un crash), historique, export GPX de l'activité, thèmes jour et nuit, logo et identité Sauge & Pêche, animations.
**Remplacé** : `core.py`, `prepare_data.py` et `data.db`, c'est-à-dire la génération dans une zone figée, par la génération mondiale décrite plus bas.

## 2. Plan d'intervention suivi

1. Moteur de génération mondial, sans zone codée en dur (`boucles.py`, profils `profils/*.brf`).
2. Parcours de création : sport, puis distance, puis départ, puis plusieurs boucles.
3. Profils vélo de route et course à pied, revêtement et indicateur de confiance.
4. Deux exports GPX distincts. Activités synchronisées. Strava par OAuth côté serveur.
5. Refonte des écrans de l'app : navigation à cinq onglets, carte sur tuiles OpenStreetMap.
6. Serveur : comptes, profils, historique, communauté, confidentialité (`serveur/`).
7. Site web (`website/`), servi par le même serveur, sur le même système de comptes.

## 3. Choix du moteur d'itinéraires

Comparaison faite en novembre 2026, avec les documentations officielles et des essais réels depuis cette machine.

| Solution | Couverture | Personnalisation | Coût, limites | Essai |
|---|---|---|---|---|
| **Graphe OSM local** (Overpass, puis notre Dijkstra) | Monde | Totale | Gratuit, mais le serveur public Overpass est saturé | Requête de 1 Ko : **39 s**, puis « at capacity ». Sa page d'état demande de ne pas l'utiliser pour du trafic automatisé. Écarté. |
| **GraphHopper** (API hébergée) | Monde | Excellente (*custom models*) | Gratuit : 500 crédits par jour, **usage non commercial**, **sans mode flexible**, donc sans *custom model* ni boucle orientée | Écarté pour l'offre hébergée. Reste une option en auto-hébergement. |
| **OpenRouteService** | Monde | Profils fixes et pondérations (`green`, `quiet`) | Clé gratuite. Boucles natives **limitées à 100 km** | Non testé (pas de clé). Bonne alternative. |
| **BRouter** | Monde (données OSM mondiales) | **Profils scriptables envoyés par le client** | Logiciel libre (MIT). Serveur public sans clé pour un usage léger. Auto-hébergeable (Java et fichiers de données par tuiles de 5°) | Réponse en **0,3 s**, altitude et D+ fournis, **étiquettes OSM par tronçon** (revêtement, type de voie, accès). **Retenu.** |

**Pourquoi BRouter** :
- Nos deux profils (`profils/loopy-velo-route.brf`, `profils/loopy-course.brf`) sont écrits pour Loopy et envoyés au moteur : c'est le niveau de personnalisation demandé.
- Le moteur renvoie les vraies étiquettes OSM, ce qui permet d'afficher le revêtement avec un indicateur de confiance (étiqueté, déduit ou inconnu).
- Aucune clé, donc rien de secret dans l'app.
- Le passage en production consiste à changer une URL vers sa propre instance (voir `docs/CONFIGURATION.md`).

**Limite constatée** : le serveur public `brouter.de` limite les clients trop actifs (« Please, retry later! », code 403) après quelques dizaines de requêtes rapprochées. Le client réessaie avec un délai, et le nombre de requêtes par génération a été réduit d'environ 24 à environ 8, grâce au calibrage décrit plus bas. **Pour des milliers d'utilisateurs, une instance BRouter propre est indispensable.**

## 4. La génération de boucles (`boucles.py`)

Les notions sont séparées, comme demandé :
- **Position de départ** : le GPS, un point touché sur la carte ou un lieu cherché (Nominatim). Jamais une zone fixe.
- **Distance cible** : la distance demandée.
- **Zone de recherche** : un cercle qui passe par le départ. Son rayon de départ vaut `distance / (2π × facteur de détour)`, avec un facteur de 1,25 à vélo et 1,3 en course. Il est ensuite **corrigé d'après la distance réellement obtenue sur le réseau**. La première direction calibre le rayon, les suivantes partent du rayon corrigé. La zone s'agrandit donc d'elle-même pour 60 ou 100 km. Elle est affichée sur la carte et indépendante du zoom.
- **Réseau disponible** : celui du moteur, donc toutes les routes et chemins d'OpenStreetMap, filtrés par le profil du sport.
- **Distance réellement calculée** : affichée à côté de la distance demandée, avec l'écart en pourcentage.

Pour chacune des 5 directions explorées autour du départ :
1. 3 points de passage sur le cercle (5 au-delà de 30 km), puis retour au départ, en une seule requête.
2. Le rayon est ajusté jusqu'à 3 % de la cible, en 4 essais au plus.

Chaque boucle est notée, plus bas étant meilleur : `3 × écart de distance + 2 × part parcourue deux fois + (1 − qualité des voies pour le sport)`, plus un terme de relief si tu en demandes un.

Sont **écartées** :
- les boucles à plus de 20 % de la distance ;
- celles dont plus de 35 % du parcours est fait deux fois (allers-retours) ;
- celles qui ressemblent à plus de 60 % à une boucle déjà retenue.

Si rien ne convient, l'app **explique** pourquoi au lieu d'inventer un tracé. Si la distance exacte est impossible, elle propose la plus proche et le dit.

Les profils suppriment les détours dus aux points de passage (`correctMisplacedViaPoints`) : pas d'aller-retour en cul-de-sac pour toucher un point. Ils respectent aussi les sens uniques et les accès (`access`, `bicycle`, `foot`).

## 5. Autres choix

| Besoin | Choix | Raison |
|---|---|---|
| Fond de carte de l'app | Tuiles OpenStreetMap, cache disque | Monde entier. Une zone déjà vue s'affiche hors connexion. Attribution affichée. |
| Fond de carte du site | Leaflet 1.9.4 et tuiles OSM | Léger et standard. |
| Recherche de lieu | Nominatim (OSM) | Solution de secours quand le GPS est refusé ou absent. Une requête par recherche. |
| Serveur | FastAPI et SQLite (mode WAL) | Même langage que l'app : le code métier (`boucles.py`, `gpx.py`, `geo.py`) est **partagé** entre l'app et le serveur. Un seul fichier de base de données, facile à sauvegarder. |
| Comptes | E-mail et mot de passe haché (scrypt, sel aléatoire). Jetons aléatoires stockés hachés | L'app envoie le jeton en en-tête `Bearer`, le site en cookie HttpOnly SameSite=Lax avec en-tête anti-CSRF. **Un seul système de comptes.** |
| Strava | OAuth 2 côté serveur, `POST /uploads` puis suivi du traitement | Le secret client ne quitte jamais le serveur. Les jetons sont rafraîchis automatiquement. |
| Site | HTML, CSS et JavaScript (modules ES) sans étape de construction | Servi par le même serveur, donc même origine et cookies simples. Rien à compiler. Voir `website/README.md`. |
