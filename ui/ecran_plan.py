"""Écran 1 : préparer la boucle (distance, D+, terrain, départ) et la générer."""
import threading

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import Screen
from kivy.utils import platform

from ui.carte import Trace, avec_zoom
from ui.logo import Symbole
from ui import widgets
from ui.widgets import BRUME, FOND, MARQUE, SIGNAL, Bouton, Pas, Segmente, apparaitre, fond, lab, nombre

MA_POSITION, SUR_LA_CARTE = "gps", "carte"


def lire_parametres(km, dplus, distance_max):
    """Valide les champs. Renvoie ((distance m, D+ m), None) ou (None, message d'erreur)."""
    try:
        distance = float((km or "").replace(",", ".")) * 1000
        d_plus = float(dplus or 0)
    except ValueError:
        return None, "Distance ou D+ invalide"
    if not 1000 <= distance <= distance_max:
        return None, f"Distance entre 1 et {distance_max / 1000:.0f} km"
    if not 0 <= d_plus <= distance * 0.15:
        return None, f"D+ entre 0 et {distance * 0.15:.0f} m pour cette distance"
    return (distance, d_plus), None


class EcranPlan(Screen):
    def __init__(self, app, **kw):
        super().__init__(name="plan", **kw)
        self.app, self.res, self.note, self.depart_choisi, self.calcul = app, None, "", None, False
        col = BoxLayout(orientation="vertical")

        # la carte en grand, avec la marque et l'historique posés dessus
        self.trace = Trace()
        carte = avec_zoom(self.trace)
        marque = BoxLayout(size_hint=(None, None), size=(dp(114), dp(44)), spacing=dp(6),
                           padding=[dp(6), dp(4), dp(12), dp(4)], pos_hint={"x": 0.03, "top": 0.97})
        fond(marque, (*FOND[:3], 0.94), dp(12))
        # point pêche cerclé d'encre le jour (la pêche seule ne se voit pas sur le lin), plein la nuit
        self.symbole = Symbole(MARQUE, SIGNAL, MARQUE if widgets.theme == "jour" else SIGNAL,
                               size_hint=(None, None), size=(dp(36), dp(36)))
        marque.add_widget(self.symbole)
        marque.add_widget(lab("Loopy", 27, gras=True, chiffres=True))
        carte.add_widget(marque)
        haut = BoxLayout(size_hint=(None, None), size=(dp(212), dp(44)), spacing=dp(8),
                         pos_hint={"right": 0.97, "top": 0.97})
        haut.add_widget(Bouton("Jour" if widgets.theme == "nuit" else "Nuit", lambda *_: app.changer_theme(), "carte", 44,
                               16, size_hint_x=0.7))
        haut.add_widget(Bouton("Historique", lambda *_: app.aller("profil"), "carte", 44, 16))
        carte.add_widget(haut)
        col.add_widget(carte)

        # les réglages, à portée de pouce
        panneau = BoxLayout(orientation="vertical", size_hint_y=None, padding=[dp(20), dp(12), dp(20), dp(18)],
                            spacing=dp(8))
        fond(panneau, FOND)
        self.info = lab("Chargement de la carte…", 19, gras=True, size_hint_y=None, height=dp(30))
        self.l_gps = lab("", 14, BRUME, size_hint_y=None, height=dp(22))
        self.km = Pas("Distance", "km", 5, 0.5, 1, 40, decimales=1)
        self.champ_dplus = Pas("Dénivelé", "m D+", 80, 10, 0, 750)
        self.km.bind(valeur=lambda w, v: self.champ_dplus.borner(maxi=int(v * 150 // 10 * 10)))
        self.pref = Segmente((("route", "Route"), ("hybride", "Mixte"), ("trail", "Trail")), "hybride")
        self.sel_depart = Segmente(((MA_POSITION, "De ma position"), (SUR_LA_CARTE, "D'un point choisi")),
                                   MA_POSITION)
        self.sel_depart.bind(choix=self.changer_depart)
        self.bas = BoxLayout(size_hint_y=None, height=dp(72), spacing=dp(10))
        self.btn_generer = Bouton("Générer une boucle", self.generer, "encre", 72, 20)
        self.btn_partir = Bouton("Partir", self.demarrer, "signal", 72, 22, size_hint_x=0)
        self.bas.add_widget(self.btn_generer)
        for w in (self.info, self.l_gps, self.km, self.champ_dplus, self.pref, self.sel_depart,
                  BoxLayout(size_hint_y=None, height=dp(4)), self.bas):
            panneau.add_widget(w)
        panneau.height = sum(w.height for w in panneau.children) + dp(8) * 7 + dp(30)
        col.add_widget(panneau)
        self.add_widget(col)

    def on_enter(self, *_):
        if not self.app.logo_vu:  # une fois par lancement : la boucle du logo se trace
            self.app.logo_vu = True
            self.symbole.animer()

    def carte_prete(self):
        self.km.borner(maxi=self.app.carte.distance_max // 500 / 2)
        self.info.text = "Règle ta sortie, puis génère une boucle"

    def etat_gps(self, texte):
        self.l_gps.text = texte

    def position(self, lat, lon, cap):
        self.trace.cap = cap
        self.trace.moi = [lat, lon]

    def boucle_prete(self, prete, animer=True):
        """Une boucle affichée : « Partir » s'ouvre en glissant depuis la droite et devient l'action
        principale ; « Générer » se resserre et passe au second plan. Et l'inverse."""
        b, g = self.btn_partir, self.btn_generer
        if prete == (b.parent is not None):
            return
        if prete:
            self.bas.add_widget(b)
            g.text, g.style = "Autre boucle", "contour"
        else:
            g.text, g.style = "Générer une boucle", "encre"
        for w, cible in ((b, 1 if prete else 0), (g, 0.8 if prete else 1)):
            Animation.cancel_all(w, "size_hint_x")
            if animer:
                Animation(size_hint_x=cible, d=0.34, t="out_cubic").start(w)
            else:
                w.size_hint_x = cible
        if not prete:
            Clock.schedule_once(lambda dt: b.parent and b.size_hint_x < 0.01 and self.bas.remove_widget(b),
                                0.36 if animer else 0)

    def changer_depart(self, _, valeur):
        choisir = valeur == SUR_LA_CARTE
        self.trace.choix = self.point_choisi if choisir else None
        if choisir:  # vue d'ensemble de la zone, pour pouvoir toucher la carte
            self.res = None
            self.trace.coords = []
            self.boucle_prete(False)
            self.info.text = "Touche la carte pour placer ton départ"
        else:
            self.depart_choisi = None
            self.trace.depart = []

    def point_choisi(self, lat, lon):
        self.depart_choisi = (lat, lon)
        self.trace.depart = [lat, lon]
        self.info.text = "Départ placé : génère ta boucle"

    def point_depart(self):
        """Renvoie (noeud de départ, message) : le point choisi, ou la position du téléphone."""
        carte = self.app.carte
        if self.sel_depart.choix == SUR_LA_CARTE:
            pt, hors = self.depart_choisi, "Ce point est hors de la zone embarquée"
            if pt is None:
                return None, "Touche la carte pour placer ton départ"
        else:
            pt, hors = self.app.gps_pos, "Tu es hors de la zone embarquée"
            if pt is None:
                return carte.depart, "Pas de GPS : départ au centre de la zone"
        if not carte.dans_zone(*pt):
            return carte.depart, hors + " : départ au centre"
        return carte.plus_proche(*pt), ""

    def generer(self, *_):
        if not self.app.carte or self.calcul:
            return
        params, erreur = lire_parametres(self.km.text, self.champ_dplus.text, self.app.carte.distance_max)
        if erreur:
            self.info.text = erreur
            return
        dep, self.note = self.point_depart()
        if dep is None:
            self.info.text = self.note
            return
        self.calcul, self.btn_generer.disabled, self.btn_partir.disabled = True, True, True
        self.info.text = "Recherche d'une boucle…"
        threading.Thread(target=self._calcul, args=(*params, self.pref.choix, dep), daemon=True).start()

    def _calcul(self, dist, d_plus, pref, dep):
        try:
            res = self.app.carte.generer(dist, d_plus, pref, dep)
        except Exception as err:  # ne jamais laisser le bouton bloqué
            res = None
            print(f"Génération : {err}")
        Clock.schedule_once(lambda dt: self.afficher(res))

    def afficher(self, res, animer=True):
        self.calcul, self.btn_generer.disabled, self.btn_partir.disabled = False, False, False
        if not res:
            self.info.text = "Aucune boucle trouvée : change la distance ou le D+"
            apparaitre(self.info)
            return
        self.res = res
        if animer:
            self.trace.tracer(res["coords"])
        else:
            self.trace.coords = res["coords"]
        self.boucle_prete(True, animer)
        self.info.text = f"Boucle de {nombre(res['distance'] / 1000)} km, {res['denivele']:.0f} m de D+"
        if animer:
            apparaitre(self.info)
        if self.note:
            self.l_gps.text = self.note

    def demarrer(self, *_):
        if not self.res:
            self.info.text = "Génère d'abord une boucle"
            return
        if platform == "android":
            if not self.app.gps_pos or self.app.gps_age > 30:
                self.info.text = "Attends le signal GPS avant de partir"
                return
            if self.app.gps_prec and self.app.gps_prec > 30:
                self.info.text = f"GPS encore imprécis ({self.app.gps_prec:.0f} m) : attends un peu"
                return
        self.app.ecran_course.preparer(self.res)
