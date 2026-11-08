"""Loopy (Kivy) : des boucles de vélo ou de course générées autour de ta position, partout dans le monde ;
le suivi de la sortie ; l'historique ; le compte, la communauté et Strava. Voir README.md."""
import os, threading, time

from kivy.animation import Animation, AnimationTransition
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import ScreenManager, SlideTransition
from kivy.utils import platform

from boucles import BRouter
from capteurs.partage import exporter
from compte import Compte, ErreurCompte
from geo import Cap
from journal import Journal
from stockage import RESUME_ITINERAIRE, Stockage, ecrire_json, lire_json
from ui import widgets

SENS = {"avant": "left", "retour": "right", "monter": "up", "descendre": "down"}
# PC : le serveur lancé à côté (uvicorn) ; téléphone : l'adresse se règle dans Profil
SERVEUR_DEFAUT = os.environ.get("LOOPY_SERVEUR", "" if platform == "android" else "http://localhost:8000")


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
        from ui.carte import Tuiles
        self.gps_pos, self.gps_prec, self.gps_age, self.cap = None, None, 0, Cap()
        self.logo_vu, self.theme_en_cours, self.gps = False, False, None
        self.chemin_reglages = os.path.join(self.user_data_dir, "reglages.json")
        try:
            self.reglages = lire_json(self.chemin_reglages)
        except (OSError, ValueError):
            self.reglages = {}
        self.moteur = BRouter(self.reglages.get("moteur"))
        self.compte = Compte(self.reglages.get("serveur", SERVEUR_DEFAUT), self.reglages.get("jeton"))
        self.stockage = Stockage(os.path.join(self.user_data_dir, "activites"),
                                 ancien_profil=os.path.join(self.user_data_dir, "profil.json"))
        self.itineraires = Stockage(os.path.join(self.user_data_dir, "itineraires"), champs=RESUME_ITINERAIRE, tri="cree")
        Tuiles.dossier = os.path.join(self.user_data_dir, "tuiles")
        self.chemin_journal = os.path.join(self.user_data_dir, "course_en_cours.db")
        self.journal = Journal(self.chemin_journal)
        self.creation = {"sport": None, "distance": None, "relief": None, "mode": "gps", "point": None}
        self.racine = BoxLayout(orientation="vertical")
        self.sm = ScreenManager(transition=Glisse(duration=0.34))
        theme = self.reglages.get("theme")
        self.creer_ecrans(theme if theme in widgets.THEMES else theme_systeme())  # pas de choix : on suit le téléphone
        return self.racine

    def creer_ecrans(self, theme):
        """(Re)construit les écrans dans le thème voulu : les couleurs sont lues à la construction."""
        from ui.ecran_accueil import EcranAccueil, EcranDistance, EcranSport
        from ui.ecran_compte import EcranCommunaute, EcranProfil
        from ui.ecran_course import EcranCourse
        from ui.ecran_plan import EcranPlan
        from ui.ecran_profil import EcranDetail, EcranHistorique
        widgets.appliquer_theme(theme)
        Window.clearcolor = widgets.FOND
        self.sm.clear_widgets()
        self.racine.clear_widgets()
        self.ecran_accueil, self.ecran_sport, self.ecran_distance = EcranAccueil(self), EcranSport(self), EcranDistance(self)
        self.ecran_plan, self.ecran_course = EcranPlan(self), EcranCourse(self)
        self.ecran_historique, self.ecran_detail = EcranHistorique(self), EcranDetail(self)
        self.ecran_profil, self.ecran_communaute = EcranProfil(self), EcranCommunaute(self)
        for e in (self.ecran_accueil, self.ecran_sport, self.ecran_distance, self.ecran_plan, self.ecran_course,
                  self.ecran_historique, self.ecran_detail, self.ecran_profil, self.ecran_communaute):
            self.sm.add_widget(e)
        self.nav = widgets.Nav(lambda n: self.aller(n, "avant"))
        self.racine.add_widget(self.sm)
        self.racine.add_widget(self.nav)
        self.nav.montrer("accueil")
        pos = self.gps_pos or self.derniere_position()
        if pos:
            self.ecran_accueil.trace.centre = list(pos)

    def changer_theme(self):
        """Jour <-> nuit : l'écran s'efface, est reconstruit, puis revient en fondu, sur le même écran."""
        if self.sm.current == "course" or self.ecran_plan.calcul or self.theme_en_cours:
            return
        self.theme_en_cours = True
        theme = "nuit" if widgets.theme == "jour" else "jour"
        self.sauver_reglages(theme=theme)
        ecran = self.sm.current
        a = Animation(opacity=0, d=0.15, t="in_quad")
        a.bind(on_complete=lambda *_: self._rebatir(theme, ecran))
        a.start(self.racine)

    def _rebatir(self, theme, ecran):
        etat_gps = self.ecran_accueil.l_gps.text
        self.creer_ecrans(theme)
        self.ecran_accueil.etat_gps(etat_gps)
        if self.gps_pos:
            self.ecran_accueil.position(*self.gps_pos, self.cap.maj(self.gps_pos))
        self.sm.transition.duration = 0
        self.aller(ecran if ecran in ("accueil", "profil", "historique", "communaute") else "accueil")
        self.sm.transition.duration = 0.34
        Animation(opacity=1, d=0.3, t="out_quad").start(self.racine)
        self.theme_en_cours = False

    def aller(self, ecran, sens="avant"):
        if ecran == self.sm.current:
            return
        self.sm.transition.direction = SENS[sens]
        self.sm.current = ecran
        self.nav.montrer(ecran)
        en_course = ecran == "course"  # pendant une sortie, toute la place va à la carte et aux chiffres
        self.nav.opacity, self.nav.disabled = (0, True) if en_course else (1, False)
        self.nav.height = 0 if en_course else widgets.dp(62)

    # --- réglages ---
    def sauver_reglages(self, **valeurs):
        self.reglages.update(valeurs)
        ecrire_json(self.chemin_reglages, self.reglages)

    def derniere_position(self):
        p = self.reglages.get("position")
        return tuple(p) if p else None

    # --- position ---
    def on_start(self):
        if platform == "android":
            self.actualiser_position()
        else:
            self.ecran_accueil.etat_gps("Sur PC, pas de GPS : choisis un point de départ ou cherche un lieu. "
                                        "La sortie est simulée (touche D : détour).")
        self.ecran_course.verifier_reprise()
        self.synchroniser_tout()

    def actualiser_position(self):
        if platform != "android":
            self.ecran_accueil.etat_gps("Sur PC, pas de GPS : choisis le départ sur la carte ou cherche un lieu.")
            return
        from capteurs.gps import Gps
        if self.gps is None:
            self.gps = Gps(self.position_telephone, lambda texte: self.ecran_accueil.etat_gps(texte))
            self.gps.demander()
        else:  # relance l'écoute : utile après avoir accordé l'autorisation dans les réglages
            self.gps.demarre = False
            self.gps.demander()

    def on_pause(self):
        if self.gps_pos:
            self.sauver_reglages(position=list(self.gps_pos))
        return True  # la course continue dans le service GPS ; on relit le journal au retour

    def on_stop(self):
        if self.gps_pos:
            self.sauver_reglages(position=list(self.gps_pos))

    def position_telephone(self, lat, lon, precision=None, age=0):
        """Position vue par l'app. Pendant une course, c'est le journal (service GPS) qui compte."""
        premiere = self.gps_pos is None
        self.gps_pos, self.gps_prec, self.gps_age = (lat, lon), precision, age
        self.ecran_accueil.position(lat, lon, self.cap.maj((lat, lon)))
        if premiere:
            self.ecran_accueil.trace.centre = [lat, lon]
            self.sauver_reglages(position=[lat, lon])
        if age > 30:
            self.ecran_accueil.etat_gps(f"Position d'il y a {age / 60:.0f} min : sors pour capter le GPS")
        else:
            self.ecran_accueil.etat_gps("GPS capté" + (f", à {precision:.0f} m près" if precision else ""))

    def exporter_gpx(self, nom, texte):
        return exporter(nom, texte, os.path.join(self.user_data_dir, "exports"))

    # --- synchronisation avec le compte (en arrière-plan ; tout reste local si elle échoue) ---
    def _fond(self, travail):
        if self.compte.connecte:
            threading.Thread(target=travail, daemon=True).start()

    def synchroniser_activite(self, act):
        def travail():
            try:
                r = self.compte.envoyer_activite(act)
                Clock.schedule_once(lambda dt: self._marquer(self.stockage, act["id"], r["id"]))
            except ErreurCompte:
                pass  # renvoyée au prochain lancement
        self._fond(travail)

    def synchroniser_itineraire(self, it):
        def travail():
            try:
                if it.get("id_serveur"):
                    self.compte.modifier_itineraire(it["id_serveur"], favori=bool(it.get("favori")), nom=it["nom"])
                else:
                    r = self.compte.enregistrer_itineraire(it)
                    Clock.schedule_once(lambda dt: self._marquer(self.itineraires, it["id"], r["id"]))
            except ErreurCompte:
                pass
        self._fond(travail)

    def _marquer(self, stockage, id_, id_serveur):
        try:
            x = stockage.charger(id_)
        except (OSError, ValueError):
            return  # supprimé entre-temps
        x["id_serveur"] = id_serveur
        stockage.enregistrer(x)

    def synchroniser_tout(self):
        """Envoie ce qui ne l'a pas encore été (sorties faites hors connexion, boucles enregistrées)."""
        from gpx import exportable
        for a in self.stockage.lister():
            if not a.get("id_serveur"):
                act = self.stockage.charger(a["id"])
                if exportable(act):
                    self.synchroniser_activite(act)
        for i in self.itineraires.lister():
            if not i.get("id_serveur"):
                self.synchroniser_itineraire(self.itineraires.charger(i["id"]))


if __name__ == "__main__":
    StarvaApp().run()
