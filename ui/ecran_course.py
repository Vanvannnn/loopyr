"""Écran 2 : la course. Tout passe par le journal (journal.py) : le service GPS (ou le simulateur
sur PC) y écrit les positions, cet écran le relit toutes les 0,5 s pour afficher la course."""
import time

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.utils import platform

from annonces import Annonceur
from capteurs.voix import Voix
from course import fmt_allure, fmt_temps
from geo import Cap, ecart
from journal import appliquer
from progression import Progression
from ui.carte import Trace, avec_zoom
from ui.widgets import ARDOISE, BLANC, CORAIL, FOND, GRIS, MINT, bouton, choix, confirmer, lab

ORIENTS = {"marche": "Cap : marche", "boussole": "Cap : boussole", "nord": "Cap : nord"}


def texte_splits(splits):
    return "\n".join(f"km {i}   {fmt_allure(1000 / s)} /km" for i, s in enumerate(splits, 1) if s > 0)


class EcranCourse(Screen):
    def __init__(self, app, **kw):
        super().__init__(name="course", **kw)
        self.app, self.course, self.prog, self.res = app, None, None, None
        self.dernier_evt, self.annonceur, self.sim, self.fini, self.voix_on = 0, None, None, False, True
        self.boussole, self.az, self.btn_cap = None, None, None
        self.voix = Voix(None if platform != "android" else self._activite())

        racine = FloatLayout()
        col = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(6))
        self.trace = Trace(suivi=True)
        carte = avec_zoom(self.trace, self.changer_orient)
        self.btn_voix = Button(text="Voix : oui", font_size="15sp", size_hint=(None, None),
                               size=(dp(120), dp(48)), pos_hint={"right": 0.98, "top": 0.98},
                               background_normal="", background_color=(0.12, 0.14, 0.16, 0.9),
                               on_release=self.changer_voix)
        carte.add_widget(self.btn_voix)
        self.l_dist = lab("0.00", 72, MINT, True, size_hint_y=None, height=dp(88))
        self.l_prevu = lab("", 16, GRIS, size_hint_y=None, height=dp(26))
        self.l_temps = lab("00:00:00", 40, gras=True, size_hint_y=None, height=dp(54))
        cases = BoxLayout(size_hint_y=None, height=dp(76), spacing=dp(8))
        self.l_allure, self.l_vitesse, self.l_dplus = lab("--:--", 32, gras=True), lab("0.0", 32, gras=True), \
            lab("0", 32, gras=True)
        for val, unite in ((self.l_allure, "min/km"), (self.l_vitesse, "km/h"), (self.l_dplus, "m D+")):
            c = BoxLayout(orientation="vertical")
            c.add_widget(val)
            c.add_widget(lab(unite, 15, GRIS, size_hint_y=None, height=dp(22)))
            cases.add_widget(c)
        boutons = BoxLayout(size_hint_y=None, height=dp(64), spacing=dp(8))
        self.btn_pause = bouton("Pause", self.pause_reprise, ARDOISE, BLANC)
        boutons.add_widget(self.btn_pause)
        boutons.add_widget(bouton("Terminer", self.terminer, CORAIL, BLANC))
        panneau = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(340), spacing=dp(2))
        with panneau.canvas.before:  # fond plein : la carte ne peut pas passer sous les chiffres
            Color(*FOND)
            fond = Rectangle(pos=panneau.pos, size=panneau.size)
        panneau.bind(pos=lambda w, v: setattr(fond, "pos", v), size=lambda w, v: setattr(fond, "size", v))
        for w in (self.l_dist, self.l_prevu, self.l_temps, cases, boutons):
            panneau.add_widget(w)
        col.add_widget(carte)
        col.add_widget(panneau)
        racine.add_widget(col)
        self.decompte = lab("", 160, MINT, True, size_hint=(1, 1), opacity=0)  # 3, 2, 1 par-dessus
        racine.add_widget(self.decompte)
        self.add_widget(racine)

    @staticmethod
    def _activite():
        from capteurs.android import activite
        return activite()

    @property
    def journal(self):
        return self.app.journal

    # --- départ ---
    def preparer(self, res):
        """Depuis l'écran de préparation : affiche la boucle, compte 3-2-1 puis lance la course."""
        self.journal.vider()
        self.journal.poser("boucle", res)
        self.journal.poser("voix", self.voix_on)
        self.afficher_boucle(res)
        self.app.sm.current = "course"
        self.voix.preparer()
        self.n = 3
        self.decompte.opacity, self.decompte.text = 1, "3"
        self.voix.dire("3")
        Clock.schedule_interval(self._decompter, 1)

    def _decompter(self, dt):
        self.n -= 1
        if self.n > 0:
            self.decompte.text = str(self.n)
            self.voix.dire(str(self.n))
            return True
        self.decompte.opacity = 0
        self.voix.dire("C'est parti")
        self.journal.ecrire("debut", time.time())
        self.lancer_enregistrement()
        self.suivre()
        return False

    def afficher_boucle(self, res):
        self.res, self.fini = res, False
        self.course, self.dernier_evt, self.cap = None, 0, Cap()
        self.prog = Progression(res["coords"])
        self.trace.coords = res["coords"]
        self.trace.fait, self.trace.boucle_faite, self.trace.moi = [], [], []
        self.l_prevu.text, self.l_prevu.color = f"{self.prog.total / 1000:.1f} km prévus", GRIS
        self.btn_pause.text = "Pause"
        Window.allow_screensaver = False  # écran allumé pendant la course

    def lancer_enregistrement(self):
        """Démarre (ou relance) ce qui écrit les positions dans le journal."""
        if platform == "android":
            from capteurs.gps import demarrer_service
            demarrer_service(self.app.chemin_journal)  # sans effet s'il tourne déjà
        else:
            from capteurs.simulateur import Simulateur
            self.sim = Simulateur(self.journal, self.res["coords"])
            self.sim.demarrer()
            # sur Android, c'est le service qui annonce (même écran éteint)
            self.annonceur = Annonceur(self.res["coords"], self.voix.dire, self.voix.vibrer, lambda: self.voix_on)

    def suivre(self):
        Clock.unschedule(self.lire_journal)
        Clock.schedule_interval(self.lire_journal, 0.5)
        self.lire_journal(0)

    def arreter_enregistrement(self):
        Clock.unschedule(self.lire_journal)
        if self.sim:
            self.sim.arreter()
            self.sim = None
        elif platform == "android":
            from capteurs.gps import arreter_service
            arreter_service()
        self.annonceur = None

    # --- pendant la course ---
    def lire_journal(self, dt):
        dernier_point = None
        for e in self.journal.lire(apres=self.dernier_evt):
            self.dernier_evt = e[0]
            self.course = appliquer(self.course, e, self.app.carte.altitude if self.app.carte else None)
            if self.annonceur:
                self.annonceur.traiter(e)
            if e[1] == "point" and self.course and not self.course.en_pause:
                self.prog.maj(e[3], e[4], e[2])
                dernier_point = (e[3], e[4])
        if dernier_point:
            self.trace.cap = self.cap.maj(dernier_point)
            self.trace.fait = self.course.trace
            self.trace.boucle_faite = self.prog.partie_faite()
            self.trace.moi = list(dernier_point)
        if self.course:
            self.maj_stats()

    def maj_stats(self):
        c, v = self.course, self.course.vitesse()
        self.l_dist.text = f"{c.dist / 1000:.2f}[size=26sp] km[/size]"
        self.l_temps.text = fmt_temps(c.duree()) + ("  [size=20sp]EN PAUSE[/size]" if c.en_pause else "")
        self.l_temps.color = GRIS if c.en_pause else BLANC
        self.l_allure.text = fmt_allure(v)
        self.l_vitesse.text = f"{v * 3.6:.1f}"
        self.l_dplus.text = f"{c.dplus:.0f}"
        self.btn_pause.text = "Reprendre" if c.en_pause else "Pause"
        p = self.prog
        if p.hors_trace:
            self.l_prevu.text, self.l_prevu.color = f"Hors du parcours (à {p.ecart:.0f} m)", CORAIL
        else:
            self.l_prevu.text = f"{p.restant / 1000:.1f} km restants · {p.pourcent:.0f} %"
            self.l_prevu.color = GRIS

    def pause_reprise(self, *_):
        if not self.course or self.fini:
            return
        self.journal.ecrire("reprise" if self.course.en_pause else "pause", time.time())
        self.lire_journal(0)

    def changer_voix(self, *_):
        self.voix_on = not self.voix_on
        self.journal.poser("voix", self.voix_on)  # lu par le service
        self.btn_voix.text = "Voix : oui" if self.voix_on else "Voix : non"

    # --- fin ---
    def terminer(self, *_):
        if not self.course or self.fini:
            return
        self.fini = True
        self.journal.ecrire("fin", time.time())
        self.lire_journal(0)
        self.arreter_enregistrement()
        self.popup_fin()

    def popup_fin(self):
        c = self.course
        moy = fmt_allure(c.dist / c.duree()) if c.duree() else "--:--"
        boite = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))
        boite.add_widget(lab(f"{c.dist / 1000:.2f} km en {fmt_temps(c.duree())}\n"
                             f"allure moyenne {moy} min/km   D+ {c.dplus:.0f} m", 22,
                             size_hint_y=None, height=dp(80)))
        sv = ScrollView()
        splits = lab(texte_splits(c.splits) or "Pas encore de kilomètre complet", 18, GRIS, size_hint_y=None)
        splits.bind(texture_size=lambda l, s: setattr(l, "height", s[1]))
        sv.add_widget(splits)
        boite.add_widget(sv)
        ligne = BoxLayout(size_hint_y=None, height=dp(64), spacing=dp(8))
        pop = Popup(title="Course terminée", content=boite, size_hint=(0.92, 0.7),
                    auto_dismiss=False, title_size="20sp")
        ligne.add_widget(bouton("Enregistrer", lambda *_: self.fin_course(pop, True)))
        ligne.add_widget(bouton("Supprimer", lambda b: confirmer(b, "Sûr ?", lambda: self.fin_course(pop, False)),
                                ARDOISE, BLANC))
        boite.add_widget(ligne)
        pop.open()

    def fin_course(self, pop, garder):
        pop.dismiss()
        if garder and self.course.dist > 0:
            self.app.stockage.enregistrer(self.course.resume())
        self.journal.vider()
        self.course = None
        self.trace.fait, self.trace.boucle_faite = [], []
        if self.boussole:
            self.boussole.activer(False)
        Clock.unschedule(self.maj_boussole)
        self.trace.orient, self.trace.az = "marche", None
        if self.btn_cap:
            self.btn_cap.text = ORIENTS["marche"]
        Window.allow_screensaver = True
        self.app.sm.current = "plan"

    # --- après un crash : une course du journal n'est pas terminée ---
    def verifier_reprise(self):
        etat, res = self.journal.etat(), self.journal.lire_meta("boucle")
        if etat is None or not res:
            return
        self.voix_on = self.journal.lire_meta("voix") is not False
        self.btn_voix.text = "Voix : oui" if self.voix_on else "Voix : non"
        self.afficher_boucle(res)
        if etat == "fin":  # terminée mais pas encore enregistrée
            self.app.sm.current = "course"
            self.lire_journal(0)
            self.fini = True
            self.popup_fin()
            return

        def reprendre():
            self.app.sm.current = "course"
            self.lancer_enregistrement()
            self.suivre()

        def finir():
            self.app.sm.current = "course"
            self.lire_journal(0)
            self.terminer()

        choix("Course en cours", "Une course n'est pas terminée.\nLa reprendre ?",
              [("Reprendre", reprendre, MINT, (0.05, 0.10, 0.08, 1)), ("Terminer", finir, ARDOISE, BLANC)])

    # --- orientation de la carte ---
    def changer_orient(self, btn):
        self.btn_cap = btn
        suite = {"marche": "boussole", "boussole": "nord", "nord": "marche"}
        if platform != "android":  # pas de boussole sur PC
            suite = {"marche": "nord", "nord": "marche"}
        mode = suite[self.trace.orient]
        Clock.unschedule(self.maj_boussole)
        if mode == "boussole":
            from capteurs.boussole import Boussole
            self.boussole = self.boussole or Boussole()
            if self.boussole.activer(True):
                Clock.schedule_interval(self.maj_boussole, 0.1)
            else:
                self.l_prevu.text = self.boussole.erreur
                mode = "nord"
        elif self.boussole:
            self.boussole.activer(False)
        if mode != "boussole":
            self.az = self.trace.az = None
        self.trace.orient = mode
        btn.text = ORIENTS[mode]
        self.trace.dessiner()

    def maj_boussole(self, dt):
        brut = self.boussole.az_brut
        if brut is None:
            return
        self.az = brut if self.az is None else (self.az + 0.25 * ecart(self.az, brut)) % 360
        self.trace.az = self.az
        self.trace.maj_angle()
