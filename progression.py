"""Où en est-on sur la boucle prévue. Python pur.
Chaque position est projetée sur la boucle en ne cherchant qu'un peu en avant de la dernière position :
une boucle qui se croise ou repasse au même endroit ne fait pas sauter la progression."""
import math

from geo import Plan

FENETRE = 300  # m de boucle cherchés en avant de la dernière position
RECUL = 50  # m cherchés en arrière (GPS qui flotte)
HORS_TRACE = 40  # m : au-delà, tu n'es plus sur la boucle…
DELAI_HORS = 10  # s : … et on te prévient si ça dure


def _projeter(p, a, b):
    """Distance de p au segment [a, b] et fraction (0..1) du point le plus proche."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    l2 = dx * dx + dy * dy
    f = 0.0 if l2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2))
    return math.hypot(p[0] - a[0] - f * dx, p[1] - a[1] - f * dy), f


class Progression:
    def __init__(self, coords):
        self.pts = [tuple(p) for p in coords]
        self.plan = Plan(*self.pts[0])
        self.xy = [self.plan.xy(*p) for p in self.pts]
        self.cumul = [0.0]
        for a, b in zip(self.xy, self.xy[1:]):
            self.cumul.append(self.cumul[-1] + math.dist(a, b))
        self.total = self.cumul[-1]
        self.fait = 0.0  # m de boucle parcourus
        self.ecart = 0.0  # m entre toi et la boucle
        self.hors_trace = False
        self._i, self._f, self._hors_depuis = 0, 0.0, None

    @property
    def restant(self):
        return max(0.0, self.total - self.fait)

    @property
    def pourcent(self):
        return 100 * self.fait / self.total if self.total else 0.0

    def _chercher(self, p, debut, fin):
        """(distance, segment, fraction) le plus proche. À distance égale (rue faite à l'aller
        et au retour), on préfère la suite de la boucle à ce qui est déjà fait."""
        best, score_min = None, None
        for i in range(debut, fin):
            d, f = _projeter(p, self.xy[i], self.xy[i + 1])
            s = self.cumul[i] + f * (self.cumul[i + 1] - self.cumul[i])
            score = d + (0 if s >= self.fait - 10 else 20)
            if best is None or score < score_min:
                best, score_min = (d, i, f), score
        return best

    def maj(self, lat, lon, t):
        p = self.plan.xy(lat, lon)
        n = len(self.xy) - 1
        i0 = self._i
        while i0 > 0 and self.cumul[i0] > self.fait - RECUL:
            i0 -= 1
        i1 = self._i
        while i1 < n and self.cumul[i1] <= self.fait + FENETRE:
            i1 += 1
        best = self._chercher(p, i0, max(i1, i0 + 1))
        if best[0] > HORS_TRACE:  # perdu localement : raccourci ou détour, on cherche partout
            partout = self._chercher(p, 0, n)
            if partout[0] <= HORS_TRACE:
                best = partout
                self.fait = 0.0  # on se recale, même en arrière
        d, i, f = best
        self.ecart = d
        if d <= HORS_TRACE:
            s = self.cumul[i] + f * (self.cumul[i + 1] - self.cumul[i])
            if s >= self.fait:
                self.fait, self._i, self._f = s, i, f
            self._hors_depuis, self.hors_trace = None, False
        else:
            if self._hors_depuis is None:
                self._hors_depuis = t
            self.hors_trace = t - self._hors_depuis >= DELAI_HORS
        return self

    def partie_faite(self):
        """Coordonnées de la boucle déjà parcourue (pour la griser sur la carte)."""
        a, b = self.pts[self._i], self.pts[min(self._i + 1, len(self.pts) - 1)]
        f = self._f
        return self.pts[:self._i + 1] + [(a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)]
