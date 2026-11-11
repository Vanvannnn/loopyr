# Graph Report - starvaclaude  (2026-11-10)

## Corpus Check
- Corpus is ~45,483 words - fits in a single context window. You may not need a graph.

## Summary
- 1099 nodes · 2665 edges · 64 communities (48 shown, 16 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 243 edges (avg confidence: 0.88)
- Token cost: 165,618 input · 0 output

## Community Hubs (Navigation)
- App Core & Storage
- Run Progress & Announcements
- Site Pages & API
- App Screens Modules
- Run Tracking Tests
- App Account Client
- Map Tiles & Trace
- Server Read Endpoints
- Profile Screen
- Community Screen
- Strava Integration
- Server Tests
- Auth & Rate Limits
- Run Screen
- History Screen
- Android Sensors
- Site Common JS
- Animated Backgrounds
- Loop Results Screen
- API Models
- Loop Engine & Search
- BRouter Client
- Loop Scoring
- Home Screen & Logo
- App Lifecycle & Sync
- Geo Helpers
- Run Journal
- Loop Engine Tests
- Site Home & Account Pages
- Stats Widgets
- Project Overview Docs
- Voice Service
- Bottom Sheets
- Server Write Endpoints
- Splits & Segments
- Activity Detail Screen
- Loop Creation Page
- Build & Test Docs
- Navigation & Theme
- Distance Screen
- Stepper Widget
- Community Page
- Website README
- Deployment Config
- Android Location Listener
- Compass Sensor
- GPS Sensor
- Server Delete Endpoints
- Routing Engine Choice
- Loop Drawing Animation
- Sport Picker Screen
- Server Dependencies
- Legacy Audit
- Countdown Overlay
- Site Preview Tiles
- Activity Page
- Site Map Module
- Public Profile Page
- Activity Upload Endpoint
- File Share & URLs
- Rate Limiter
- Strava OAuth Return

## God Nodes (most connected - your core abstractions)
1. `Bouton` - 45 edges
2. `lab()` - 39 edges
3. `StarvaApp` - 37 edges
4. `EcranCourse` - 37 edges
5. `Mon espace page` - 34 edges
6. `Trace` - 32 edges
7. `Course` - 30 edges
8. `Compte` - 25 edges
9. `nombre()` - 25 edges
10. `Segmente` - 24 edges

## Surprising Connections (you probably didn't know these)
- `Dynamic search zone (calibrated radius)` --implements--> `generer()`  [INFERRED]
  docs/AUDIT.md → boucles.py
- `GraphHopper hosted API (rejected)` --semantically_similar_to--> `BRouter routing engine (MIT)`  [INFERRED] [semantically similar]
  docs/AUDIT.md → README.md
- `Local OSM graph via Overpass (rejected)` --semantically_similar_to--> `BRouter routing engine (MIT)`  [INFERRED] [semantically similar]
  docs/AUDIT.md → README.md
- `OpenRouteService (alternative)` --semantically_similar_to--> `BRouter routing engine (MIT)`  [INFERRED] [semantically similar]
  docs/AUDIT.md → README.md
- `Loop scoring and rejection rules` --references--> `qualite()`  [INFERRED]
  docs/AUDIT.md → boucles.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Routing engine selection (BRouter vs alternatives)** — docs_audit_brouter_choice, readme_brouter, docs_audit_local_osm_graph_overpass, docs_audit_graphhopper, docs_audit_openrouteservice [EXTRACTED 1.00]
- **Worldwide loop generation pipeline** — boucles_generer, docs_audit_dynamic_search_zone, docs_audit_five_directions, docs_audit_loop_scoring, docs_bilan_surface_confidence, readme_brouter [INFERRED 0.85]
- **Strava OAuth and GPX upload flow** — docs_audit_strava_oauth_server, serveur_strava, docs_configuration_strava_app_setup, docs_configuration_strava_credentials, gpx_gpx, docs_bilan_fake_strava [INFERRED 0.85]
- **Account authentication flow** — website_inscription, website_connexion, website_mot_de_passe, website_reinitialiser, website_espace [INFERRED 0.95]
- **Getting an activity onto Strava** — website_espace, website_strava, website_strava_ok, website_espace_strava_link, website_espace_activities_tab [INFERRED 0.85]
- **Community social interactions** — website_communaute, website_u, website_activite, website_espace_feed_tab [INFERRED 0.85]

## Communities (64 total, 16 thin omitted)

### Community 0 - "App Core & Storage"
Cohesion: 0.06
Nodes (28): Outing and loop sync with account, Two distinct GPX exports (route vs activity), exportable(), gpx(), gpx_itineraire(), heure_iso(), nom_itineraire(), _pt() (+20 more)

### Community 1 - "Run Progress & Announcements"
Cohesion: 0.09
Nodes (17): Annonceur, phrase_allure(), cercle(), Simulateur, Plan, Progression, _projeter(), carre() (+9 more)

### Community 2 - "Site Pages & API"
Cohesion: 0.07
Nodes (31): envoyer_mail(), API /api/activites/{id}, API /api/activites/{id}/jaime, Se connecter page, API /api/sessions, Login form, API /api/itineraires, Mon espace page (+23 more)

### Community 3 - "App Screens Modules"
Cohesion: 0.12
Nodes (5): Five-tab app navigation, avec_zoom(), confirmer(), desarmer(), hexa_de()

### Community 4 - "Run Tracking Tests"
Cohesion: 0.16
Nodes (16): Course, fmt_temps(), ligne_droite(), courir(), test_denivele_avec_hysteresis(), test_distance_et_duree(), test_formats(), test_pause_gele_duree_et_distance_sans_trait_droit() (+8 more)

### Community 5 - "App Account Client"
Cohesion: 0.11
Nodes (7): Compte, ErreurCompte, Altitudes, test_altitudes_depuis_la_boucle(), test_compte_synchronisation_communaute(), test_serveur_injoignable(), url()

### Community 6 - "Map Tiles & Trace"
Cohesion: 0.10
Nodes (7): ecart(), inverse(), mercator(), Trace, disque(), ligne(), Tuiles

### Community 7 - "Server Read Endpoints"
Cohesion: 0.09
Nodes (26): reduire(), activite_visible(), avatar_url(), carte_utilisateur(), chercher_utilisateurs(), clause_visible(), commentaires(), commenter() (+18 more)

### Community 8 - "Profile Screen"
Cohesion: 0.13
Nodes (12): EcranProfil, go(), fini(), fini(), fini(), en_fond(), fil(), section() (+4 more)

### Community 9 - "Community Screen"
Cohesion: 0.11
Nodes (8): fmt_allure(), EcranCommunaute, chrono(), allure_moy(), rythme(), Bouton, nombre(), style()

### Community 10 - "Strava Integration"
Cohesion: 0.10
Nodes (19): act_dict(), avec_statut(), envoyer_strava(), exiger_strava(), gpx_d_activite(), mon_activite(), page_retour(), statut_envoi() (+11 more)

### Community 11 - "Server Tests"
Cohesion: 0.12
Nodes (16): activite(), client(), compte(), FauxStrava, Rep, test_activites_visibilite_et_vie_privee(), test_fil_jaimes_commentaires(), test_generation_par_le_serveur() (+8 more)

### Community 12 - "Auth & Rate Limits"
Cohesion: 0.16
Nodes (16): connecter(), deconnecter(), entetes(), inscrire(), ip(), jeton_de(), limiter(), moi_public() (+8 more)

### Community 13 - "Run Screen"
Cohesion: 0.18
Nodes (4): Cap, EcranCourse, finir(), reprendre()

### Community 14 - "History Screen"
Cohesion: 0.11
Nodes (8): date_fr(), debut(), duree_longue(), EcranHistorique, km_par_semaine(), Ligne, lundi(), unite()

### Community 15 - "Android Sensors"
Cohesion: 0.13
Nodes (6): activite(), systeme(), version_sdk(), arreter_service(), demarrer_service(), exporter()

### Community 16 - "Site Common JS"
Cohesion: 0.12
Nodes (15): allure(), api(), echapper(), entete(), exigerConnexion(), gpxItineraire(), ICONES, km() (+7 more)

### Community 17 - "Animated Backgrounds"
Cohesion: 0.11
Nodes (5): Bande, echelle(), fond(), pulser(), teinter()

### Community 18 - "Loop Results Screen"
Cohesion: 0.15
Nodes (3): alleger(), EcranPlan, Repartition

### Community 19 - "API Models"
Cohesion: 0.14
Nodes (12): Activite, Commentaire, Connexion, Inscription, ModifActivite, modifier_activite(), modifier_itineraire(), modifier_moi() (+4 more)

### Community 20 - "Loop Engine & Search"
Cohesion: 0.15
Nodes (4): chercher_lieu(), contexte_ssl(), _une_boucle(), 5 explored directions with via points

### Community 21 - "BRouter Client"
Cohesion: 0.15
Nodes (6): BRouter, ErreurItineraire, traduire_erreur(), troncons(), test_erreurs_lisibles(), test_lecture_reponse_brouter()

### Community 22 - "Loop Scoring"
Cohesion: 0.13
Nodes (10): noter(), qualite(), recouvrement(), resume_voies(), revetement(), type_voie(), Surface and confidence indicator, test_deux_sports_deux_preferences() (+2 more)

### Community 23 - "Home Screen & Logo"
Cohesion: 0.14
Nodes (5): EcranAccueil, boucles(), _cadre(), goutte(), Symbole

### Community 24 - "App Lifecycle & Sync"
Cohesion: 0.19
Nodes (3): StarvaApp, travail(), travail()

### Community 25 - "Geo Helpers"
Cohesion: 0.18
Nodes (4): Community (follow, feed, likes, comments), cap_entre(), haversine(), rogner()

### Community 26 - "Run Journal"
Cohesion: 0.21
Nodes (4): appliquer(), Journal, test_rejouer_reconstruit_la_course(), test_vider()

### Community 27 - "Loop Engine Tests"
Cohesion: 0.26
Nodes (11): generer(), recouvrement_entre(), Faux, test_aller_retour_refuse_avec_explication(), test_boucle_fermee_au_depart_et_a_la_bonne_distance(), test_calibrage_peu_de_requetes(), test_distance_et_sport_valides(), test_moteur_en_echec() (+3 more)

### Community 28 - "Site Home & Account Pages"
Cohesion: 0.15
Nodes (16): Profile, preferences and privacy form, Loopy home page, Profile and community pitch, Real generated loop examples, Itinerary vs activity GPX exports, Hero animated loop demo, Six steps milestones section, Créer un compte page (+8 more)

### Community 29 - "Stats Widgets"
Cohesion: 0.16
Nodes (3): Semaines, Barre, Croissance

### Community 30 - "Project Overview Docs"
Cohesion: 0.15
Nodes (13): Audit and technical choices, Intervention plan (7 steps), Leaflet 1.9.4, OSM tiles with disk cache (app map), Refonte report (version 0.4), Map tile provider (OSM usage policy), Barlow Condensed and Atkinson Hyperlegible fonts (OFL), Loopy (+5 more)

### Community 31 - "Voice Service"
Cohesion: 0.23
Nodes (3): chaine(), Voix, principal()

### Community 33 - "Server Write Endpoints"
Cohesion: 0.17
Nodes (9): aimer(), changer_avatar(), creer_itineraire(), Demande, generer_boucles(), NouvelItineraire, strava_connexion(), suivre() (+1 more)

### Community 34 - "Splits & Segments"
Cohesion: 0.21
Nodes (3): barre_titre(), Segmente, Splits

### Community 36 - "Loop Creation Page"
Cohesion: 0.18
Nodes (12): Créer une boucle page, Distance picker with suggestions, API /api/boucles, Loop generation and proposals, Itinerary GPX download, Loop details (road types, surface bars), Nominatim place search, Relief selector (plat/vallonné) (+4 more)

### Community 37 - "Build & Test Docs"
Cohesion: 0.18
Nodes (9): Fake Strava test double, Tests executed (60 pytest + real generations), Not verified here (phone, real Strava, SMTP, third-party GPX), APK build (buildozer.spec), Android app (Kivy, buildozer), certifi, kivy[base]==2.3.1, plyer (+1 more)

### Community 39 - "Distance Screen"
Cohesion: 0.25
Nodes (3): EcranDistance, fil(), lire_distance()

### Community 41 - "Community Page"
Cohesion: 0.18
Nodes (11): Communauté page, API /api/communaute/activites, API /api/communaute/itineraires, API /api/utilisateurs, Recent public activities mosaic, Shared loops mosaic, Sport filter (Tous/Course/Vélo), Athlete search (+3 more)

### Community 42 - "Website README"
Cohesion: 0.20
Nodes (7): Server security measures, Account pages (connexion, inscription, mot-de-passe, reinitialiser), Community pages (communaute, u, activite), creer.html loop creation page, espace.html personal space, index.html home page, Loopy website README

### Community 43 - "Deployment Config"
Cohesion: 0.27
Nodes (9): External interventions required, Known limits (in-memory rate limiter, plaintext Strava tokens, uncapped tile cache), Server environment variables, LOOPY_DONNEES, LOOPY_URL_PUBLIQUE, SMTP settings, Strava application setup and upload flow, STRAVA_CLIENT_ID / STRAVA_CLIENT_SECRET (+1 more)

### Community 47 - "Server Delete Endpoints"
Cohesion: 0.25
Nodes (7): itin_de(), ne_plus_aimer(), ne_plus_suivre(), strava_deconnexion(), supprimer_compte(), supprimer_itineraire(), revoquer()

### Community 48 - "Routing Engine Choice"
Cohesion: 0.29
Nodes (8): correctMisplacedViaPoints, GraphHopper hosted API (rejected), Local OSM graph via Overpass (rejected), OpenRouteService (alternative), LOOPY_BROUTER, Self-hosted BRouter instance, BRouter routing engine (MIT), loopy-velo-route.brf profile (derived from fastbike)

### Community 51 - "Server Dependencies"
Cohesion: 0.29
Nodes (5): Loopy server (FastAPI, SQLite), fastapi>=0.115, httpx>=0.27, python-multipart>=0.0.9, uvicorn>=0.30

### Community 52 - "Legacy Audit"
Cohesion: 0.33
Nodes (3): Legacy core.py Dijkstra on data.db graph, Existing version 0.3 (commit 1d2e83c), Installation, launch and configuration

### Community 54 - "Site Preview Tiles"
Cohesion: 0.47
Nodes (3): apercu(), tuileActivite(), tuileItineraire()

### Community 55 - "Activity Page"
Cohesion: 0.33
Nodes (6): Activité page, Activity stats (distance, duration, pace, D+), Comments section and form, API /api/activites/{id}/commentaires, J'aime button, Leaflet route map

### Community 57 - "Public Profile Page"
Cohesion: 0.33
Nodes (6): Public user profile page, Visible activities mosaic, API /api/utilisateurs/{nom}, API /api/utilisateurs/{nom}/abonnement, Profile header with follow button, Per-sport stats

### Community 61 - "Strava OAuth Return"
Cohesion: 0.67
Nodes (3): Strava account link/unlink, Strava OAuth return page, Strava OAuth status message (ok/refus/permission/erreur)

## Ambiguous Edges - Review These
- `strava.py` → `httpx>=0.27`  [AMBIGUOUS]
  requirements-serveur.txt · relation: conceptually_related_to

## Knowledge Gaps
- **55 isolated node(s):** `Nominatim place search`, `Barlow Condensed and Atkinson Hyperlegible fonts (OFL)`, `Existing version 0.3 (commit 1d2e83c)`, `Local OSM graph via Overpass (rejected)`, `GraphHopper hosted API (rejected)` (+50 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 336 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **16 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Trace` connect `Map Tiles & Trace` to `Splits & Segments`, `App Screens Modules`, `Activity Detail Screen`, `Profile Screen`, `Run Screen`, `Loop Drawing Animation`, `Animated Backgrounds`, `Loop Results Screen`, `Home Screen & Logo`?**
  _High betweenness centrality (0.079) - this node is a cross-community bridge._
- **Are the 8 inferred relationships involving `Bouton` (e.g. with `EcranAccueil` and `EcranDistance`) actually correct?**
  _`Bouton` has 8 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Nominatim place search`, `Barlow Condensed and Atkinson Hyperlegible fonts (OFL)`, `Existing version 0.3 (commit 1d2e83c)` to the rest of the system?**
  _55 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `App Core & Storage` be split into smaller, more focused modules?**
  _Cohesion score 0.05859969558599695 - nodes in this community are weakly interconnected._
- **Why does `gpx_itineraire()` connect `App Core & Storage` to `Site Common JS`, `Loop Results Screen`, `Site Pages & API`, `App Screens Modules`?**
  _High betweenness centrality (0.073) - this node is a cross-community bridge._
- **Are the 17 inferred relationships involving `StarvaApp` (e.g. with `BRouter` and `Gps`) actually correct?**
  _`StarvaApp` has 17 INFERRED edges - model-reasoned connections that need verification._

### Low-confidence Hints
_AMBIGUOUS edges — the extractor was unsure. Verify before acting on these._

- **What is the exact relationship between `strava.py` and `httpx>=0.27`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._