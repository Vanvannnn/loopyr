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
