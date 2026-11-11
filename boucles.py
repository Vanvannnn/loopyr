"""Génération de boucles partout dans le monde, depuis la position réelle. Python pur (urllib).

Le calcul d'itinéraire est fait par BRouter (https://brouter.de, données OpenStreetMap mondiales) avec nos
deux profils (profils/*.brf) : vélo de route et course à pied. Ce module choisit où passer :
  - la position de départ est celle donnée (GPS ou point choisi), jamais une zone codée en dur ;
  - la zone de recherche est un cercle qui passe par le départ, dont le rayon vient de la distance voulue,
    puis est corrigé d'après la distance réellement obtenue sur le réseau (2 ou 3 essais) ;
  - plusieurs directions sont explorées autour du départ : une proposition par direction ;
  - chaque proposition est notée (écart à la distance, portions parcourues deux fois, qualité des voies
    pour le sport, relief voulu) et les boucles incohérentes sont écartées plutôt que proposées.
Le serveur BRouter est configurable (variable LOOPY_BROUTER) : le serveur public dépanne, la production
utilise sa propre instance (voir docs/CONFIGURATION.md)."""
import json, math, os, random, threading, time, urllib.error, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

from geo import Plan, haversine

PROFILS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profils")
AGENT = "Loopy/0.4 (+https://github.com/Vanvannnn/loopy)"

SPORTS = {
    "velo": dict(nom="vélo", profil="loopy-velo-route", suggestions=(20, 30, 50, 75, 100), mini=3, maxi=300,
                 detour=1.25, gpx="cycling", strava="Ride"),
    "course": dict(nom="course à pied", profil="loopy-course", suggestions=(5, 10, 15, 20), mini=1, maxi=100,
                   detour=1.3, gpx="running", strava="Run"),
}

REVETU = {"asphalt", "concrete", "paved", "concrete:plates", "concrete:lanes", "chipseal", "metal", "wood",
          "paving_stones", "tartan", "rubber"}
PAVE = {"sett", "cobblestone", "unhewn_cobblestone", "bricks", "brick"}
NON_REVETU = {"unpaved", "gravel", "fine_gravel", "compacted", "dirt", "earth", "ground", "grass", "sand", "mud",
              "pebblestone", "woodchips", "rock", "rocks", "grass_paver", "stone", "shells", "ice", "snow"}
# sans étiquette surface, ces routes sont goudronnées dans l'immense majorité des cas : on le dit « déduit »
ROUTES = {"motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential", "living_street",
          "service", "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link"}
GRANDS_AXES = {"trunk", "primary", "secondary", "trunk_link", "primary_link", "secondary_link"}
PIETON = {"footway", "pedestrian", "path", "track", "steps", "bridleway"}


class ErreurItineraire(Exception):
    """Le moteur n'a pas pu calculer (point hors réseau, serveur indisponible…). Message lisible."""


# --- le moteur : BRouter ---
class BRouter:
    def __init__(self, url=None, timeout=45):
        self.url = (url or os.environ.get("LOOPY_BROUTER") or "https://brouter.de/brouter").rstrip("/")
        self.timeout, self.ids, self.verrou = timeout, {}, threading.Lock()

    def _http(self, url, donnees=None):
        """(code HTTP, texte). Les refus temporaires (serveur chargé, trop de requêtes) sont réessayés."""
        req = urllib.request.Request(url, data=donnees, headers={"User-Agent": AGENT})
        for attente in (2, 5, 0):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout, context=contexte_ssl()) as r:
                    return r.status, r.read().decode("utf-8")
            except urllib.error.HTTPError as e:  # BRouter explique l'erreur dans le corps
                try:
                    corps = e.read().decode("utf-8", "replace")
                except Exception:
                    corps = ""
                if e.code not in (403, 429, 502, 503, 504) or not attente:
                    return e.code, corps
            except (urllib.error.URLError, OSError) as e:
                if not attente:
                    raise ErreurItineraire("Pas de connexion au moteur d'itinéraires") from e
            time.sleep(attente)
        raise ErreurItineraire("Moteur d'itinéraires indisponible")

    def _profil(self, nom, perime=None):
        """Nos profils sont envoyés une fois au serveur, qui les garde un temps sous un identifiant.
        perime : identifiant refusé par le serveur ; un seul fil le renvoie, les autres prennent le nouveau."""
        with self.verrou:
            if nom not in self.ids or self.ids[nom] == perime:
                with open(os.path.join(PROFILS, nom + ".brf"), "rb") as f:
                    code, texte = self._http(self.url + "/profile", f.read())
                try:
                    rep = json.loads(texte)
                except ValueError:
                    raise ErreurItineraire("Moteur d'itinéraires indisponible (profil non accepté)")
                if rep.get("error"):
                    raise ErreurItineraire(f"Profil {nom} refusé : {rep['error']}")
                self.ids[nom] = rep["profileid"]
            return self.ids[nom]

    def itineraire(self, points, sport, alternative=0):
        """points : [(lat, lon), …] dans l'ordre ; alternative : 0 = la route du moteur, 1 à 3 = ses variantes. Renvoie coords, ele, distance (m), montee (m),
        troncons [(longueur m, étiquettes OSM)] et hints : les consignes [indice du point, commande, sortie de
        rond-point, distance jusqu'à la suivante, angle] (commandes de BRouter, VoiceHint)."""
        lonlats = "|".join(f"{lon:.6f},{lat:.6f}" for lat, lon in points)
        perime = None
        for essai in range(2):
            pid = self._profil(SPORTS[sport]["profil"], perime)
            # timode=2 : consignes de navigation (voicehints) calculées par le moteur sur le vrai réseau
            q = urllib.parse.urlencode({"lonlats": lonlats, "profile": pid, "alternativeidx": alternative, "format": "geojson",
                                        "timode": 2})
            code, texte = self._http(f"{self.url}?{q}")
            if code == 200 and texte.lstrip().startswith("{"):
                break
            if essai == 0 and code == 500 and not texte.strip():
                perime = pid  # réponse vide : le serveur a oublié notre profil, on le renvoie
                continue
            raise ErreurItineraire(traduire_erreur(texte))
        try:
            f = json.loads(texte)["features"][0]
        except (ValueError, KeyError, IndexError):
            raise ErreurItineraire(traduire_erreur(texte))
        p, pts = f["properties"], f["geometry"]["coordinates"]
        return {"coords": [(round(c[1], 6), round(c[0], 6)) for c in pts],
                "ele": [c[2] if len(c) > 2 else None for c in pts],
                "distance": float(p["track-length"]), "montee": float(p.get("filtered ascend") or 0),
                "troncons": troncons(p.get("messages") or []),
                "hints": [[int(h[0]), int(h[1]), int(h[2]), float(h[3]), float(h[4])]
                          for h in p.get("voicehints") or () if len(h) >= 5]}


def traduire_erreur(texte):
    t = texte.lower()
    if "not mapped" in t or "no track found" in t or "operation killed" in t:
        return "Pas de route ou de chemin praticable à cet endroit"
    if "datafile" in t or "not found" in t:
        return "Pas de données cartographiques pour cet endroit"
    return "Le moteur d'itinéraires a refusé la demande"


def troncons(messages):
    """Les « messages » BRouter : une ligne par tronçon, avec sa longueur et ses étiquettes OSM."""
    if len(messages) < 2:
        return []
    tete = messages[0]
    i_d, i_t = tete.index("Distance"), tete.index("WayTags")
    out = []
    for m in messages[1:]:
        tags = dict(x.split("=", 1) for x in m[i_t].split() if "=" in x)
        out.append((float(m[i_d]), tags))
    return out


_ssl = None


def contexte_ssl():
    """Sur Android, Python n'a pas les certificats du système : on prend ceux de certifi s'il est là."""
    global _ssl
    if _ssl is None:
        import ssl
        try:
            import certifi
            _ssl = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            _ssl = ssl.create_default_context()
    return _ssl


# --- analyse d'un itinéraire ---
def revetement(tags):
    """('revetu' | 'pave' | 'non_revetu' | 'inconnu', connu : la surface est-elle étiquetée ?)."""
    s = tags.get("surface", "").split(";")[0]
    if s in REVETU:
        return "revetu", True
    if s in PAVE:
        return "pave", True
    if s in NON_REVETU:
        return "non_revetu", True
    if tags.get("highway") in ROUTES or tags.get("tracktype") == "grade1":
        return "revetu", False  # déduit, jamais présenté comme certain
    return "inconnu", False


def type_voie(tags):
    hw = tags.get("highway", "")
    if hw == "cycleway" or tags.get("bicycle") == "designated" or tags.get("bicycle_road") == "yes":
        return "cyclable"
    if hw == "steps":
        return "escaliers"
    if hw in PIETON:
        return "chemin"
    if hw in GRANDS_AXES:
        return "grand_axe"
    return "rue"


def resume_voies(trs):
    """Mètres par revêtement et par type de voie, et part de surfaces réellement connues."""
    rev = dict.fromkeys(("revetu", "pave", "non_revetu", "inconnu"), 0.0)
    voies = dict.fromkeys(("cyclable", "chemin", "rue", "grand_axe", "escaliers"), 0.0)
    connu = deduit = total = 0.0
    for l, tags in trs:
        r, c = revetement(tags)
        rev[r] += l
        voies[type_voie(tags)] += l
        total += l
        if c:
            connu += l
        elif r == "revetu":
            deduit += l
    return {"revetement": rev, "voies": voies, "surface_connue": connu / total if total else 0.0,
            "surface_deduite": deduit / total if total else 0.0}


def qualite(resume, sport):
    """0 à 1 : part de la boucle sur des voies adaptées au sport."""
    total = sum(resume["voies"].values()) or 1
    rev, v = resume["revetement"], resume["voies"]
    if sport == "velo":  # vélo de route : du revêtu, peu de grands axes, des pistes cyclables en bonus
        bon = rev["revetu"] - 0.5 * v["grand_axe"] + 0.3 * v["cyclable"]
    else:  # course : chemins, parcs et voies piétonnes, rues calmes ; pas de grands axes ni d'escaliers
        bon = v["chemin"] + 0.6 * v["rue"] + 0.5 * v["cyclable"] - v["grand_axe"] - v["escaliers"]
    return max(0.0, min(1.0, bon / total))


def recouvrement(coords):
    """Part de la distance parcourue deux fois (dans un sens ou dans l'autre)."""
    vus, double, total = set(), 0.0, 0.0
    for a, b in zip(coords, coords[1:]):
        if a == b:
            continue
        cle = (min(a, b), max(a, b))
        l = haversine(a, b)
        total += l
        if cle in vus:
            double += l
        vus.add(cle)
    return double / total if total else 0.0


def cercle(depart, rayon, cap, n):
    """n points de passage sur un cercle de rayon donné qui passe par le départ, centré dans la direction cap."""
    plan = Plan(*depart)
    a = math.radians(cap)
    cx, cy = rayon * math.sin(a), rayon * math.cos(a)
    phi0 = a + math.pi  # angle du départ vu du centre
    return [plan.latlon(cx + rayon * math.sin(phi0 + 2 * math.pi * k / (n + 1)),
                        cy + rayon * math.cos(phi0 + 2 * math.pi * k / (n + 1))) for k in range(1, n + 1)]


# --- la génération ---
def _une_boucle(routeur, depart, distance, sport, cap, rayon0, essais=4):
    """Une direction : on ajuste le rayon jusqu'à approcher la distance voulue. Renvoie la meilleure ou None."""
    n = 3 if distance < 30000 else 5
    rayon, meilleure, derniere_erreur = rayon0, None, None
    for _ in range(essais):
        try:
            it = routeur.itineraire([depart, *cercle(depart, rayon, cap, n), depart], sport)
        except ErreurItineraire as e:  # point de passage dans l'eau, un champ… : on décale la direction
            derniere_erreur, cap = str(e), cap + 25
            continue
        it.update(cap=cap % 360, rayon=rayon)
        if meilleure is None or abs(it["distance"] - distance) < abs(meilleure["distance"] - distance):
            meilleure = it
        ecart = it["distance"] / distance
        if abs(ecart - 1) < 0.03:
            break
        rayon *= max(0.5, min(2.0, 1 / ecart))
    return meilleure or derniere_erreur


def noter(it, distance, sport, relief=None):
    """Plus petit = meilleur. Ajoute au dictionnaire les éléments de la note, pour les expliquer."""
    res = resume_voies(it["troncons"])
    ecart = abs(it["distance"] - distance) / distance
    rec = recouvrement(it["coords"])
    q = qualite(res, sport)
    score = 3 * ecart + 2 * rec + (1 - q)
    dpkm = it["montee"] / max(it["distance"] / 1000, 0.1)
    if relief == "plat":
        score += 0.6 * min(1.0, dpkm / 20)
    elif relief == "vallonne":
        score += 0.6 * (1 - min(1.0, dpkm / 20))
    it.update(resume_voies=res, ecart=ecart, recouvrement=rec, qualite=q, score=score)
    return it


def generer(depart, distance, sport, routeur=None, n=3, relief=None, graine=None, directions=5, paralleles=2):
    """Plusieurs boucles depuis depart (lat, lon) pour distance (m) et sport ('velo' | 'course').
    Renvoie {"propositions": [...] (la meilleure d'abord), "zone": {...}, "cible", "message"}.
    Chaque proposition : coords, ele, distance, montee, resume_voies, qualite, recouvrement, ecart, cap."""
    if sport not in SPORTS:
        raise ValueError("sport inconnu")
    s = SPORTS[sport]
    if not s["mini"] * 1000 <= distance <= s["maxi"] * 1000:
        raise ValueError(f"Distance entre {s['mini']} et {s['maxi']} km pour le {s['nom']}")
    routeur = routeur or BRouter()
    hasard = random.Random(graine)
    rayon0 = distance / (2 * math.pi * s["detour"])
    debut = hasard.uniform(0, 360)
    caps = [debut + k * 360 / directions for k in range(directions)]
    # la première direction calibre le rayon (le réseau allonge plus ou moins le cercle) : les suivantes
    # partent du rayon corrigé et tombent juste en 1 ou 2 requêtes au lieu de 3 ou 4
    bruts = [_une_boucle(routeur, depart, distance, sport, caps[0], rayon0)]
    if isinstance(bruts[0], dict):
        rayon0 = bruts[0]["rayon"] * distance / bruts[0]["distance"]
    with ThreadPoolExecutor(paralleles) as ex:
        bruts += list(ex.map(lambda c: _une_boucle(routeur, depart, distance, sport, c, rayon0), caps[1:]))
    erreurs = [b for b in bruts if isinstance(b, str)]
    cands = [noter(b, distance, sport, relief) for b in bruts if isinstance(b, dict)]
    # incohérentes : très loin de la distance, ou faites en bonne partie d'allers-retours
    bonnes = sorted((c for c in cands if c["ecart"] <= 0.2 and c["recouvrement"] <= 0.35), key=lambda c: c["score"])
    retenues = []
    for c in bonnes:  # des propositions variées : pas deux fois presque la même boucle
        if all(recouvrement_entre(c["coords"], r["coords"]) < 0.6 for r in retenues):
            retenues.append(c)
        if len(retenues) == n:
            break
    zone = {"centre": list(depart), "rayon": round(max([c["rayon"] for c in cands] or [rayon0]) * 2)}
    out = {"propositions": retenues, "zone": zone, "cible": distance, "sport": sport, "depart": list(depart),
           "message": ""}
    if not retenues:
        if not cands:
            out["message"] = (erreurs[0] if erreurs else "Aucune boucle trouvée") + " : choisis un autre départ"
        else:
            proche = min(cands, key=lambda c: c["ecart"])
            out["message"] = (f"Aucune boucle satisfaisante ici pour {distance / 1000:.0f} km : le réseau ne "
                              f"permet que des allers-retours ou des boucles de {proche['distance'] / 1000:.1f} km. "
                              "Essaie une autre distance ou un autre départ.")
    elif retenues[0]["ecart"] > 0.05:
        out["message"] = (f"La boucle la plus proche fait {retenues[0]['distance'] / 1000:.1f} km pour "
                          f"{distance / 1000:.1f} km demandés : c'est ce que le réseau autour de ton départ permet "
                          "de mieux en boucle. Régénère pour d'autres essais.")
    return out


def trajets(depart, arrivee, sport, routeur=None, n=3):
    """De depart à arrivee (lat, lon) : la route du moteur et ses variantes (alternativeidx de BRouter), sans
    doublon. Même forme de résultat que generer, plus "arrivee" ; pas de "cible" : aucune distance n'est visée."""
    if sport not in SPORTS:
        raise ValueError("sport inconnu")
    s = SPORTS[sport]
    vol = haversine(depart, arrivee)
    if vol < 200:
        raise ValueError("Départ et arrivée trop proches : pour revenir au départ, crée une boucle")
    if vol > s["maxi"] * 1000:
        raise ValueError(f"Arrivée trop loin : {s['maxi']} km au plus pour le {s['nom']}")
    routeur = routeur or BRouter()

    def une(k):
        try:
            return routeur.itineraire([depart, arrivee], sport, alternative=k)
        except ErreurItineraire as e:
            return str(e)
    with ThreadPoolExecutor(2) as ex:
        bruts = list(ex.map(une, range(n)))
    retenues = []
    for b in bruts:  # une variante qui reprend presque toute une autre n'apporte rien
        if isinstance(b, dict) and all(recouvrement_entre(b["coords"], r["coords"]) < 0.8 for r in retenues):
            res = resume_voies(b["troncons"])
            b.update(resume_voies=res, qualite=qualite(res, sport), recouvrement=0.0, ecart=0.0)
            retenues.append(b)
    erreurs = [b for b in bruts if isinstance(b, str)]
    message = "" if retenues else (erreurs[0] if erreurs else "Aucun itinéraire trouvé") + " : choisis d'autres points"
    return {"propositions": retenues, "zone": None, "sport": sport, "depart": list(depart), "arrivee": list(arrivee),
            "message": message}


def recouvrement_entre(a, b):
    """Part de la boucle a qui emprunte aussi la boucle b."""
    seg_b = {(min(p, q), max(p, q)) for p, q in zip(b, b[1:])}
    total = commun = 0.0
    for p, q in zip(a, a[1:]):
        l = haversine(p, q)
        total += l
        if (min(p, q), max(p, q)) in seg_b:
            commun += l
    return commun / total if total else 0.0


def alleger(prop):
    """Ce qu'on garde d'une proposition pour l'enregistrer ou l'envoyer (sans les tronçons bruts)."""
    return {k: prop[k] for k in ("coords", "ele", "distance", "montee", "resume_voies", "qualite", "recouvrement",
                                 "ecart", "hints") if k in prop}


# --- recherche d'un lieu, si le GPS n'est pas disponible ---
def chercher_lieu(texte, timeout=15):
    """Ville ou adresse -> [(nom, lat, lon)] via Nominatim (OpenStreetMap). Une requête par recherche."""
    q = urllib.parse.urlencode({"q": texte, "format": "jsonv2", "limit": 5})
    req = urllib.request.Request(f"https://nominatim.openstreetmap.org/search?{q}", headers={"User-Agent": AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=contexte_ssl()) as r:
            return [(x["display_name"], float(x["lat"]), float(x["lon"])) for x in json.loads(r.read())]
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise ErreurItineraire("Recherche de lieu impossible (pas de connexion ?)") from e


def lieu_de(lat, lon, timeout=8):
    """La commune d'une position (Nominatim, OpenStreetMap), pour nommer une sortie. None si inconnue."""
    q = urllib.parse.urlencode({"lat": f"{lat:.5f}", "lon": f"{lon:.5f}", "format": "jsonv2", "zoom": 14,
                                "accept-language": "fr"})
    req = urllib.request.Request(f"https://nominatim.openstreetmap.org/reverse?{q}", headers={"User-Agent": AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=contexte_ssl()) as r:
            adresse = json.loads(r.read()).get("address") or {}
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise ErreurItineraire("Lieu inconnu (pas de connexion ?)") from e
    for cle in ("city", "town", "village", "municipality", "suburb"):
        if adresse.get(cle):
            return adresse[cle]
    return None
