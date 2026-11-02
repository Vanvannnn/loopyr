"""Loopy (Kivy) : boucles de course générées hors-ligne, suivi de la course, export GPX.
Voir README.md pour préparer les données, lancer sur PC et construire l'APK."""
import os, threading, time

from kivy.animation import Animation, AnimationTransition
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.screenmanager import ScreenManager, SlideTransition
from kivy.utils import platform

from capteurs.partage import exporter
from core import Carte
from geo import Cap
from journal import Journal
from stockage import Stockage, ecrire_json, lire_json
from ui import widgets

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.db")
# sens des transitions : on avance vers la gauche, on revient vers la droite, la course monte
SENS = {"avant": "left", "retour": "right", "monter": "up", "descendre": "down"}


class Glisse(SlideTransition):
    """Glissement d'écran avec une vraie décélération (celui de Kivy avance à vitesse constante)."""

    def on_progress(self, p):
        super().on_progress(AnimationTransition.out_cubic(p))


def theme_systeme():
    """Nuit si le téléphone est en mode sombre ; sur PC, nuit entre 20 h et 7 h."""
    if platform == "android":
        try:
            from capteurs.android import activite
            return "nuit" if activite().getResources().getConfiguration().uiMode & 0x30 == 0x20 else "jour"
        except Exception:
            pass
    return "nuit" if not 7 <= time.localtime().tm_hour < 20 else "jour"


class StarvaApp(App):  # nom de classe gardé : il fixe le dossier des données sur PC
    title = "Loopy"

    def build(self):
        self.carte, self.gps_pos, self.gps_prec, self.gps_age, self.cap = None, None, None, 0, Cap()
        self.reseau = self.zone = None
        self.logo_vu, self.theme_en_cours = False, False  # la boucle du logo se trace une fois, à l'ouverture
        self.stockage = Stockage(os.path.join(self.user_data_dir, "activites"),
                                 ancien_profil=os.path.join(self.user_data_dir, "profil.json"))
        self.chemin_journal = os.path.join(self.user_data_dir, "course_en_cours.db")
        self.chemin_reglages = os.path.join(self.user_data_dir, "reglages.json")
        self.journal = Journal(self.chemin_journal)
        self.sm = ScreenManager(transition=Glisse(duration=0.34))
        try:
            theme = lire_json(self.chemin_reglages)["theme"]
        except (OSError, ValueError, KeyError):
            theme = theme_systeme()  # pas encore de choix : on suit le téléphone
        self.creer_ecrans(theme if theme in widgets.THEMES else "jour")
        threading.Thread(target=self._charger, daemon=True).start()
        return self.sm

    def creer_ecrans(self, theme):
        """(Re)construit les écrans dans le thème voulu : les couleurs sont lues à la construction."""
        from ui.ecran_course import EcranCourse
        from ui.ecran_plan import EcranPlan
        from ui.ecran_profil import EcranDetail, EcranProfil
        widgets.appliquer_theme(theme)
        Window.clearcolor = widgets.FOND
        self.sm.clear_widgets()
        self.ecran_plan, self.ecran_course = EcranPlan(self), EcranCourse(self)
        self.ecran_profil, self.ecran_detail = EcranProfil(self), EcranDetail(self)
        for e in (self.ecran_plan, self.ecran_course, self.ecran_profil, self.ecran_detail):
            self.sm.add_widget(e)
        if self.reseau:
            self.brancher_carte()

    def changer_theme(self):
        """Jour <-> nuit, depuis l'accueil : l'écran s'efface, est reconstruit, puis revient en fondu.
        La boucle affichée et l'état du GPS sont gardés."""
        if self.sm.current != "plan" or self.ecran_plan.calcul or self.theme_en_cours:
            return
        self.theme_en_cours = True
        theme = "nuit" if widgets.theme == "jour" else "jour"
        ecrire_json(self.chemin_reglages, {"theme": theme})
        a = Animation(opacity=0, d=0.15, t="in_quad")
        a.bind(on_complete=lambda *_: self._rebatir(theme))
        a.start(self.sm)

    def _rebatir(self, theme):
        res, etat_gps = self.ecran_plan.res, self.ecran_plan.l_gps.text
        self.creer_ecrans(theme)
        self.ecran_plan.etat_gps(etat_gps)
        if res:
            self.ecran_plan.afficher(res, animer=False)
        if self.gps_pos:
            self.ecran_plan.position(*self.gps_pos, self.cap.maj(self.gps_pos))
        Animation(opacity=1, d=0.3, t="out_quad").start(self.sm)
        self.theme_en_cours = False

    def aller(self, ecran, sens="avant"):
        self.sm.transition.direction = SENS[sens]
        self.sm.current = ecran

    def on_start(self):
        if platform == "android":
            from capteurs.gps import Gps
            self.gps = Gps(self.position_telephone, lambda texte: self.ecran_plan.etat_gps(texte))
            self.gps.demander()
        else:
            self.ecran_plan.etat_gps("Sur PC, la course est simulée (touche D : faire un détour)")

    def on_pause(self):
        return True  # la course continue dans le service GPS ; on relit le journal au retour

    def _charger(self):
        self.carte = Carte(DB)
        reseau = {0: [], 1: []}
        for t, pts in self.carte.segments():
            reseau[t].append(pts)
        lats = [n[0] for n in self.carte.nodes.values()]
        lons = [n[1] for n in self.carte.nodes.values()]
        zone = [(min(lats), min(lons)), (max(lats), max(lons))]
        Clock.schedule_once(lambda dt: self.carte_prete(reseau, zone))

    def carte_prete(self, reseau, zone):
        self.reseau, self.zone = reseau, zone
        self.brancher_carte()
        self.ecran_course.verifier_reprise()

    def brancher_carte(self):
        for e in (self.ecran_plan, self.ecran_course, self.ecran_detail):
            e.trace.reseau = self.reseau
            e.trace.zone = self.zone
        self.ecran_plan.carte_prete()

    def position_telephone(self, lat, lon, precision=None, age=0):
        """Position vue par l'app (écran de préparation). Pendant une course, c'est le journal qui compte."""
        self.gps_pos, self.gps_prec, self.gps_age = (lat, lon), precision, age
        self.ecran_plan.position(lat, lon, self.cap.maj((lat, lon)))
        if age > 30:
            self.ecran_plan.etat_gps(f"Position d'il y a {age / 60:.0f} min : sors pour capter le GPS")
        else:
            self.ecran_plan.etat_gps("GPS capté" + (f", à {precision:.0f} m près" if precision else ""))

    def exporter_gpx(self, nom, texte):
        return exporter(nom, texte, os.path.join(self.user_data_dir, "exports"))


if __name__ == "__main__":
    StarvaApp().run()
