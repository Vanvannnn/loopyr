"""La carte hors-ligne (widget Trace) et ses boutons de zoom."""
import math

from kivy.animation import Animation
from kivy.graphics import (Color, Ellipse, InstructionGroup, Line, Mesh, PopMatrix,
                           PushMatrix, Rotate, Scale, Translate, Triangle)
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ListProperty, NumericProperty
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.stencilview import StencilView

from geo import ecart
from ui.widgets import CHEMIN, ENCRE, FOND, ROUTE, SIGNAL, SUR_SIGNAL, TRACE, TRACE_PALE, Bouton


def avec_zoom(trace, on_mode=None):
    """La carte + gros boutons + / − (et le bouton d'orientation) par-dessus."""
    f = FloatLayout()
    trace.pos_hint = {"x": 0, "y": 0}  # sans pos_hint, FloatLayout laisse la carte collée en bas de l'écran
    f.add_widget(trace)
    for txt, fac, place in (("+", 1.4, {"y": 0.51}), ("−", 1 / 1.4, {"top": 0.49})):
        f.add_widget(Bouton(txt, lambda *_, fac=fac: trace.zoomer(fac), "carte", 56, 28,
                            size_hint=(None, None), width=dp(56), pos_hint={"right": 0.97, **place}))
    if on_mode:
        f.add_widget(Bouton("Sens de course", on_mode, "carte", 48, 15, size_hint=(None, None),
                            width=dp(150), pos_hint={"x": 0.03, "top": 0.97}))
    return f


class Trace(StencilView):
    """Fond hors-ligne (rues et chemins de data.db), boucle, trajet, départ et toi.
    suivi=False : vue d'ensemble. suivi=True : centré sur toi.
    Zoom : pincer, molette ou boutons. Le fond est dessiné une fois puis déplacé par le GPU."""
    coords = ListProperty([])
    moi = ListProperty([])
    fait = ListProperty([])
    boucle_faite = ListProperty([])  # partie de la boucle déjà parcourue (grisée)
    depart = ListProperty([])
    zone = ListProperty([])
    suivi = BooleanProperty(False)
    angle = NumericProperty(0)  # rotation actuelle de la carte (animée)
    revele = NumericProperty(1)  # part de la boucle déjà tracée (animée quand une boucle arrive)
    orient = "marche"  # marche (direction de marche en haut), boussole, nord
    cap = None  # direction de marche, en degrés
    az = None  # direction du téléphone (boussole)
    rayon = 250  # mètres visibles autour de toi au zoom 1
    choix = None  # fonction appelée quand on touche la carte

    def __init__(self, **kw):
        super().__init__(**kw)
        self.reseau, self.lat0, self.lon0, self.k = {}, None, 0, 1.0
        self.zoom, self.pan, self.s, self.cx, self.cy = 1.0, [0.0, 0.0], 1.0, 0, 0
        self.touches, self.multi = {}, False
        self.tr, self.sc = Translate(0, 0), Scale(1, 1, 1)
        self.rot = Rotate(angle=0, axis=(0, 0, 1), origin=(0, 0))
        self.g_res, self.g_dyn = InstructionGroup(), InstructionGroup()
        for i in (PushMatrix(), self.rot, self.tr, self.sc, self.g_res, self.g_dyn, PopMatrix()):
            self.canvas.add(i)
        self.bind(pos=self.dessiner, size=self.dessiner, zone=self.init_zone, coords=self.reset,
                  suivi=self.reset, moi=self.dessiner, depart=self.dessiner, revele=self.dessiner)

    def mondial(self, lat, lon):  # degrés -> mètres autour du centre de la zone
        return (lon - self.lon0) * self.k * 111000, (lat - self.lat0) * 111000

    def geo(self, x, y):
        return self.lat0 + y / 111000, self.lon0 + x / (self.k * 111000)

    def init_zone(self, *_):
        (la0, lo0), (la1, lo1) = self.zone
        self.lat0, self.lon0 = (la0 + la1) / 2, (lo0 + lo1) / 2
        self.k = math.cos(math.radians(self.lat0))
        self.g_res.clear()
        for t, couleur in ((0, ROUTE), (1, CHEMIN)):  # rues, chemins
            self.g_res.add(Color(*couleur))
            verts, idx = [], []
            for pts in self.reseau.get(t, ()):
                n = len(verts) // 4
                for p in pts:
                    verts += [*self.mondial(*p), 0, 0]
                idx += [i for j in range(n, n + len(pts) - 1) for i in (j, j + 1)]
                if len(verts) > 240000:  # un Mesh accepte au plus 65535 sommets
                    self.g_res.add(Mesh(vertices=verts, indices=idx, mode="lines"))
                    verts, idx = [], []
            if idx:
                self.g_res.add(Mesh(vertices=verts, indices=idx, mode="lines"))
        self.dessiner()

    def reset(self, *_):
        self.zoom, self.pan = 1.0, [0.0, 0.0]
        self.dessiner()

    def tracer(self, coords, d=1.1):
        """Affiche une nouvelle boucle en la traçant depuis le départ, comme un GPS qui l'enregistre."""
        Animation.cancel_all(self, "revele")
        self.revele = 0
        self.coords = coords
        Animation(revele=1, d=d, t="in_out_cubic").start(self)

    def zoomer(self, facteur):
        self.zoom = min(12, max(0.4, self.zoom * facteur))
        self.dessiner()

    def vue(self):
        if self.suivi and len(self.moi) == 2:
            self.cx, self.cy = self.mondial(*self.moi)
            base = min(self.width, self.height) / (2 * self.rayon)
        else:
            ref = self.coords if len(self.coords) >= 2 else self.zone
            pts = [self.mondial(*p) for p in ref]
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            base = min((self.width - 40) / max(max(xs) - min(xs), 1),
                       (self.height - 40) / max(max(ys) - min(ys), 1))
            self.cx = (min(xs) + max(xs)) / 2 + self.pan[0]
            self.cy = (min(ys) + max(ys)) / 2 + self.pan[1]
        self.s = base * self.zoom
        px, py = self.center_x, self.center_y
        self.sc.xyz = (self.s, self.s, 1)
        self.tr.xy = (px - self.cx * self.s, py - self.cy * self.s)
        self.rot.origin = (px, py)
        self.maj_angle()

    def cible(self):
        if not (self.suivi and len(self.moi) == 2) or self.orient == "nord":
            return 0
        a = self.az if (self.orient == "boussole" and self.az is not None) else self.cap
        return a or 0

    def maj_angle(self):
        d = ecart(self.angle, self.cible())
        if abs(d) > 0.5:
            Animation.cancel_all(self, "angle")
            Animation(angle=self.angle + d, duration=0.3).start(self)

    def on_angle(self, *_):
        self.rot.angle = self.angle

    def dessiner(self, *_):
        if self.lat0 is None or self.width < 2 or self.height < 2:
            return
        self.vue()
        self.g_dyn.clear()
        u = 1 / self.s  # un pixel, en mètres

        def ligne(pts, couleur, px):
            self.g_dyn.add(Color(*couleur))
            self.g_dyn.add(Line(points=[v for p in pts for v in self.mondial(*p)], width=px * u))

        def disque(p, rayons):
            x, y = self.mondial(*p)
            for r, c in rayons:
                self.g_dyn.add(Color(*c))
                self.g_dyn.add(Ellipse(pos=(x - r * u, y - r * u), size=(2 * r * u, 2 * r * u)))

        if len(self.coords) >= 2:
            n = max(2, int(len(self.coords) * self.revele))
            ligne(self.coords[:n], TRACE, 5)
        if len(self.boucle_faite) >= 2:
            ligne(self.boucle_faite, TRACE_PALE, 5)
        if len(self.fait) >= 2:
            ligne(self.fait, ENCRE, 3)
        if len(self.coords) >= 2:  # départ et arrivée : le point du logo
            disque(self.coords[0], ((14, FOND), (11, SUR_SIGNAL), (8, SIGNAL)))
        if len(self.depart) == 2 and not self.suivi:
            disque(self.depart, ((14, FOND), (11, ENCRE), (5, FOND)))  # départ choisi, pas encore de boucle
        if len(self.moi) == 2:
            x, y = self.mondial(*self.moi)
            if self.cap is None:  # pas encore de direction : un point
                disque(self.moi, ((12, FOND), (10, TRACE), (5, FOND)))
            else:  # flèche orientée vers la direction de marche
                sb, cb = math.sin(math.radians(self.cap)), math.cos(math.radians(self.cap))
                self.g_dyn.add(Color(*TRACE[:3], 0.18))
                self.g_dyn.add(Ellipse(pos=(x - 30 * u, y - 30 * u), size=(60 * u, 60 * u)))

                def pt(a, b, k):
                    return x + (a * cb + b * sb) * k * u, y + (-a * sb + b * cb) * k * u

                for k, c in ((19, SUR_SIGNAL), (14, SIGNAL)):  # contour sombre, flèche signal
                    self.g_dyn.add(Color(*c))
                    self.g_dyn.add(Triangle(points=[*pt(0, 1.5, k), *pt(-1, -1, k), *pt(0, -0.45, k)]))
                    self.g_dyn.add(Triangle(points=[*pt(0, 1.5, k), *pt(0, -0.45, k), *pt(1, -1, k)]))

    # --- gestes : pincer pour zoomer, glisser pour déplacer, toucher pour choisir ---
    def on_touch_down(self, t):
        if not self.collide_point(*t.pos):
            return False
        if "button" in t.profile and t.button.startswith("scroll"):  # molette (PC)
            self.zoomer(1.25 if t.button == "scrollup" else 0.8)
            return True
        t.grab(self)
        self.touches[t.uid] = t.pos
        t.ud["debut"] = t.pos
        return True

    def on_touch_move(self, t):
        if t.grab_current is not self or t.uid not in self.touches:
            return False
        ancien = dict(self.touches)
        self.touches[t.uid] = t.pos
        ids = sorted(self.touches)
        if len(ids) >= 2:
            self.multi = True
            d0 = math.dist(ancien[ids[0]], ancien[ids[1]])
            d1 = math.dist(self.touches[ids[0]], self.touches[ids[1]])
            if d0 > 10:
                self.zoomer(d1 / d0)
        elif not self.suivi:
            self.pan[0] -= (t.pos[0] - ancien[t.uid][0]) / self.s
            self.pan[1] -= (t.pos[1] - ancien[t.uid][1]) / self.s
            self.dessiner()
        return True

    def on_touch_up(self, t):
        if t.grab_current is not self:
            return False
        t.ungrab(self)
        simple = len(self.touches) == 1 and not self.multi
        bouge = math.dist(t.pos, t.ud.get("debut", t.pos)) > dp(12)
        self.touches.pop(t.uid, None)
        if not self.touches:
            self.multi = False
        if simple and not bouge and self.choix and self.lat0 is not None:
            self.choix(*self.geo((t.pos[0] - self.tr.x) / self.s, (t.pos[1] - self.tr.y) / self.s))
        return True
