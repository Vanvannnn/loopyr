# Site web de Loopy

Le site présente l'app. Il permet aussi d'utiliser Loopy depuis un navigateur : créer une boucle, gérer son compte, retrouver ses parcours et ses sorties, rejoindre la communauté. Il est servi par le serveur Loopy (`serveur/app.py`), sur la même origine que l'API : **même compte que l'app**.

Il n'y a ni compilation ni dépendances npm. Pages HTML, une feuille de style et des modules JavaScript natifs. Leaflet 1.9.4 est copié dans assets/vendor/leaflet (pas de CDN : aucune adresse IP de visiteur envoyée à un tiers).

| Fichier | Contenu |
|---|---|
| `index.html` | Page d'accueil : boucle réelle animée, les six étapes, les deux profils, des exemples réels, les deux exports, profil et communauté |
| `creer.html` | Créer une boucle : sport, distance, départ (géolocalisation HTTPS, point sur la carte ou recherche), propositions, GPX de l'itinéraire, enregistrement |
| `connexion.html`, `inscription.html`, `mot-de-passe.html`, `reinitialiser.html` | Compte (API `/api/sessions`, `/api/comptes`, `/api/mot-de-passe/*`) |
| `espace.html` | Espace personnel : activités (visibilité, GPX, envoi vers Strava), parcours (favoris, partage, GPX), statistiques, fil, abonnements, profil et confidentialité, Strava, suppression du compte |
| `communaute.html`, `u.html`, `activite.html` | Boucles partagées, sorties publiques, recherche de sportifs, profil public (suivre), activité (j'aime, commentaires) |
| `strava-ok.html` | Page de retour après l'autorisation Strava demandée depuis l'app |
| `assets/css/loopy.css` | Couleurs (Sauge et Pêche, mode sombre), typographie, composants |
| `assets/js/commun.js` | Appels à l'API, formats français, GPX de l'itinéraire, pictogrammes |
| `assets/js/carte.js`, `assets/js/apercu.js` | Cartes Leaflet aux couleurs de Loopy, aperçus SVG des tracés |
| `assets/exemples.json` | Boucles réelles du moteur, régénérées avec `python outils/exemples_site.py` |

Développement : lance `uvicorn serveur.app:app --reload` à la racine du projet, puis ouvre http://localhost:8000.

Accessibilité et mouvement :
- les animations respectent `prefers-reduced-motion` ;
- le focus clavier est visible ;
- les couleurs sont choisies pour un contraste suffisant, en clair comme en sombre ;
- chaque graphique a un équivalent textuel.
