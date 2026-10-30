"""Suivi d'une course et profil. Python pur, aucune dépendance."""
import json, math, time


def haversine(a, b):
    """Distance en mètres entre deux points (lat, lon)."""
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dl = math.radians(b[1] - a[1])
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 12742000 * math.asin(math.sqrt(h))


def fmt_temps(s):
    s = int(s)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def fmt_allure(v):
    """Vitesse en m/s -> allure 'm:ss' par km."""
    if v < 0.5:
        return "--:--"
    sec = 1000 / v
    return f"{int(sec // 60)}:{int(sec % 60):02d}"


class Course:
    def __init__(self):
        self.debut, self.fin = time.time(), None
        self.dist, self.trace, self.recent = 0.0, [], []

    def ajouter(self, lat, lon, precision=None):
        if precision and precision > 25:  # position trop imprécise
            return
        p = (lat, lon)
        if self.trace:
            d = haversine(self.trace[-1], p)
            if d < 2:  # bruit du GPS à l'arrêt
                return
            self.dist += d
        self.trace.append(p)
        self.recent.append((time.time(), self.dist))
        self.recent = self.recent[-30:]

    def terminer(self):
        self.fin = time.time()

    def duree(self):
        return (self.fin or time.time()) - self.debut

    def vitesse(self):
        """Vitesse en m/s, lissée sur les 15 dernières secondes."""
        now = time.time()
        r = [x for x in self.recent if now - x[0] <= 15]
        if len(r) < 2 or r[-1][0] <= r[0][0]:
            return 0.0
        return (r[-1][1] - r[0][1]) / (r[-1][0] - r[0][0])

    def resume(self):
        pas = max(1, len(self.trace) // 300)
        return {"date": time.strftime("%Y-%m-%d %H:%M", time.localtime(self.debut)),
                "distance": round(self.dist), "duree": round(self.duree()),
                "trace": [[round(a, 5), round(b, 5)] for a, b in self.trace[::pas]]}


def charger(chemin):
    try:
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def enregistrer(chemin, course):
    courses = charger(chemin)
    courses.insert(0, course)
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(courses, f)
