"""Où en est-on sur la boucle prévue, et quelle est la prochaine consigne. Python pur (app et service GPS).

Chaque position est projetée sur la boucle en ne cherchant qu'un peu autour de la dernière position connue :
une boucle qui se croise, repasse au même endroit ou revient près du départ ne fait jamais sauter la
progression vers la fin. Les règles qui évitent les fausses alertes :
  - la tolérance suit la précision annoncée par le GPS (un trottoir à 10-15 m de la route est sur le parcours) ;
  - une position très imprécise ne décide de rien ;
  - « hors du parcours » n'est annoncé qu'après plusieurs positions de suite, et le retour aussi ;
  - une position retrouvée ailleurs sur la boucle n'est adoptée que si les positions suivantes confirment le sens :
    en avançant (raccourci), on se recale plus loin ; en reculant (boucle prise dans l'autre sens, souvent dès le
    départ), la boucle est inversée et suivie dans ce sens, au lieu d'annoncer « 300 m restants ».
Les consignes (tourner, rond-point…) sont celles du moteur d'itinéraires (BRouter, « voicehints »), calculées
sur le vrai réseau routier : rien n'est déduit de la seule forme du tracé."""
import math

from geo import Plan, cap_entre, projeter

FENETRE = 300  # m de boucle cherchés en avant de la dernière position (plus si le GPS s'est tu un moment)
RECUL = 50  # m cherchés en arrière (GPS qui flotte)
TOLERANCE_MIN, TOLERANCE_MAX = 25, 50  # m : écart au tracé encore considéré « sur le parcours »
PRECISION_IGNOREE = 60  # m : position trop vague pour décider quoi que ce soit
CONFIRMATIONS = 3  # positions de suite pour sortir du parcours, y revenir, ou changer de place sur la boucle
DELAI_HORS = 8  # s : et au moins ce temps hors du tracé
GLISSEMENT = 15  # m : déplacement minimal le long de la boucle pour juger d'un sens de marche

# commandes BRouter (VoiceHint.java) -> consigne (tutoiement, comme le reste de l'app)
CONSIGNES = {1: "Continue tout droit", 2: "Tourne à gauche", 3: "Légèrement à gauche", 4: "Tourne franchement à gauche",
             5: "Tourne à droite", 6: "Légèrement à droite", 7: "Tourne franchement à droite", 8: "Garde la gauche",
             9: "Garde la droite", 10: "Fais demi-tour", 11: "Fais demi-tour", 12: "Fais demi-tour",
             16: "Continue tout droit", 17: "Sors à gauche", 18: "Sors à droite"}
ROND_POINT = (14, 15)
MIROIR = {2: 5, 5: 2, 3: 6, 6: 3, 4: 7, 7: 4, 8: 9, 9: 8, 17: 18, 18: 17, 10: 12, 12: 10}
GAUCHE, DROITE = {2, 3, 4, 8, 10, 17}, {5, 6, 7, 9, 12, 18}
ORDINAUX = {1: "première", 2: "deuxième", 3: "troisième", 4: "quatrième", 5: "cinquième", 6: "sixième"}
CARDINAUX = ("le nord", "le nord-est", "l'est", "le sud-est", "le sud", "le sud-ouest", "l'ouest", "le nord-ouest")


def texte_consigne(cmd, sortie=0):
    if cmd in ROND_POINT:
        if sortie:
            return f"Au rond-point, prends la {ORDINAUX.get(sortie, f'{sortie}e')} sortie"
        return "Au rond-point, suis le tracé"
    return CONSIGNES.get(cmd, "Suis le tracé")


def cote(cmd):
    """'gauche', 'droite', 'rond_point', 'demi_tour' ou 'tout_droit' : pour la flèche du bandeau."""
    if cmd in ROND_POINT:
        return "rond_point"
    if cmd in (10, 11, 12):
        return "demi_tour"
    if cmd in GAUCHE:
        return "gauche"
    if cmd in DROITE:
        return "droite"
    return "tout_droit"


def tolerance(precision):
    return max(TOLERANCE_MIN, min(TOLERANCE_MAX, 15 + (precision if precision else 10)))


def arrondi(m):
    """Distance annoncée : 20 m, 150 m, 1,2 km."""
    if m >= 1000:
        return f"{m / 1000:.1f} km".replace(".", ",")
    return f"{max(10, int(round(m / 10.0)) * 10)} m"


class Progression:
    def __init__(self, coords, consignes=None):
        """coords : la boucle [(lat, lon)] ; consignes : les voicehints de BRouter
        [[indice du point, commande, sortie de rond-point, distance, angle], …] (facultatif)."""
        self.pts = [tuple(p) for p in coords]
        self.consignes_brutes = [list(h) for h in (consignes or ())]
        self.plan = Plan(*self.pts[0])
        self._preparer()
        self.fait = 0.0  # m de boucle parcourus
        self.ecart = 0.0  # m entre toi et la boucle
        self.hors_trace = False
        self.arrive = False
        self.inversee = False  # la boucle est suivie dans l'autre sens que prévu
        self.evenement = None  # dernier changement : "hors", "retour", "inverse", "raccourci", "arrivee"
        self._i, self._f = 0, 0.0
        self._hors = []  # instants des positions hors du tracé, d'affilée
        self._dedans = 0  # positions de suite sur le tracé (pour confirmer un retour)
        self._ailleurs = []  # (t, s) : positions retrouvées sur la boucle loin de la dernière position
        self._dernier_t = None

    def _preparer(self):
        self.xy = [self.plan.xy(*p) for p in self.pts]
        self.cumul = [0.0]
        for a, b in zip(self.xy, self.xy[1:]):
            self.cumul.append(self.cumul[-1] + math.dist(a, b))
        self.total = self.cumul[-1]
        n = len(self.pts)
        self.consignes = []  # (position sur la boucle en m, commande, sortie)
        for h in self.consignes_brutes:
            i, cmd = int(h[0]), int(h[1])
            if 0 < i < n and (cmd in CONSIGNES or cmd in ROND_POINT):
                self.consignes.append((self.cumul[min(i, n - 1)], cmd, int(h[2]) if len(h) > 2 else 0))
        self.consignes.sort()

    @property
    def restant(self):
        return max(0.0, self.total - self.fait)

    @property
    def pourcent(self):
        return 100 * self.fait / self.total if self.total else 0.0

    # --- recherche sur la boucle ---
    def _position(self, i, f):
        return self.cumul[i] + f * (self.cumul[i + 1] - self.cumul[i])

    def _chercher(self, p, debut, fin):
        """(distance, segment, fraction, position) le plus proche entre les segments debut et fin. À distance
        presque égale (rue faite à l'aller et au retour), on préfère la suite de la boucle à ce qui est fait."""
        best, score_min = None, None
        for i in range(max(0, debut), min(fin, len(self.xy) - 1)):
            d, f = projeter(p, self.xy[i], self.xy[i + 1])
            s = self._position(i, f)
            score = d + (0 if s >= self.fait - 10 else 20)
            if best is None or score < score_min:
                best, score_min = (d, i, f, s), score
        return best

    def _segment_de(self, s):
        i = 0
        while i < len(self.cumul) - 2 and self.cumul[i + 1] < s:
            i += 1
        return i

    # --- une nouvelle position ---
    def maj(self, lat, lon, t, precision=None):
        self.evenement = None
        if precision and precision > PRECISION_IGNOREE or len(self.xy) < 2:
            return self
        p = self.plan.xy(lat, lon)
        tol = tolerance(precision)
        silence = 0 if self._dernier_t is None else max(0.0, t - self._dernier_t)
        self._dernier_t = t
        avant = FENETRE + min(1500.0, 12 * silence)  # GPS muet un moment : on a pu avancer davantage
        i0 = self._segment_de(self.fait - RECUL)
        i1 = self._segment_de(self.fait + avant) + 1
        d, i, f, s = self._chercher(p, i0, i1)
        if d <= tol:
            self._sur_le_trace(i, f, s, d)
        else:
            self._loin(p, t, tol, d)
        if not self.arrive and self.fait >= self.total - max(30.0, tol) and self.total > 0:
            self.arrive, self.evenement = True, "arrivee"
        return self

    def _sur_le_trace(self, i, f, s, d):
        self.ecart, self._ailleurs = d, []
        if s >= self.fait:
            self.fait, self._i, self._f = s, i, f
        self._hors = []
        self._dedans += 1
        if self.hors_trace and self._dedans >= 2:
            self.hors_trace, self.evenement = False, "retour"

    def _loin(self, p, t, tol, d_local):
        self._dedans = 0
        ailleurs = self._chercher(p, 0, len(self.xy) - 1)
        if ailleurs and ailleurs[0] <= tol:  # sur la boucle, mais pas là où on t'attendait
            self.ecart = ailleurs[0]
            self._ailleurs = [x for x in self._ailleurs if t - x[0] <= 60] + [(t, ailleurs[3])]
            self._hors = []
            self._decider_ailleurs()
            return
        self.ecart = d_local
        self._ailleurs = []
        self._hors.append(t)
        if not self.hors_trace and len(self._hors) >= CONFIRMATIONS and t - self._hors[0] >= DELAI_HORS:
            self.hors_trace, self.evenement = True, "hors"

    def _decider_ailleurs(self):
        """Plusieurs positions retrouvées ailleurs sur la boucle : on regarde dans quel sens elles avancent."""
        if len(self._ailleurs) < CONFIRMATIONS:
            return
        s = [x[1] for x in self._ailleurs]  # les dernières 60 s
        pas = list(zip(s, s[1:]))
        # le sens est net si l'écart total le dit et que presque tous les pas vont dans ce sens (GPS qui flotte)
        montee = s[-1] - s[0] >= GLISSEMENT and sum(b >= a - 2 for a, b in pas) >= 0.75 * len(pas)
        descente = s[0] - s[-1] >= GLISSEMENT and sum(b <= a + 2 for a, b in pas) >= 0.75 * len(pas)
        if descente:  # tu remontes la boucle : elle est faite dans l'autre sens
            self.inverser(s[-1])
            self.evenement = "inverse"
        elif montee and s[-1] > self.fait:  # raccourci ou départ plus loin : on suit à partir de là
            self.fait = s[-1]
            self._i = self._segment_de(s[-1])
            self._f = 0.0 if self.cumul[self._i + 1] == self.cumul[self._i] else \
                (s[-1] - self.cumul[self._i]) / (self.cumul[self._i + 1] - self.cumul[self._i])
            self._ailleurs, self.hors_trace, self.evenement = [], False, "raccourci"

    def inverser(self, s_actuelle=None):
        """La boucle dans l'autre sens. Les consignes restent celles du moteur, aux mêmes carrefours, côté inversé
        (un « à gauche » à l'aller est un « à droite » au retour) ; le numéro de sortie d'un rond-point ne se
        déduit pas : la consigne dit alors de suivre le tracé."""
        n = len(self.pts)
        self.pts.reverse()
        self.consignes_brutes = [[n - 1 - h[0], MIROIR.get(h[1], h[1]), 0 if h[1] in ROND_POINT else h[2]]
                                 for h in self.consignes_brutes]
        self._preparer()
        self.inversee = not self.inversee
        s = 0.0 if s_actuelle is None else max(0.0, self.total - s_actuelle)
        self.fait, self._ailleurs, self.hors_trace, self._hors = s, [], False, []
        self._i = self._segment_de(s)
        a, b = self.cumul[self._i], self.cumul[self._i + 1]
        self._f = (s - a) / (b - a) if b > a else 0.0

    # --- ce qu'on affiche ---
    def prochaine(self):
        """(texte, distance en m, commande) de la prochaine consigne, ou None s'il n'y en a plus."""
        for s, cmd, sortie in self.consignes:
            if s > self.fait + 5:
                return texte_consigne(cmd, sortie), s - self.fait, cmd
        return None

    def point_a(self, s):
        """(lat, lon) du point situé à s mètres du départ, le long de la boucle."""
        s = max(0.0, min(self.total, s))
        i = self._segment_de(s)
        a, b = self.cumul[i], self.cumul[i + 1]
        f = (s - a) / (b - a) if b > a else 0.0
        pa, pb = self.pts[i], self.pts[i + 1]
        return pa[0] + f * (pb[0] - pa[0]), pa[1] + f * (pb[1] - pa[1])

    def point_prochaine(self):
        """(lat, lon) du carrefour de la prochaine consigne, pour le marquer sur la carte."""
        for s, _, _ in self.consignes:
            if s > self.fait + 5:
                return self.point_a(s)
        return None

    def consigne_depart(self):
        """« Départ : tourne à droite dans 20 m », ou la direction à prendre si le premier virage est loin."""
        if len(self.pts) < 2:
            return ""
        proche = self.prochaine()
        if proche and proche[1] <= 150:
            return f"Départ : {proche[0][0].lower()}{proche[0][1:]} dans {arrondi(proche[1])}"
        j = 1
        while j < len(self.pts) - 1 and self.cumul[j] < 25:
            j += 1
        cap = cap_entre(self.pts[0], self.pts[j])
        loin = f" sur {arrondi(proche[1])}" if proche else ""
        return f"Départ : pars vers {CARDINAUX[int((cap + 22.5) // 45) % 8]} et suis le tracé{loin}"

    def partie_faite(self):
        """Coordonnées de la boucle déjà parcourue (pour la griser sur la carte)."""
        a, b = self.pts[self._i], self.pts[min(self._i + 1, len(self.pts) - 1)]
        f = self._f
        return self.pts[:self._i + 1] + [(a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)]
