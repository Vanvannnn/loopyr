"""Le symbole de Loopy, « la rose des boucles » : trois boucles de longueurs différentes partent du même
point de départ et y reviennent. Mêmes valeurs que logo/kit/construire.py (ROSE ; unités du kit, y vers le bas)."""
import math

from kivy.animation import Animation
from kivy.graphics import Color, Ellipse, Line
from kivy.properties import NumericProperty
from kivy.uix.widget import Widget

# (angle de la boucle en degrés, distance départ → centre du bout, rayon du bout)
BOUCLES = ((-105, 84, 42), (15, 64, 32), (150, 48, 24))
TRAIT, ECART, POINT = 15, 21, 10.5  # graisse, vide autour du départ, rayon du point
COEUR = 0.6  # le cœur pêche du point, cerclé de la couleur de la marque


def goutte(ang, d, r, n=48):
    """Une boucle échantillonnée : du départ au bout, tour du cercle, retour au départ."""
    a = math.radians(ang)
    cx, cy = d * math.cos(a), d * math.sin(a)
    beta = math.acos(r / d)
    a0 = a + math.pi + beta
    a1 = a + math.pi - beta + 2 * math.pi
    out = [(0.0, 0.0)]
    for i in range(n + 1):
        t = a0 + (a1 - a0) * i / n
        out.append((cx + r * math.cos(t), cy + r * math.sin(t)))
    out.append((0.0, 0.0))
    dense = []  # les deux droites aussi, pour que le tracé progressif avance à vitesse régulière
    for p, q in zip(out, out[1:]):
        pas = max(1, int(math.dist(p, q) / 3))
        dense += [(p[0] + (q[0] - p[0]) * k / pas, p[1] + (q[1] - p[1]) * k / pas) for k in range(pas)]
    dense.append(out[-1])
    return [p for p in dense if math.hypot(*p) > ECART]  # ouverte autour du départ


def boucles():
    return [goutte(*b) for b in BOUCLES]


def _cadre():
    pts = [p for b in boucles() for p in b]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs) - TRAIT / 2, min(ys) - TRAIT / 2, max(xs) + TRAIT / 2, max(ys) + TRAIT / 2


CADRE = _cadre()


class Symbole(Widget):
    """Le symbole, aux couleurs du thème. dessin : part des boucles tracées (0 à 1) ; point : taille du départ."""
    dessin = NumericProperty(1)
    point = NumericProperty(1)

    def __init__(self, marque, coeur, anneau=None, **kw):
        super().__init__(**kw)
        self.couleurs, self.boucles = (marque, coeur, anneau or marque), boucles()
        self.bind(pos=self.dessiner, size=self.dessiner, dessin=self.dessiner, point=self.dessiner)

    def animer(self):
        """Le point de départ se pose, puis les trois boucles partent de lui en même temps."""
        self.dessin, self.point = 0, 0
        Animation(point=1, d=0.35, t="out_back").start(self)
        (Animation(d=0.15) + Animation(dessin=1, d=0.9, t="in_out_cubic")).start(self)

    def dessiner(self, *_):
        x0, y0, x1, y1 = CADRE
        k = min(self.width / (x1 - x0), self.height / (y1 - y0))
        ox = self.center_x - (x0 + x1) / 2 * k
        oy = self.center_y + (y0 + y1) / 2 * k

        def xy(p):
            return ox + p[0] * k, oy - p[1] * k
        marque, coeur, anneau = self.couleurs
        self.canvas.clear()
        with self.canvas:
            if self.dessin > 0.01:
                Color(*marque)
                for b in self.boucles:
                    n = max(2, int(len(b) * self.dessin))
                    Line(points=[v for p in b[:n] for v in xy(p)], width=TRAIT * k / 2, cap="round",
                         joint="round")
            x, y = xy((0, 0))
            for r, c in ((POINT, anneau), (POINT * COEUR, coeur)):
                r *= k * self.point
                Color(*c)
                Ellipse(pos=(x - r, y - r), size=(2 * r, 2 * r))
