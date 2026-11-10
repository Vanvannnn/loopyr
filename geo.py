"""Calculs géographiques. Python pur, aucune dépendance."""
import math


def haversine(a, b):
    """Distance en mètres entre deux points (lat, lon)."""
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dl = math.radians(b[1] - a[1])
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 12742000 * math.asin(math.sqrt(h))


def cap_entre(a, b):
    """Direction (degrés, 0 = nord, sens horaire) en allant du point a vers le point b."""
    p1, p2, dl = math.radians(a[0]), math.radians(b[0]), math.radians(b[1] - a[1])
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return math.degrees(math.atan2(y, x)) % 360


def ecart(a, b):
    """Plus court écart signé (degrés) pour aller de a vers b."""
    return (b - a + 180) % 360 - 180


class Plan:
    """Projection locale (mètres) autour d'un point : précise à quelques km de distance."""

    def __init__(self, lat0, lon0):
        self.lat0, self.lon0 = lat0, lon0
        self.k = math.cos(math.radians(lat0)) * 111320

    def xy(self, lat, lon):
        return (lon - self.lon0) * self.k, (lat - self.lat0) * 111320

    def latlon(self, x, y):
        return self.lat0 + y / 111320, self.lon0 + x / self.k


class Cap:
    """Direction de marche (degrés), lissée, à partir des positions successives."""

    def __init__(self):
        self.valeur, self.dernier = None, None

    def maj(self, p):
        if self.dernier is None:
            self.dernier = p
        elif haversine(self.dernier, p) >= 4:
            nouveau = cap_entre(self.dernier, p)
            self.valeur = nouveau if self.valeur is None else (self.valeur + 0.6 * ecart(self.valeur, nouveau)) % 360
            self.dernier = p
        return self.valeur


def rogner(coords, m=300):
    """Retire les m premiers et derniers mètres d'un tracé : le départ (souvent le domicile) n'est pas montré
    aux autres. Un tracé trop court pour être rogné n'est pas montré du tout."""
    if len(coords) < 2:
        return []
    cumul = [0.0]
    for a, b in zip(coords, coords[1:]):
        cumul.append(cumul[-1] + haversine(a, b))
    if cumul[-1] <= 2 * m + 100:
        return []
    return [p for p, d in zip(coords, cumul) if m <= d <= cumul[-1] - m]


def reduire(coords, n=400):
    """Au plus n points (affichage d'aperçus), en gardant le premier et le dernier."""
    if len(coords) <= n:
        return list(coords)
    pas = (len(coords) - 1) / (n - 1)
    return [coords[round(i * pas)] for i in range(n)]


class Altitudes:
    """Altitude d'une position d'après la boucle prévue (modèle de terrain du moteur, à moins de 60 m du tracé).
    Interpolée le long du tronçon le plus proche : les sommets du tracé sont espacés de dizaines à centaines de
    mètres ; prendre le sommet le plus proche faisait avancer l'altitude par marches, en retard sur la montée."""

    def __init__(self, coords, ele, case=0.001):
        self.case, self.grille = case, {}
        self.pts = [tuple(p) for p in coords]
        self.ele = list(ele or ())
        self.plan = Plan(*self.pts[0]) if self.pts else None
        self.xy = [self.plan.xy(*p) for p in self.pts] if self.plan else []
        # chaque tronçon est inscrit dans toutes les cases qu'il traverse : un long tronçon droit (route de
        # campagne, un seul segment sur 800 m) est retrouvé en son milieu
        for i in range(len(self.pts) - 1):
            if i + 1 >= len(self.ele) or self.ele[i] is None or self.ele[i + 1] is None:
                continue
            (la0, lo0), (la1, lo1) = self.pts[i], self.pts[i + 1]
            n = 1 + int(max(abs(la1 - la0), abs(lo1 - lo0)) / (case / 2))
            for k in range(n + 1):
                la, lo = la0 + (la1 - la0) * k / n, lo0 + (lo1 - lo0) * k / n
                self.grille.setdefault((int(la // case), int(lo // case)), set()).add(i)

    def __call__(self, lat, lon):
        i0, j0 = int(lat // self.case), int(lon // self.case)
        segs = {i for di in (-1, 0, 1) for dj in (-1, 0, 1) for i in self.grille.get((i0 + di, j0 + dj), ())}
        if not segs:
            return None
        p = self.plan.xy(lat, lon)
        meilleur = None
        for i in segs:
            d, f = projeter(p, self.xy[i], self.xy[i + 1])
            if meilleur is None or d < meilleur[0]:
                meilleur = (d, self.ele[i] + f * (self.ele[i + 1] - self.ele[i]))
        return meilleur[1] if meilleur[0] <= 60 else None


def projeter(p, a, b):
    """Distance de p au segment [a, b] (plan local, mètres) et fraction (0..1) du point le plus proche."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    l2 = dx * dx + dy * dy
    f = 0.0 if l2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2))
    return math.hypot(p[0] - a[0] - f * dx, p[1] - a[1] - f * dy), f


def altitude_pression(hpa):
    """Altitude barométrique (m) dans l'atmosphère standard. Seules ses variations comptent : la météo décale
    le niveau, pas les écarts sur une sortie de quelques heures."""
    return 44330.0 * (1 - (hpa / 1013.25) ** 0.190295)


class Altimetre:
    """Choisit l'altitude qui sert au dénivelé, du plus fiable au moins fiable, et s'y tient pendant la sortie :
    - « baro » : le baromètre du téléphone (variations précises au mètre), calé sur le terrain au premier point ;
    - « terrain » : le modèle de terrain le long de la boucle prévue (tant qu'on est dessus) ;
    - « gps » : l'altitude GPS, très bruitée, seulement si sa précision verticale est correcte, et lissée.
    Renvoie None quand aucune altitude fiable n'est disponible : le dénivelé n'avance pas plutôt que de mentir."""
    LISSAGE_GPS = 0.1  # ~10 s de constante de temps à 1 position/s : le bruit s'efface, une montée passe

    def __init__(self, terrain=None):
        self.terrain, self.source, self.decalage, self.gps_lisse = terrain, None, None, None

    def __call__(self, lat, lon, gps=None, vprec=None, pression=None):
        t = self.terrain(lat, lon) if self.terrain else None
        if pression:
            h = altitude_pression(pression)
            if self.decalage is None:
                ref = t if t is not None else (gps if gps is not None else h)
                self.decalage = ref - h
            self.source = "baro"
            return h + self.decalage
        if self.source == "baro":  # baromètre muet un instant : on attend sa prochaine valeur
            return None
        if t is not None and self.source in (None, "terrain"):
            self.source = "terrain"
            return t
        if gps is not None and (vprec is None or vprec <= 12) and self.source in (None, "gps"):
            self.source = "gps"
            g = self.gps_lisse
            self.gps_lisse = gps if g is None else g + self.LISSAGE_GPS * (gps - g)
            return self.gps_lisse
        return None
