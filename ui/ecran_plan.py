"""Écran 1 : préparer la boucle (distance, D+, terrain, départ) et la générer."""
import threading

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import Screen
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.utils import platform

from ui.carte import Trace, avec_zoom
from ui.widgets import ARDOISE, BLANC, GRIS, bouton, lab

MA_POSITION, SUR_LA_CARTE = "Ma position", "Choisir sur la carte"


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
        col = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        titres = BoxLayout(size_hint_y=None, height=dp(22), spacing=dp(8))
        for t in ("Distance (km)", "Dénivelé + (m)", "Terrain"):
            titres.add_widget(lab(t, 13, GRIS))
        ligne = BoxLayout(size_hint_y=None, height=dp(64), spacing=dp(8))
        champ = dict(font_size="26sp", multiline=False, padding=[dp(14), dp(16), dp(14), dp(8)],
                     background_color=(0.16, 0.18, 0.20, 1), foreground_color=BLANC)
        self.km = TextInput(text="5", input_filter="float", **champ)
        self.champ_dplus = TextInput(text="80", input_filter="int", **champ)
        self.pref = Spinner(text="hybride", values=("hybride", "trail", "route"), font_size="20sp",
                            background_normal="", background_color=ARDOISE)
        for w in (self.km, self.champ_dplus, self.pref):
            ligne.add_widget(w)
        self.sel_depart = Spinner(text=MA_POSITION, values=(MA_POSITION, SUR_LA_CARTE),
                                  font_size="20sp", size_hint_y=None, height=dp(56),
                                  background_normal="", background_color=ARDOISE)
        self.sel_depart.bind(text=self.changer_depart)
        self.btn_generer = bouton("Générer la boucle", self.generer)
        self.info = lab("Chargement de la carte…", 18, size_hint_y=None, height=dp(52))
        self.l_gps = lab("", 14, GRIS, size_hint_y=None, height=dp(44))
        self.trace = Trace()
        bas = BoxLayout(size_hint_y=None, height=dp(64), spacing=dp(8))
        bas.add_widget(bouton("Démarrer la course", self.demarrer))
        bas.add_widget(bouton("Mon profil", lambda *_: setattr(app.sm, "current", "profil"),
                              ARDOISE, BLANC))
        for w in (titres, ligne, self.sel_depart, self.btn_generer, self.info, self.l_gps,
                  avec_zoom(self.trace), bas):
            col.add_widget(w)
        self.add_widget(col)

    def carte_prete(self):
        self.info.text = "Carte prête"

    def etat_gps(self, texte):
        self.l_gps.text = texte

    def position(self, lat, lon, cap):
        self.trace.cap = cap
        self.trace.moi = [lat, lon]

    def changer_depart(self, _, texte):
        choisir = texte == SUR_LA_CARTE
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
        carte = self.app.carte
        if self.sel_depart.text == SUR_LA_CARTE:
            pt, hors = self.depart_choisi, "Ce point est hors de la zone embarquée"
            if pt is None:
                return None, "Touche la carte pour choisir ton départ"
        else:
            pt, hors = self.app.gps_pos, "Tu es hors de la zone embarquée"
            if pt is None:
                return carte.depart, "pas de GPS : départ au centre de la zone"
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
        self.calcul, self.btn_generer.disabled = True, True
        self.info.text = "Calcul en cours…"
        threading.Thread(target=self._calcul, args=(*params, self.pref.text, dep), daemon=True).start()

    def _calcul(self, dist, d_plus, pref, dep):
        try:
            res = self.app.carte.generer(dist, d_plus, pref, dep)
        except Exception as err:  # ne jamais laisser le bouton bloqué
            res = None
            print(f"Génération : {err}")
        Clock.schedule_once(lambda dt: self.afficher(res))

    def afficher(self, res):
        self.calcul, self.btn_generer.disabled = False, False
        if not res:
            self.info.text = "Aucune boucle trouvée : change la distance ou le D+"
            return
        self.res = res
        self.trace.coords = res["coords"]
        txt = f"{res['distance'] / 1000:.1f} km   D+ {res['denivele']:.0f} m"
        self.info.text = txt + (f"\n({self.note})" if self.note else "")

    def demarrer(self, *_):
        if not self.res:
            self.info.text = "Génère d'abord une boucle"
            return
        if platform == "android":
            if not self.app.gps_pos or self.app.gps_age > 30:
                self.info.text = "En attendant le signal GPS, ne pars pas encore (voir l'état GPS)"
                return
            if self.app.gps_prec and self.app.gps_prec > 30:
                self.info.text = f"GPS encore imprécis ({self.app.gps_prec:.0f} m) : attends un peu"
                return
        self.app.ecran_course.preparer(self.res)
