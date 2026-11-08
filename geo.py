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
    """Altitude d'une position d'après le point le plus proche de la boucle prévue (à moins de 80 m)."""

    def __init__(self, coords, ele, case=0.001):
        self.case, self.grille = case, {}
        for (lat, lon), e in zip(coords, ele or ()):
            if e is not None:
                self.grille.setdefault((int(lat // case), int(lon // case)), []).append((lat, lon, e))

    def __call__(self, lat, lon):
        i, j = int(lat // self.case), int(lon // self.case)
        proches = [p for di in (-1, 0, 1) for dj in (-1, 0, 1) for p in self.grille.get((i + di, j + dj), ())]
        if not proches:
            return None
        d, e = min((haversine((lat, lon), p[:2]), p[2]) for p in proches)
        return e if d <= 80 else None
