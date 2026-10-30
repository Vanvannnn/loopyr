"""Starva (Kivy). Ordre de travail, depuis ce dossier :
  1. python prepare_data.py     -> crée data.db (PC, avec internet)
  2. python main.py             -> test sur PC (pip install kivy), coureur simulé à la place du GPS
  3. buildozer android debug    -> APK dans bin/ (Linux ou WSL)
"""
import math, os, threading, time
from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import (Color, Ellipse, InstructionGroup, Line, Mesh, PopMatrix,
                           PushMatrix, Rectangle, Rotate, Scale, Translate, Triangle)
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ListProperty, NumericProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.stencilview import StencilView
from kivy.uix.textinput import TextInput
from kivy.utils import platform

from core import Carte
from course import Course, charger, enregistrer, fmt_allure, fmt_temps, haversine

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.db")
MINT, FOND, ENCRE = (0.20, 0.78, 0.55, 1), (0.07, 0.08, 0.09, 1), (0.05, 0.10, 0.08, 1)
CORAIL, GRIS, BLANC = (1, 0.35, 0.25, 1), (0.55, 0.58, 0.60, 1), (1, 1, 1, 1)
ARDOISE = (0.18, 0.20, 0.22, 1)


def bouton(texte, action, couleur=MINT, texte_couleur=ENCRE, hauteur=64):
    return Button(text=texte, font_size="20sp", bold=True, size_hint_y=None, height=dp(hauteur),
                  background_normal="", background_color=couleur, color=texte_couleur,
                  on_release=action)


def lab(texte, taille, couleur=BLANC, gras=False, **kw):
    l = Label(text=texte, font_size=f"{taille}sp", color=couleur, bold=gras, markup=True,
              halign="center", valign="middle", **kw)
    l.bind(size=lambda i, s: setattr(i, "text_size", s))
    return l


def cap_entre(a, b):
    """Direction (degrés, 0 = nord, sens horaire) en allant du point a vers le point b."""
    p1, p2, dl = math.radians(a[0]), math.radians(b[0]), math.radians(b[1] - a[1])
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return math.degrees(math.atan2(y, x)) % 360


def ecart(a, b):
    """Plus court écart signé (degrés) pour aller de a vers b."""
    return (b - a + 180) % 360 - 180


def creer_boussole(rappel):
    """Écoute du capteur d'orientation d'Android (téléphone uniquement)."""
    from jnius import PythonJavaClass, java_method

    class Ecoute(PythonJavaClass):
        __javainterfaces__ = ["android/hardware/SensorEventListener"]

        @java_method("(Landroid/hardware/Sensor;I)V")
        def onAccuracyChanged(self, sensor, precision):
            pass

        @java_method("(Landroid/hardware/SensorEvent;)V")
        def onSensorChanged(self, event):
            rappel(list(event.values))

    return Ecoute()


def avec_zoom(trace, on_mode=None):
    """La carte + gros boutons + / − (et le bouton d'orientation) par-dessus."""
    f = FloatLayout()
    f.add_widget(trace)
    for txt, fac, y in (("+", 1.4, 0.58), ("−", 1 / 1.4, 0.18)):
        f.add_widget(Button(text=txt, font_size="32sp", size_hint=(None, None),
                            size=(dp(60), dp(60)), pos_hint={"right": 0.98, "y": y},
                            background_normal="", background_color=(0.12, 0.14, 0.16, 0.9),
                            on_release=lambda *_, fac=fac: trace.zoomer(fac)))
    if on_mode:
        f.add_widget(Button(text="Cap : marche", font_size="15sp", size_hint=(None, None),
                            size=(dp(150), dp(48)), pos_hint={"x": 0.02, "top": 0.98},
                            background_normal="", background_color=(0.12, 0.14, 0.16, 0.9),
                            on_release=on_mode))
    return f


class Trace(StencilView):
    """Fond hors-ligne (rues et chemins de data.db), boucle, trajet, départ et toi.
    suivi=False : vue d'ensemble. suivi=True : centré sur toi.
    Zoom : pincer, molette ou boutons. Le fond est dessiné une fois puis déplacé par le GPU."""
    coords = ListProperty([])
    moi = ListProperty([])
    fait = ListProperty([])
    depart = ListProperty([])
    zone = ListProperty([])
    suivi = BooleanProperty(False)
    angle = NumericProperty(0)  # rotation actuelle de la carte (animée)
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
                  suivi=self.reset, moi=self.dessiner, depart=self.dessiner)

    def mondial(self, lat, lon):  # degrés -> mètres autour du centre de la zone
        return (lon - self.lon0) * self.k * 111000, (lat - self.lat0) * 111000

    def geo(self, x, y):
        return self.lat0 + y / 111000, self.lon0 + x / (self.k * 111000)

    def init_zone(self, *_):
        (la0, lo0), (la1, lo1) = self.zone
        self.lat0, self.lon0 = (la0 + la1) / 2, (lo0 + lo1) / 2
        self.k = math.cos(math.radians(self.lat0))
        self.g_res.clear()
        for t, couleur in ((0, (0.48, 0.53, 0.60)), (1, (0.80, 0.62, 0.30))):  # routes, chemins
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

        def point(p, r, centre):
            x, y = self.mondial(*p)
            for rr, c in ((r, BLANC), (r * 0.62, centre)):
                self.g_dyn.add(Color(*c))
                self.g_dyn.add(Ellipse(pos=(x - rr * u, y - rr * u), size=(2 * rr * u, 2 * rr * u)))

        if len(self.coords) >= 2:
            ligne(self.coords, MINT, 3)
        if len(self.fait) >= 2:
            ligne(self.fait, BLANC, 4)
        if len(self.coords) >= 2:
            point(self.coords[0], 12, MINT)  # départ de la boucle
        if len(self.depart) == 2 and not self.suivi:
            point(self.depart, 13, (0.95, 0.75, 0.20, 1))  # départ choisi
        if len(self.moi) == 2:
            if self.cap is None:
                point(self.moi, 12, CORAIL)  # pas encore de direction : un point
            else:  # flèche orientée vers la direction de marche
                x, y = self.mondial(*self.moi)
                sb, cb = math.sin(math.radians(self.cap)), math.cos(math.radians(self.cap))
                self.g_dyn.add(Color(1, 0.35, 0.25, 0.25))
                self.g_dyn.add(Ellipse(pos=(x - 30 * u, y - 30 * u), size=(60 * u, 60 * u)))

                def pt(a, b, k):
                    return x + (a * cb + b * sb) * k * u, y + (-a * sb + b * cb) * k * u

                for k, c in ((19, BLANC), (14, CORAIL)):  # contour blanc, puis flèche corail
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


class StarvaApp(App):
    def build(self):
        Window.clearcolor = FOND
        self.carte, self.gps_pos, self.course, self.res, self.note = None, None, None, None, ""
        self.chemin_profil = os.path.join(self.user_data_dir, "profil.json")
        self.sm = ScreenManager()
        for ecran in (self.ecran_plan(), self.ecran_course(), self.ecran_profil()):
            self.sm.add_widget(ecran)
        threading.Thread(target=self._charger, daemon=True).start()
        self.gps_demarre, self.dernier_t, self.t_cb = False, 0, 0
        self.cap, self.dernier_pt, self.az, self.az_brut, self.ecoute = None, None, None, None, None
        self.boussole_on = False
        return self.sm

    def on_start(self):
        self.demander_gps()

    # --- écran 1 : préparer la boucle ---
    def ecran_plan(self):
        e = Screen(name="plan")
        col = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        titres = BoxLayout(size_hint_y=None, height=dp(22), spacing=dp(8))
        for t in ("Distance (km)", "Dénivelé + (m)", "Terrain"):
            titres.add_widget(lab(t, 13, GRIS))
        ligne = BoxLayout(size_hint_y=None, height=dp(64), spacing=dp(8))
        champ = dict(font_size="26sp", multiline=False, padding=[dp(14), dp(16), dp(14), dp(8)],
                     background_color=(0.16, 0.18, 0.20, 1), foreground_color=BLANC)
        self.km = TextInput(text="5", input_filter="float", **champ)
        self.dp = TextInput(text="80", input_filter="int", **champ)
        self.pref = Spinner(text="hybride", values=("hybride", "trail", "route"), font_size="20sp",
                            background_normal="", background_color=ARDOISE)
        for w in (self.km, self.dp, self.pref):
            ligne.add_widget(w)
        self.depart_choisi = None
        self.sel_depart = Spinner(text="Ma position", values=("Ma position", "Choisir sur la carte"),
                                  font_size="20sp", size_hint_y=None, height=dp(56),
                                  background_normal="", background_color=ARDOISE)
        self.sel_depart.bind(text=self.changer_depart)
        self.info = lab("Chargement de la carte…", 18, size_hint_y=None, height=dp(52))
        self.l_gps = lab("", 14, GRIS, size_hint_y=None, height=dp(44))
        self.trace = Trace()
        bas = BoxLayout(size_hint_y=None, height=dp(64), spacing=dp(8))
        bas.add_widget(bouton("Démarrer la course", self.demarrer))
        bas.add_widget(bouton("Mon profil", lambda *_: setattr(self.sm, "current", "profil"),
                              ARDOISE, BLANC))
        for w in (titres, ligne, self.sel_depart, bouton("Générer la boucle", self.generer),
                  self.info, self.l_gps, avec_zoom(self.trace), bas):
            col.add_widget(w)
        e.add_widget(col)
        return e

    def _charger(self):
        self.carte = Carte(DB)
        reseau = {0: [], 1: []}
        for t, pts in self.carte.segments():
            reseau[t].append(pts)
        self.trace.reseau = self.trace2.reseau = reseau
        lats = [n[0] for n in self.carte.nodes.values()]
        lons = [n[1] for n in self.carte.nodes.values()]
        zone = [(min(lats), min(lons)), (max(lats), max(lons))]
        Clock.schedule_once(lambda dt: self.carte_prete(zone))

    def carte_prete(self, zone):
        self.trace.zone = self.trace2.zone = zone
        self.info.text = "Carte prête"

    def changer_depart(self, _, texte):
        choisir = texte == "Choisir sur la carte"
        self.trace.choix = self.point_choisi if choisir else None
        if choisir:  # vue d'ensemble de la zone, pour pouvoir toucher la carte
            self.res = None
            self.trace.coords = []
            self.info.text = "Touche la carte pour choisir ton départ"
        else:
            self.depart_choisi = None
            self.trace.depart = []

    def point_choisi(self, lat, lon):
        self.depart_choisi = (lat, lon)
        self.trace.depart = [lat, lon]
        self.info.text = "Départ choisi : génère ta boucle"

    def point_depart(self):
        """Renvoie (noeud de départ, message) : le point choisi, ou la position du téléphone."""
        if self.sel_depart.text == "Choisir sur la carte":
            pt, hors = self.depart_choisi, "Ce point est hors de la zone embarquée"
            if pt is None:
                return None, "Touche la carte pour choisir ton départ"
        else:
            pt, hors = self.gps_pos, "Tu es hors de la zone embarquée"
            if pt is None:
                return self.carte.depart, "pas de GPS : départ au centre de la zone"
        if not self.carte.dans_zone(*pt):
            return self.carte.depart, hors + " : départ au centre"
        return self.carte.plus_proche(*pt), ""

    def generer(self, *_):
        if not self.carte:
            return
        dep, self.note = self.point_depart()
        if dep is None:
            self.info.text = self.note
            return
        self.info.text = "Calcul en cours…"
        args = (float(self.km.text or 5) * 1000, float(self.dp.text or 0), self.pref.text, dep)
        threading.Thread(target=self._calcul, args=args, daemon=True).start()

    def _calcul(self, dist, dp_, pref, dep):
        res = self.carte.generer(dist, dp_, pref, dep)
        Clock.schedule_once(lambda dt: self.afficher(res))

    def afficher(self, res):
        if not res:
            self.info.text = "Aucune boucle trouvée : change la distance ou le D+"
            return
        self.res = res
        self.trace.coords = res["coords"]
        txt = f"{res['distance'] / 1000:.1f} km   D+ {res['denivele']:.0f} m"
        self.info.text = txt + (f"\n({self.note})" if self.note else "")

    # --- écran 2 : la course ---
    def ecran_course(self):
        e = Screen(name="course")
        col = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(6))
        self.trace2 = Trace(suivi=True)
        self.l_dist = lab("0.00", 76, MINT, True, size_hint_y=None, height=dp(96))
        self.l_prevu = lab("", 16, GRIS, size_hint_y=None, height=dp(24))
        self.l_temps = lab("00:00:00", 42, gras=True, size_hint_y=None, height=dp(58))
        cases = BoxLayout(size_hint_y=None, height=dp(80), spacing=dp(8))
        self.l_allure = lab("--:--", 34, gras=True)
        self.l_vitesse = lab("0.0", 34, gras=True)
        for val, unite in ((self.l_allure, "min/km"), (self.l_vitesse, "km/h")):
            c = BoxLayout(orientation="vertical")
            c.add_widget(val)
            c.add_widget(lab(unite, 15, GRIS, size_hint_y=None, height=dp(22)))
            cases.add_widget(c)
        panneau = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(330), spacing=dp(2))
        with panneau.canvas.before:  # fond plein : la carte ne peut pas passer sous les chiffres
            Color(*FOND)
            fond = Rectangle(pos=panneau.pos, size=panneau.size)
        panneau.bind(pos=lambda w, v: setattr(fond, "pos", v),
                     size=lambda w, v: setattr(fond, "size", v))
        for w in (self.l_dist, self.l_prevu, self.l_temps, cases,
                  bouton("Terminer la course", self.terminer, CORAIL, BLANC, 64)):
            panneau.add_widget(w)
        col.add_widget(avec_zoom(self.trace2, self.changer_orient))
        col.add_widget(panneau)
        e.add_widget(col)
        return e

    def changer_orient(self, btn):
        self.btn_cap = btn
        try:
            suite = {"marche": "boussole", "boussole": "nord", "nord": "marche"}
            if platform != "android":  # pas de boussole sur PC
                suite = {"marche": "nord", "nord": "marche"}
            mode = suite[self.trace2.orient]
            Clock.unschedule(self.maj_boussole)
            if mode == "boussole":
                if self.boussole(True):
                    Clock.schedule_interval(self.maj_boussole, 0.1)
                else:
                    mode = "nord"
            else:
                self.boussole(False)
                self.trace2.az = None
            self.trace2.orient = mode
            btn.text = {"marche": "Cap : marche", "boussole": "Cap : boussole", "nord": "Cap : nord"}[mode]
            self.trace2.dessiner()
        except Exception as err:
            self.l_prevu.text = f"Orientation : erreur ({err})"

    def boussole(self, activer):
        """Active ou coupe le capteur d'orientation (Android). Renvoie False si indisponible."""
        if platform != "android":
            return False
        try:
            from jnius import autoclass, cast
            act = autoclass("org.kivy.android.PythonActivity").mActivity
            sm = cast("android.hardware.SensorManager", act.getSystemService("sensor"))
            if activer:
                capteur = sm.getDefaultSensor(11)  # TYPE_ROTATION_VECTOR
                if capteur is None:
                    self.l_prevu.text = "Pas de boussole sur ce téléphone"
                    return False
                if self.ecoute is None:  # créé une fois et gardé : Android peut encore l'appeler
                    self.ecoute = creer_boussole(self.lire_boussole)
                self.boussole_on = True
                sm.registerListener(self.ecoute, capteur, 2)
            elif self.boussole_on:
                self.boussole_on = False
                sm.unregisterListener(self.ecoute)
                self.az_brut = self.az = None
        except Exception as err:
            self.l_prevu.text = f"Boussole indisponible ({err})"
            return False
        return True

    def lire_boussole(self, v):  # appelé par Android : on garde juste la valeur
        if not self.boussole_on:
            return
        x, y, z = v[0], v[1], v[2]
        w = v[3] if len(v) > 3 else math.sqrt(max(0.0, 1 - x * x - y * y - z * z))
        r1, r2, r4 = 2 * (x * y - z * w), 2 * (x * z + y * w), 1 - 2 * (x * x + z * z)
        r5, r8 = 2 * (y * z - x * w), 1 - 2 * (x * x + y * y)
        if abs(r8) > 0.7:  # téléphone à plat : on vise le haut de l'écran
            az = math.degrees(math.atan2(r1, r4))
        else:  # téléphone debout : on vise l'arrière (là où tu regardes)
            az = math.degrees(math.atan2(-r2, -r5))
        self.az_brut = az % 360

    def maj_boussole(self, dt):
        if self.az_brut is None:
            return
        self.az = self.az_brut if self.az is None else (self.az + 0.25 * ecart(self.az, self.az_brut)) % 360
        self.trace2.az = self.az
        self.trace2.maj_angle()

    def demarrer(self, *_):
        if not self.res:
            self.info.text = "Génère d'abord une boucle"
            return
        if platform == "android" and not self.gps_pos:
            self.info.text = "En attendant le signal GPS, ne pars pas encore (voir l'état GPS)"
            return
        self.course = Course()
        self.trace2.fait = []
        self.trace2.coords = self.res["coords"]
        self.l_prevu.text = f"sur {self.res['distance'] / 1000:.1f} km prévus"
        Window.allow_screensaver = False  # écran allumé pendant la course
        self.sm.current = "course"
        Clock.schedule_interval(self.maj_stats, 0.5)
        if platform != "android":  # sur PC : coureur virtuel qui suit la boucle
            self.sim_i, self.sim_d = 0, 0.0
            self.nouvelle_position(*self.res["coords"][0])
            Clock.schedule_interval(self.simuler, 1)
        else:
            self.nouvelle_position(*self.gps_pos)

    def simuler(self, dt):
        pts = self.res["coords"]
        reste = (3 + 0.6 * math.sin(self.course.duree() / 8)) * dt  # ~3 m/s, avec des variations
        while self.sim_i < len(pts) - 1:
            d = haversine(pts[self.sim_i], pts[self.sim_i + 1])
            if self.sim_d + reste < d:
                self.sim_d += reste
                break
            reste -= d - self.sim_d
            self.sim_d, self.sim_i = 0.0, self.sim_i + 1
        a, b = pts[self.sim_i], pts[min(self.sim_i + 1, len(pts) - 1)]
        f = self.sim_d / (haversine(a, b) or 1e-6)
        self.nouvelle_position(a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)

    def nouvelle_position(self, lat, lon, precision=None, age=0):
        self.gps_pos = (lat, lon)
        p = (lat, lon)
        if self.dernier_pt is None:
            self.dernier_pt = p
        elif haversine(self.dernier_pt, p) >= 4:  # direction de marche, lissée
            nouveau = cap_entre(self.dernier_pt, p)
            self.cap = nouveau if self.cap is None else (self.cap + 0.6 * ecart(self.cap, nouveau)) % 360
            self.dernier_pt = p
        self.trace.cap = self.trace2.cap = self.cap
        self.trace.moi = [lat, lon]
        if platform == "android":
            if age > 30:
                self.l_gps.text = (f"GPS : dernière position connue (il y a {age / 60:.0f} min). "
                                   "Va dehors pour un signal frais")
            else:
                self.l_gps.text = "GPS : ok" + (f" (précision {precision:.0f} m)" if precision else "")
        if self.course and age <= 30:
            self.course.ajouter(lat, lon, precision)
            self.trace2.fait = list(self.course.trace)
            self.trace2.moi = [lat, lon]

    def maj_stats(self, dt):
        c, v = self.course, self.course.vitesse()
        self.l_dist.text = f"{c.dist / 1000:.2f}[size=26sp] km[/size]"
        self.l_temps.text = fmt_temps(c.duree())
        self.l_allure.text = fmt_allure(v)
        self.l_vitesse.text = f"{v * 3.6:.1f}"

    def terminer(self, *_):
        Clock.unschedule(self.maj_stats)
        Clock.unschedule(self.simuler)
        c = self.course
        c.terminer()
        moy = fmt_allure(c.dist / c.duree()) if c.duree() else "--:--"
        boite = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(12))
        boite.add_widget(lab(f"{c.dist / 1000:.2f} km en {fmt_temps(c.duree())}\n"
                             f"allure moyenne {moy} min/km", 24))
        ligne = BoxLayout(size_hint_y=None, height=dp(64), spacing=dp(8))
        pop = Popup(title="Course terminée", content=boite, size_hint=(0.92, 0.55),
                    auto_dismiss=False, title_size="20sp")
        ligne.add_widget(bouton("Enregistrer", lambda *_: self.fin_course(pop, True)))
        ligne.add_widget(bouton("Supprimer", lambda *_: self.fin_course(pop, False), ARDOISE, BLANC))
        boite.add_widget(ligne)
        pop.open()

    def fin_course(self, pop, garder):
        pop.dismiss()
        if garder and self.course.dist > 0:
            enregistrer(self.chemin_profil, self.course.resume())
        self.course = None
        self.trace2.fait = []
        self.boussole(False)
        Clock.unschedule(self.maj_boussole)
        self.trace2.orient = "marche"
        if getattr(self, "btn_cap", None):
            self.btn_cap.text = "Cap : marche"
        Window.allow_screensaver = True
        self.sm.current = "plan"

    # --- écran 3 : profil ---
    def ecran_profil(self):
        e = Screen(name="profil")
        col = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        self.l_totaux = lab("", 26, MINT, True, size_hint_y=None, height=dp(70))
        self.liste = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(8))
        self.liste.bind(minimum_height=self.liste.setter("height"))
        sv = ScrollView()
        sv.add_widget(self.liste)
        for w in (self.l_totaux, sv, bouton("Retour", lambda *_: setattr(self.sm, "current", "plan"))):
            col.add_widget(w)
        e.add_widget(col)
        e.bind(on_pre_enter=self.remplir_profil)
        return e

    def remplir_profil(self, *_):
        courses = charger(self.chemin_profil)
        total = sum(r["distance"] for r in courses) / 1000
        self.l_totaux.text = f"{len(courses)} courses   {total:.1f} km"
        self.liste.clear_widgets()
        for r in courses:
            moy = fmt_allure(r["distance"] / r["duree"]) if r["duree"] else "--:--"
            self.liste.add_widget(lab(f"{r['date']}\n{r['distance'] / 1000:.2f} km   "
                                      f"{fmt_temps(r['duree'])}   {moy} /km", 18,
                                      size_hint_y=None, height=dp(64)))

    # --- GPS (Android uniquement) ---
    def etat_gps(self, texte):
        Clock.schedule_once(lambda dt: setattr(self.l_gps, "text", texte))

    def demander_gps(self):
        try:
            from android.permissions import Permission, check_permission, request_permissions
        except ImportError:
            self.l_gps.text = "PC : position simulée pendant la course"
            return
        self.perms = [Permission.ACCESS_FINE_LOCATION, Permission.ACCESS_COARSE_LOCATION]
        self.l_gps.text = "GPS : autorisation en cours…"
        if check_permission(self.perms[0]):  # déjà accordée : Android n'appellerait pas le callback
            self.precis = True
            Clock.schedule_once(self._demarrer_gps, 0.5)
        else:
            request_permissions(self.perms, self._perm_ok)
            Clock.schedule_interval(self._attendre_perm, 1)

    def _perm_ok(self, perms, results):  # réponse à la fenêtre d'autorisation
        if not any(results):
            self.etat_gps("GPS : localisation refusée (Réglages > Applis > Starva > Autorisations)")

    def _attendre_perm(self, dt):
        if self.gps_demarre:
            return False
        try:
            from android.permissions import check_permission
            fin, gros = check_permission(self.perms[0]), check_permission(self.perms[1])
        except Exception as err:
            self.l_gps.text = f"GPS : erreur d'autorisation ({err})"
            return False
        if fin or gros:
            self.precis = fin
            self._demarrer_gps(dt)
            return False

    def _demarrer_gps(self, dt):
        if self.gps_demarre:
            return
        self.gps_demarre = True
        try:
            from plyer import gps
            gps.configure(on_location=self.on_loc, on_status=self.on_status)
            gps.start(minTime=1000, minDistance=0)
            self.l_gps.text = ("GPS : recherche du signal…" if self.precis
                               else "GPS : position approximative seulement, autorise la position précise")
        except Exception as err:
            self.l_gps.text = f"GPS (plyer) indisponible : {err}"
        Clock.schedule_interval(self.sonder, 1)  # plan B : on interroge Android directement

    def sonder(self, dt):
        """Si l'écoute de plyer ne reçoit rien, on lit la dernière position connue d'Android."""
        try:
            from jnius import autoclass, cast
            act = autoclass("org.kivy.android.PythonActivity").mActivity
            lm = cast("android.location.LocationManager", act.getSystemService("location"))
            gps_on, res_on = bool(lm.isProviderEnabled("gps")), bool(lm.isProviderEnabled("network"))
            best = None
            for p in ("gps", "network", "passive"):
                loc = lm.getLastKnownLocation(p)
                if loc is not None and (best is None or loc.getTime() > best.getTime()):
                    best = loc
        except Exception as err:
            self.l_gps.text = f"GPS : sondage impossible ({err})"
            return
        if not gps_on:
            self.l_gps.text = "La localisation du téléphone est désactivée : active-la dans les réglages"
        elif best is None and not self.gps_pos:
            self.l_gps.text = f"GPS : recherche du signal… (réseau {'oui' if res_on else 'non'})"
        if best is not None and best.getTime() != self.dernier_t and time.time() - self.t_cb > 3:
            self.dernier_t = best.getTime()
            age = time.time() - best.getTime() / 1000
            self.nouvelle_position(best.getLatitude(), best.getLongitude(), best.getAccuracy(), age)

    def on_status(self, stype, status):
        self.etat_gps(f"GPS : {stype} {status}")

    def on_loc(self, **kw):
        self.t_cb = time.time()
        try:
            lat, lon, prec = kw["lat"], kw["lon"], kw.get("accuracy")
        except KeyError:
            self.etat_gps(f"GPS : réponse inattendue {list(kw)}")
            return
        Clock.schedule_once(lambda dt: self.nouvelle_position(lat, lon, prec))


if __name__ == "__main__":
    StarvaApp().run()