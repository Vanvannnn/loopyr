"""La carte (widget Trace) : tuiles OpenStreetMap partout dans le monde, boucle, trajet, départ et toi.
Projection Mercator (celle des tuiles), mise à l'échelle pour que 1 unité = 1 mètre près de l'origine.
Les tuiles sont téléchargées en arrière-plan puis gardées sur le disque : une zone déjà vue s'affiche
hors connexion. Zoom : pincer, molette ou boutons. Tout est dessiné une fois puis déplacé par le GPU."""
import math, os, threading, urllib.request, weakref
from concurrent.futures import ThreadPoolExecutor

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.graphics import (Color, Ellipse, InstructionGroup, Line, PopMatrix, PushMatrix, Rectangle, Rotate,
                           Scale, Translate, Triangle)
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ListProperty, NumericProperty
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.stencilview import StencilView

from geo import ecart
from ui import widgets
from ui.widgets import BRUME, ENCRE, FOND, SIGNAL, SUR_SIGNAL, TRACE, TRACE_PALE, Bouton, lab

R_TERRE = 6378137.0
MONDE = 2 * math.pi * R_TERRE
URL_TUILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"  # politique d'usage OSM : voir docs/CONFIGURATION.md
AGENT = "Loopy/0.4 (+https://github.com/Vanvannnn/loopy)"


def mercator(lat, lon):
    lat = max(-85.05, min(85.05, lat))
    return R_TERRE * math.radians(lon), R_TERRE * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def inverse(x, y):
    return math.degrees(2 * math.atan(math.exp(y / R_TERRE)) - math.pi / 2), math.degrees(x / R_TERRE)


class Tuiles:
    """Cache partagé par toutes les cartes : disque, puis mémoire (textures). Un seul téléchargement par tuile."""
    dossier = None
    textures, en_cours, cartes = {}, set(), weakref.WeakSet()
    pool = ThreadPoolExecutor(3)
    verrou = threading.Lock()

    @classmethod
    def demander(cls, z, x, y):
        cle = (z, x, y)
        if cle in cls.textures or cle in cls.en_cours or cls.dossier is None:
            return
        cls.en_cours.add(cle)
        chemin = os.path.join(cls.dossier, str(z), str(x), f"{y}.png")
        if os.path.exists(chemin):
            Clock.schedule_once(lambda dt: cls._charger(cle, chemin))
        else:
            cls.pool.submit(cls._telecharger, cle, chemin)

    @classmethod
    def _telecharger(cls, cle, chemin):
        z, x, y = cle
        try:
            from boucles import contexte_ssl
            req = urllib.request.Request(URL_TUILES.format(z=z, x=x, y=y), headers={"User-Agent": AGENT})
            with urllib.request.urlopen(req, timeout=20, context=contexte_ssl()) as r:
                data = r.read()
            os.makedirs(os.path.dirname(chemin), exist_ok=True)
            with open(chemin + ".tmp", "wb") as f:
                f.write(data)
            os.replace(chemin + ".tmp", chemin)
            Clock.schedule_once(lambda dt: cls._charger(cle, chemin))
        except Exception:  # hors connexion : la tuile sera redemandée au prochain dessin
            Clock.schedule_once(lambda dt: cls.en_cours.discard(cle), 5)

    @classmethod
    def _charger(cls, cle, chemin):
        from kivy.core.image import Image as CoreImage
        try:
            cls.textures[cle] = CoreImage(chemin).texture
        except Exception:
            try:
                os.remove(chemin)  # fichier abîmé : on le retéléchargera
            except OSError:
                pass
        cls.en_cours.discard(cle)
        for c in list(cls.cartes):
            c.redessiner_tuiles()


def avec_zoom(trace, on_mode=None):
    """La carte + gros boutons + / − (et le bouton d'orientation), et l'attribution OpenStreetMap."""
    f = FloatLayout()
    trace.pos_hint = {"x": 0, "y": 0}  # sans pos_hint, FloatLayout laisse la carte collée en bas de l'écran
    f.add_widget(trace)
    for txt, fac, place in (("+", 1.4, {"y": 0.51}), ("−", 1 / 1.4, {"top": 0.49})):
        f.add_widget(Bouton(txt, lambda *_, fac=fac: trace.zoomer(fac), "carte", 56, 28,
                            size_hint=(None, None), width=dp(56), pos_hint={"right": 0.97, **place}))
    if on_mode:
        # en bas à gauche : le haut de la carte est au bandeau de navigation
        f.add_widget(Bouton("Sens de marche", on_mode, "carte", 48, 15, size_hint=(None, None),
                            width=dp(150), pos_hint={"x": 0.03, "y": 0.05}))
    f.add_widget(lab("© OpenStreetMap", 11, BRUME, size_hint=(None, None), size=(dp(110), dp(18)),
                     pos_hint={"x": 0.02, "y": 0.005}))
    return f


class Trace(StencilView):
    """suivi=False : vue d'ensemble (boucle, ou autour de « centre »). suivi=True : centré sur toi."""
    coords = ListProperty([])
    autres = ListProperty([])  # les autres propositions, en pâle
    moi = ListProperty([])
    fait = ListProperty([])
    boucle_faite = ListProperty([])  # partie de la boucle déjà parcourue (grisée)
    depart = ListProperty([])
    prochain = ListProperty([])  # (lat, lon) du prochain carrefour (navigation)
    rejoindre = ListProperty([])  # chemin calculé pour revenir sur la boucle, en pointillés
    centre = ListProperty([])  # vue d'ensemble sans boucle : autour de ce point
    zone = ListProperty([])  # [lat, lon, rayon m] : la zone de recherche, en cercle discret
    suivi = BooleanProperty(False)
    angle = NumericProperty(0)  # rotation actuelle de la carte (animée)
    revele = NumericProperty(1)  # part de la boucle déjà tracée (animée quand une boucle arrive)
    orient = "marche"  # marche (direction de marche en haut), boussole, nord
    cap = None  # direction de marche, en degrés
    az = None  # direction du téléphone (boussole)
    rayon = 250  # mètres visibles autour de toi au zoom 1 (suivi)
    rayon_vue = 1500  # mètres visibles autour de « centre » (vue d'ensemble)
    choix = None  # fonction appelée quand on touche la carte

    def __init__(self, **kw):
        super().__init__(**kw)
        self.x0 = self.y0 = None
        self.k = 1.0
        self.zoom, self.pan, self.s, self.cx, self.cy = 1.0, [0.0, 0.0], 1.0, 0, 0
        self.touches, self.multi = {}, False
        self.tr, self.sc = Translate(0, 0), Scale(1, 1, 1)
        self.rot = Rotate(angle=0, axis=(0, 0, 1), origin=(0, 0))
        self.g_tuiles, self.g_dyn = InstructionGroup(), InstructionGroup()
        for i in (PushMatrix(), self.rot, self.tr, self.sc, self.g_tuiles, self.g_dyn, PopMatrix()):
            self.canvas.add(i)
        Tuiles.cartes.add(self)
        self.bind(pos=self.dessiner, size=self.dessiner, coords=self.reset, suivi=self.reset, centre=self.reset,
                  moi=self.dessiner, depart=self.dessiner, revele=self.dessiner, autres=self.dessiner,
                  zone=self.dessiner, prochain=self.dessiner, rejoindre=self.dessiner)

    # --- projection ---
    def _origine(self, lat, lon):
        """L'origine suit le lieu : à plus de 50 km, on la replace (précision, et échelle locale juste)."""
        x, y = mercator(lat, lon)
        if self.x0 is None or math.hypot(x - self.x0, y - self.y0) * self.k > 50000:
            self.x0, self.y0, self.k = x, y, math.cos(math.radians(lat))
            self.g_tuiles.clear()

    def mondial(self, lat, lon):  # degrés -> mètres autour de l'origine
        x, y = mercator(lat, lon)
        return (x - self.x0) * self.k, (y - self.y0) * self.k

    def geo(self, x, y):
        return inverse(x / self.k + self.x0, y / self.k + self.y0)

    def reference(self):
        for pts in (self.coords, [self.moi] if self.suivi else [], [self.centre], [self.moi], [self.depart]):
            if pts and len(pts[0]) == 2:
                return pts[0]
        return None

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
        self.zoom = min(40, max(0.05, self.zoom * facteur))
        self.dessiner()

    def vue(self):
        if self.suivi and len(self.moi) == 2:
            self.cx, self.cy = self.mondial(*self.moi)
            base = min(self.width, self.height) / (2 * self.rayon)
            cap = self.cible()
            if self.cap is not None and self.orient != "nord":  # on voit plus loin devant que derrière
                avance = 0.32 * min(self.width, self.height) / 2 / (base * self.zoom)
                self.cx += avance * math.sin(math.radians(cap))
                self.cy += avance * math.cos(math.radians(cap))
        else:
            if len(self.coords) >= 2:
                pts = [self.mondial(*p) for p in self.coords]
                xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            else:
                c = self.mondial(*self.reference())
                xs, ys = [c[0] - self.rayon_vue, c[0] + self.rayon_vue], [c[1] - self.rayon_vue, c[1] + self.rayon_vue]
            base = min((self.width - 40) / max(max(xs) - min(xs), 1), (self.height - 40) / max(max(ys) - min(ys), 1))
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

    # --- tuiles ---
    def redessiner_tuiles(self):
        if self.x0 is None or self.width < 2:
            return
        self.g_tuiles.clear()
        cote_px = MONDE * self.k * self.s  # largeur du monde à l'écran, en pixels
        z = max(2, min(19, round(math.log2(max(cote_px / dp(256), 1)))))
        r = math.hypot(self.width, self.height) / 2 / self.s / self.k  # demi-diagonale, en mètres Mercator
        xm, ym = self.cx / self.k + self.x0, self.cy / self.k + self.y0
        jour = widgets.theme == "jour"
        self.g_tuiles.add(Color(1, 1, 1, 1) if jour else Color(0.42, 0.47, 0.45, 1))  # la nuit, tuiles assombries
        for zz in (z - 1, z):  # le niveau du dessous couvre les trous pendant le chargement
            n, cote = 2 ** zz, MONDE / 2 ** zz
            tx0, tx1 = int((xm - r + MONDE / 2) // cote), int((xm + r + MONDE / 2) // cote)
            ty0, ty1 = int((MONDE / 2 - (ym + r)) // cote), int((MONDE / 2 - (ym - r)) // cote)
            if (tx1 - tx0 + 1) * (ty1 - ty0 + 1) > 80:
                continue
            for tx in range(tx0, tx1 + 1):
                for ty in range(max(0, ty0), min(n - 1, ty1) + 1):
                    cle = (zz, tx % n, ty)
                    tex = Tuiles.textures.get(cle)
                    if tex is None:
                        if zz == z:
                            Tuiles.demander(*cle)
                        continue
                    gx = (tx * cote - MONDE / 2 - self.x0) * self.k
                    gy = (MONDE / 2 - (ty + 1) * cote - self.y0) * self.k
                    self.g_tuiles.add(Rectangle(texture=tex, pos=(gx, gy), size=(cote * self.k, cote * self.k)))

    def dessiner(self, *_):
        ref = self.reference()
        if ref is None or self.width < 2 or self.height < 2:
            return
        self._origine(*ref)
        self.vue()
        self.redessiner_tuiles()
        self.g_dyn.clear()
        u = 1 / self.s  # un pixel, en mètres

        def ligne(pts, couleur, px):
            self.g_dyn.add(Color(*couleur))
            self.g_dyn.add(Line(points=[v for p in pts for v in self.mondial(*p)], width=px * u, joint="round"))

        def disque(p, rayons):
            x, y = self.mondial(*p)
            for r, c in rayons:
                self.g_dyn.add(Color(*c))
                self.g_dyn.add(Ellipse(pos=(x - r * u, y - r * u), size=(2 * r * u, 2 * r * u)))

        if len(self.zone) == 3:  # la zone de recherche : un cercle discret
            x, y = self.mondial(*self.zone[:2])
            self.g_dyn.add(Color(*ENCRE[:3], 0.35))
            self.g_dyn.add(Line(circle=(x, y, self.zone[2]), width=1.5 * u))
        for autre in self.autres:
            if len(autre) >= 2:
                ligne(autre, (*TRACE_PALE[:3], 0.9), 4)
        if len(self.coords) >= 2:
            n = max(2, int(len(self.coords) * self.revele))
            ligne(self.coords[:n], FOND, 8)  # liseré : la boucle se détache des tuiles
            ligne(self.coords[:n], TRACE, 5)
        if len(self.boucle_faite) >= 2:  # la partie de la boucle déjà faite s'efface…
            ligne(self.boucle_faite, FOND, 8)
            ligne(self.boucle_faite, TRACE_PALE, 5)
        if len(self.fait) >= 2:  # … et ton vrai trajet par-dessus : encre bordée de pêche, distinct du prévu (sauge)
            ligne(self.fait, SIGNAL, 8)
            ligne(self.fait, ENCRE, 3.5)
        if len(self.rejoindre) >= 2:  # le chemin pour revenir sur la boucle, en couleur signal
            ligne(self.rejoindre, FOND, 8)
            ligne(self.rejoindre, SIGNAL, 4.5)
        if len(self.prochain) == 2 and self.suivi:  # le prochain carrefour : un anneau encre
            disque(self.prochain, ((13, FOND), (10, ENCRE), (5, FOND)))
        if len(self.coords) >= 2:  # départ et arrivée : le point du logo
            disque(self.coords[0], ((14, FOND), (11, SUR_SIGNAL), (8, SIGNAL)))
        if len(self.depart) == 2 and not self.suivi:
            disque(self.depart, ((14, FOND), (11, ENCRE), (5, FOND)))  # départ choisi, pas encore de boucle
        if len(self.moi) == 2:
            x, y = self.mondial(*self.moi)
            if self.cap is None:  # pas encore de direction : un point
                disque(self.moi, ((12, FOND), (10, TRACE), (5, FOND)))
            else:  # grande flèche orientée vers la direction de marche, lisible en courant
                sb, cb = math.sin(math.radians(self.cap)), math.cos(math.radians(self.cap))
                self.g_dyn.add(Color(*TRACE[:3], 0.22))
                self.g_dyn.add(Ellipse(pos=(x - 54 * u, y - 54 * u), size=(108 * u, 108 * u)))
                self.g_dyn.add(Color(*FOND))  # pastille claire : la flèche se détache de n'importe quelle tuile
                self.g_dyn.add(Ellipse(pos=(x - 36 * u, y - 36 * u), size=(72 * u, 72 * u)))

                def pt(a, b, k):
                    return x + (a * cb + b * sb) * k * u, y + (-a * sb + b * cb) * k * u

                for k, c in ((32, SUR_SIGNAL), (25, SIGNAL)):  # contour sombre, flèche signal (2 fois l'ancienne)
                    self.g_dyn.add(Color(*c))
                    self.g_dyn.add(Triangle(points=[*pt(0, 1.3, k), *pt(-0.95, -0.95, k), *pt(0, -0.4, k)]))
                    self.g_dyn.add(Triangle(points=[*pt(0, 1.3, k), *pt(0, -0.4, k), *pt(0.95, -0.95, k)]))

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
        if simple and not bouge and self.choix and self.x0 is not None:
            self.choix(*self.geo((t.pos[0] - self.tr.x) / self.s, (t.pos[1] - self.tr.y) / self.s))
        return True
