"""Starva (Kivy) : boucles de course générées hors-ligne, suivi façon Strava, export GPX.
Voir README.md pour préparer les données, lancer sur PC et construire l'APK."""
import os, threading

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.screenmanager import ScreenManager
from kivy.utils import platform

from capteurs.partage import exporter
from core import Carte
from geo import Cap
from journal import Journal
from stockage import Stockage
from ui.ecran_course import EcranCourse
from ui.ecran_plan import EcranPlan
from ui.ecran_profil import EcranDetail, EcranProfil
from ui.widgets import FOND

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.db")


class StarvaApp(App):
    def build(self):
        Window.clearcolor = FOND
        self.carte, self.gps_pos, self.gps_prec, self.gps_age, self.cap = None, None, None, 0, Cap()
        self.stockage = Stockage(os.path.join(self.user_data_dir, "activites"),
                                 ancien_profil=os.path.join(self.user_data_dir, "profil.json"))
        self.chemin_journal = os.path.join(self.user_data_dir, "course_en_cours.db")
        self.journal = Journal(self.chemin_journal)
        self.sm = ScreenManager()
        self.ecran_plan, self.ecran_course = EcranPlan(self), EcranCourse(self)
        self.ecran_profil, self.ecran_detail = EcranProfil(self), EcranDetail(self)
        for e in (self.ecran_plan, self.ecran_course, self.ecran_profil, self.ecran_detail):
            self.sm.add_widget(e)
        threading.Thread(target=self._charger, daemon=True).start()
        return self.sm

    def on_start(self):
        if platform == "android":
            from capteurs.gps import Gps
            self.gps = Gps(self.position_telephone, self.ecran_plan.etat_gps)
            self.gps.demander()
        else:
            self.ecran_plan.etat_gps("PC : position simulée pendant la course (touche D : détour)")

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
        for e in (self.ecran_plan, self.ecran_course, self.ecran_detail):
            e.trace.reseau = reseau
            e.trace.zone = zone
        self.ecran_plan.carte_prete()
        self.ecran_course.verifier_reprise()

    def position_telephone(self, lat, lon, precision=None, age=0):
        """Position vue par l'app (écran de préparation). Pendant une course, c'est le journal qui compte."""
        self.gps_pos, self.gps_prec, self.gps_age = (lat, lon), precision, age
        self.ecran_plan.position(lat, lon, self.cap.maj((lat, lon)))
        if age > 30:
            self.ecran_plan.etat_gps(f"GPS : dernière position connue (il y a {age / 60:.0f} min). "
                                     "Va dehors pour un signal frais")
        else:
            self.ecran_plan.etat_gps("GPS : ok" + (f" (précision {precision:.0f} m)" if precision else ""))

    def exporter_gpx(self, nom, texte):
        return exporter(nom, texte, os.path.join(self.user_data_dir, "exports"))


if __name__ == "__main__":
    StarvaApp().run()
