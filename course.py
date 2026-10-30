"""Suivi d'une course : points GPS, pauses, splits, vitesse, D+. Python pur, aucune dépendance.
Les heures (t) sont des secondes epoch ; celles des points sont l'heure du fix GPS."""
import time

from geo import haversine

PRECISION_MAX = 25  # m : position trop imprécise au-delà
VITESSE_MAX = 12  # m/s : au-delà, c'est un saut du GPS, pas toi
BRUIT = 2  # m : déplacement ignoré (bruit du GPS à l'arrêt)
SEUIL_DPLUS = 3  # m : une montée n'est comptée qu'au-delà (altitudes approximatives)
SAUTS_MAX = 3  # sauts d'affilée : c'est alors le point de référence qui était faux


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
    def __init__(self, debut=None, horloge=time.time):
        self.horloge = horloge
        self.debut = horloge() if debut is None else debut
        self.fin = None
        self.pauses = []  # [début, fin ou None]
        self.segments = [[]]  # un segment par période sans pause : [(t, lat, lon, ele), ...]
        self.dist = self.dplus = 0.0
        self.splits = []  # temps en mouvement (s) de chaque km
        self.recent = []  # (t, distance) des 15 dernières secondes, pour la vitesse
        self._ele_ref, self._sauts = None, 0

    def _t(self, t):
        return self.horloge() if t is None else t

    @property
    def en_pause(self):
        return bool(self.pauses) and self.pauses[-1][1] is None

    @property
    def trace(self):
        """Tous les points (lat, lon), pour l'affichage."""
        return [(la, lo) for seg in self.segments for _, la, lo, _ in seg]

    def pause(self, t=None):
        if self.fin is None and not self.en_pause:
            self.pauses.append([self._t(t), None])
            self.recent = []

    def reprendre(self, t=None):
        if self.en_pause:
            self.pauses[-1][1] = self._t(t)
            if self.segments[-1]:
                self.segments.append([])  # pas de trait droit entre la pause et la reprise

    def terminer(self, t=None):
        if self.fin is None:
            t = self._t(t)
            if self.en_pause:
                self.pauses[-1][1] = t
            self.fin = t

    def duree(self, t=None):
        """Temps en mouvement (pauses exclues), en secondes, jusqu'à t (ou maintenant)."""
        fin = self.fin if self.fin is not None else self._t(t)
        arret = sum(max(0, min(f if f is not None else fin, fin) - d) for d, f in self.pauses)
        return max(0.0, fin - self.debut - arret)

    def duree_totale(self, t=None):
        return (self.fin if self.fin is not None else self._t(t)) - self.debut

    def ajouter(self, t, lat, lon, ele=None, precision=None):
        """Ajoute un fix GPS. Renvoie True s'il est gardé."""
        if self.fin is not None or self.en_pause or t < self.debut:
            return False
        if precision and precision > PRECISION_MAX:
            return False
        seg = self.segments[-1]
        if seg:
            t0, la0, lo0, _ = seg[-1]
            d = haversine((la0, lo0), (lat, lon))
            if d < BRUIT or t <= t0:
                return False
            if d / (t - t0) > VITESSE_MAX:
                self._sauts += 1
                if self._sauts <= SAUTS_MAX:
                    return False
                seg.append((t, lat, lon, ele))  # on repart de ce point, sans compter la distance
                self._sauts, self._ele_ref = 0, None
                return True
            self._compter(t0, d, t)
        self._sauts = 0
        seg.append((t, lat, lon, ele))
        self._denivele(ele)
        self.recent = [x for x in self.recent if t - x[0] <= 15] + [(t, self.dist)]
        return True

    def _compter(self, t0, d, t):
        avant = self.dist
        self.dist += d
        while self.dist >= 1000 * (len(self.splits) + 1):
            km = 1000 * (len(self.splits) + 1)
            passage = t0 + (t - t0) * (km - avant) / d  # heure du passage au km, interpolée
            self.splits.append(self.duree(passage) - sum(self.splits))

    def _denivele(self, ele):
        if ele is None:
            return
        if self._ele_ref is None or ele < self._ele_ref:
            self._ele_ref = ele
        elif ele - self._ele_ref >= SEUIL_DPLUS:
            self.dplus += ele - self._ele_ref
            self._ele_ref = ele

    def vitesse(self, t=None):
        """Vitesse en m/s, lissée sur les 15 dernières secondes."""
        if self.en_pause:
            return 0.0
        now = self._t(t)
        r = [x for x in self.recent if now - x[0] <= 15]
        if len(r) < 2 or r[-1][0] <= r[0][0]:
            return 0.0
        return (r[-1][1] - r[0][1]) / (r[-1][0] - r[0][0])

    def resume(self):
        """L'activité complète, prête à être enregistrée puis exportée en GPX."""
        return {"id": time.strftime("%Y%m%d-%H%M%S", time.localtime(self.debut)),
                "date": time.strftime("%Y-%m-%d %H:%M", time.localtime(self.debut)),
                "debut": self.debut, "distance": round(self.dist), "duree": round(self.duree()),
                "duree_totale": round(self.duree_totale()), "denivele": round(self.dplus),
                "splits": [round(s, 1) for s in self.splits],
                "segments": [[[round(t, 1), round(la, 6), round(lo, 6), None if e is None else round(e, 1)]
                              for t, la, lo, e in seg] for seg in self.segments if seg],
                "strava_id": None}
