"""Écran 3 : l'historique des courses, et le détail d'une course (trace, splits, export GPX)."""
import time

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.graphics import Color, Line, Rectangle, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.properties import NumericProperty
from kivy.uix.widget import Widget

from course import fmt_allure
from gpx import exportable, gpx
from ui.carte import Trace, avec_zoom
from ui.ecran_course import chrono
from ui.widgets import (BRUME, ENCRE, FOND, FOND_2, ROUTE, TRACE, Bouton, Croissance, Splits, apparaitre, echelle,
                        confirmer, desarmer, fond, hexa_de, lab, nombre, unite)

JOURS = ("lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim.")
MOIS = ("janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc.")
SEMAINE = 7 * 86400


def allure_moy(act):
    return fmt_allure(act["distance"] / act["duree"]) if act.get("duree") else "--:--"


def debut(act):
    """Heure de départ (epoch), y compris pour les courses d'avant, qui n'avaient que la date."""
    if act.get("debut"):
        return act["debut"]
    try:
        return time.mktime(time.strptime(act["date"], "%Y-%m-%d %H:%M"))
    except (KeyError, ValueError):
        return 0


def date_fr(act):
    t = time.localtime(debut(act))
    return f"{JOURS[t.tm_wday]} {t.tm_mday} {MOIS[t.tm_mon - 1]}, {t.tm_hour}h{t.tm_min:02d}"


def duree_longue(s):
    h, m = int(s // 3600), int(s % 3600 // 60)
    return f"{h} h {m:02d}" if h else f"{m} min"


def lundi(t):
    """Début (epoch, minuit local) de la semaine de t."""
    j = time.localtime(t)
    return time.mktime((j.tm_year, j.tm_mon, j.tm_mday - j.tm_wday, 0, 0, 0, 0, 0, -1))


def km_par_semaine(acts, maintenant, n=10):
    """Les n dernières semaines, de la plus ancienne à celle en cours : [(lundi, km)]."""
    fin = lundi(maintenant)
    semaines = [lundi(fin - i * SEMAINE + 3 * 86400) for i in range(n - 1, -1, -1)]  # +3 j : changement d'heure
    km = dict.fromkeys(semaines, 0.0)
    for a in acts:
        l = lundi(debut(a))
        if l in km:
            km[l] += a["distance"] / 1000
    return list(km.items())


class Semaines(BoxLayout):
    """Histogramme des km par semaine : barres encre sur filet, la semaine en cours en sauge.
    Les barres poussent depuis le filet à chaque arrivée sur l'écran."""

    def __init__(self, **kw):
        super().__init__(orientation="vertical", size_hint_y=None, height=dp(150), spacing=dp(4), **kw)
        self.barres = Croissance()
        self.dates = BoxLayout(size_hint_y=None, height=dp(18))
        self.add_widget(self.barres)
        self.add_widget(self.dates)
        self.valeurs = []
        self.barres.bind(pos=self.dessiner, size=self.dessiner, pousse=self.dessiner)

    def remplir(self, valeurs):
        self.valeurs = valeurs
        self.dates.clear_widgets()
        for i, (l, _) in enumerate(valeurs):
            t = time.localtime(l)
            pair = (len(valeurs) - 1 - i) % 2 == 0  # une date sur deux, en finissant par la semaine en cours
            self.dates.add_widget(lab(f"{t.tm_mday}/{t.tm_mon}" if pair else "", 15, BRUME, chiffres=True,
                                      aligne="center"))
        self.barres.faire_pousser(0.8)

    def dessiner(self, *_):
        w = self.barres
        w.canvas.clear()
        if not self.valeurs:
            return
        n, haut = len(self.valeurs), max(km for _, km in self.valeurs) or 1
        larg = w.width / n
        with w.canvas:
            Color(*ROUTE)
            Line(points=[w.x, w.y, w.right, w.y], width=dp(1))
            for i, (_, km) in enumerate(self.valeurs):
                Color(*(TRACE if i == n - 1 else ENCRE))
                retard = i / n * 0.35  # de gauche à droite, la semaine en cours en dernier
                p = max(0.0, min(1.0, (w.pousse - retard) / (1 - retard)))
                h = max(dp(2), (w.height - dp(4)) * km / haut) * p if km else 0
                RoundedRectangle(pos=(w.x + i * larg + larg * 0.18, w.y), size=(larg * 0.64, h),
                                 radius=[dp(3), dp(3), 0, 0])


class Ligne(ButtonBehavior, BoxLayout):
    """Une course de la liste : date et allure à gauche, distance en gros à droite."""

    def __init__(self, act, action, **kw):
        super().__init__(size_hint_y=None, height=dp(74), padding=[0, dp(10)], **kw)
        echelle(self)  # avant le fond : la ligne entière grandit à son arrivée
        with self.canvas.before:
            self._c = Color(*FOND)
            self._fond = Rectangle()
            Color(*FOND_2)
            self._filet = Rectangle()
        self.bind(pos=self._maj, size=self._maj, state=self._maj, on_release=lambda *_: action())
        gauche = BoxLayout(orientation="vertical")
        gauche.add_widget(lab(date_fr(act), 17, gras=True))
        gauche.add_widget(lab(f"{chrono(act.get('duree') or 0)}  {allure_moy(act)} /km", 19, BRUME, chiffres=True))
        self.add_widget(gauche)
        self.add_widget(lab(f"{nombre(act['distance'] / 1000, 2)}{unite('km', 15)}", 38, gras=True, chiffres=True,
                            aligne="right", size_hint_x=0.55))

    def _maj(self, *_):
        self._c.rgba = FOND_2 if self.state == "down" else FOND
        self._fond.pos, self._fond.size = (self.x - dp(20), self.y), (self.width + dp(40), self.height)
        self._filet.pos, self._filet.size = (self.x, self.y), (self.width, dp(1))


def barre_titre(titre, retour):
    b = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(6))
    b.add_widget(Bouton("‹ Retour", retour, "discret", 56, 17, size_hint_x=None, width=dp(104)))
    l = lab(titre, 18, gras=True, aligne="right")
    b.add_widget(l)
    b.titre = l
    return b


class EcranProfil(Screen):
    compte = NumericProperty(0)  # total de km affiché, qui défile jusqu'au vrai total

    def __init__(self, app, **kw):
        super().__init__(name="profil", **kw)
        self.app = app
        col = BoxLayout(orientation="vertical", padding=[dp(20), dp(4), dp(20), 0])
        col.add_widget(barre_titre("Historique", lambda *_: app.aller("plan", "retour")))
        sv = ScrollView(do_scroll_x=False)
        self.contenu = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(6))
        self.contenu.bind(minimum_height=self.contenu.setter("height"))
        self.l_totaux = lab("", 88, gras=True, chiffres=True, size_hint_y=None, height=dp(96))
        self.l_soustitre = lab("", 16, BRUME, size_hint_y=None, height=dp(24))
        self.l_semaine = lab("", 16, gras=True, size_hint_y=None, height=dp(48))
        self.semaines = Semaines()
        self.liste = BoxLayout(orientation="vertical", size_hint_y=None)
        self.liste.bind(minimum_height=self.liste.setter("height"))
        for w in (self.l_totaux, self.l_soustitre, self.l_semaine, self.semaines,
                  Widget(size_hint_y=None, height=dp(18)), self.liste):
            self.contenu.add_widget(w)
        sv.add_widget(self.contenu)
        col.add_widget(sv)
        self.add_widget(col)
        self.bind(on_pre_enter=self.remplir)

    def remplir(self, *_):
        acts = self.app.stockage.lister()
        km = sum(a["distance"] for a in acts) / 1000
        temps = sum(a.get("duree") or 0 for a in acts)
        dplus = sum(a.get("denivele") or 0 for a in acts)
        Animation.cancel_all(self, "compte")
        self.compte = 0
        Animation(compte=km, d=0.8, t="out_cubic").start(self)
        n = len(acts)
        self.l_soustitre.text = (f"{n} course{'s' if n > 1 else ''}, {duree_longue(temps)} de course, "
                                 f"{dplus:.0f} m de D+")
        semaines = km_par_semaine(acts, time.time())
        self.semaines.remplir(semaines)
        self.l_semaine.text = f"Cette semaine : [color={hexa_de(TRACE)}]{nombre(semaines[-1][1])} km[/color]"
        self.liste.clear_widgets()
        if not acts:
            self.liste.add_widget(lab("Pas encore de course. Génère une boucle et pars.", 17, BRUME,
                                      size_hint_y=None, height=dp(60)))
            self.liste.add_widget(Bouton("Préparer une sortie", lambda *_: self.app.aller("plan", "retour"),
                                         "encre", 64))
        for i, a in enumerate(acts):
            ligne = Ligne(a, lambda id_=a["id"]: self.app.ecran_detail.ouvrir(id_))
            self.liste.add_widget(ligne)
            if i < 8:  # les premières lignes arrivent l'une après l'autre ; les suivantes sont hors écran
                ligne.opacity = 0
                Clock.schedule_once(lambda dt, l=ligne: apparaitre(l, 0.3, 0.97), 0.25 + 0.05 * i)

    def on_compte(self, *_):
        self.l_totaux.text = f"{nombre(self.compte)}{unite('km', 22)}"


class EcranDetail(Screen):
    def __init__(self, app, **kw):
        super().__init__(name="detail", **kw)
        self.app, self.act = app, None
        col = BoxLayout(orientation="vertical")
        self.barre = barre_titre("", lambda *_: app.aller("profil", "retour"))
        self.barre.padding = [dp(20), dp(4), dp(20), 0]
        self.trace = Trace()
        panneau = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(390),
                            padding=[dp(20), dp(10), dp(20), dp(18)], spacing=dp(8))
        fond(panneau, FOND)
        self.l_titre = lab("", 72, gras=True, chiffres=True, size_hint_y=None, height=dp(78))
        chiffres = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(12))
        self.cases = []
        for legende, couleur in (("temps", None), ("allure, min/km", None), ("dénivelé", TRACE)):
            c = BoxLayout(orientation="vertical")
            v = lab("", 30, couleur or ENCRE, gras=True, chiffres=True)
            c.add_widget(v)
            c.add_widget(lab(legende, 13, BRUME, size_hint_y=None, height=dp(18)))
            self.cases.append(v)
            chiffres.add_widget(c)
        sv = ScrollView(do_scroll_x=False)
        self.splits = Splits()
        sv.add_widget(self.splits)
        self.l_info = lab("", 14, BRUME, size_hint_y=None, height=dp(22))
        bas = BoxLayout(size_hint_y=None, height=dp(68), spacing=dp(10))
        self.btn_gpx = Bouton("Exporter le GPX", self.exporter, "encre", 68, 19)
        self.btn_suppr = Bouton("Supprimer", self.supprimer, "contour", 68, 17, size_hint_x=0.6)
        bas.add_widget(self.btn_gpx)
        bas.add_widget(self.btn_suppr)
        for w in (self.l_titre, chiffres, sv, self.l_info, bas):
            panneau.add_widget(w)
        for w in (self.barre, avec_zoom(self.trace), panneau):
            col.add_widget(w)
        self.add_widget(col)

    def ouvrir(self, id_):
        a = self.act = self.app.stockage.charger(id_)
        self.barre.titre.text = date_fr(a)
        self.l_titre.text = f"{nombre(a['distance'] / 1000, 2)}{unite('km', 22)}"
        for case, texte in zip(self.cases, (chrono(a.get("duree") or 0), allure_moy(a),
                                            f"{a.get('denivele') or 0:.0f}{unite('m', 14)}")):
            case.text = texte
        pts = [(p[1], p[2]) for seg in a.get("segments") or () for p in seg] or a.get("trace") or []
        pas = max(1, len(pts) // 1500)
        self.trace.tracer([tuple(p) for p in pts[::pas]], 0.9)
        self.splits.remplir(a.get("splits") or ())
        self.btn_gpx.disabled = not exportable(a)
        self.l_info.text = "" if exportable(a) else "Course d'avant la mise à jour, sans heure par point : pas d'export"
        desarmer(self.btn_suppr)
        self.app.aller("detail")

    def exporter(self, *_):
        a = self.act
        try:
            self.l_info.text = self.app.exporter_gpx(f"loopy-{a['id']}.gpx", gpx(a))
        except Exception as err:
            self.l_info.text = f"Export impossible : {err}"

    def supprimer(self, btn):
        def go():
            self.app.stockage.supprimer(self.act["id"])
            self.app.aller("profil", "retour")
        confirmer(btn, "Supprimer ?", go)
