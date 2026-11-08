"""Écran 2 : la course. Tout passe par le journal (journal.py) : le service GPS (ou le simulateur
sur PC) y écrit les positions, cet écran le relit toutes les 0,5 s pour afficher la course."""
import time

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, Line
from kivy.metrics import dp
from kivy.properties import NumericProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.utils import platform

from annonces import Annonceur
from capteurs.voix import Voix
from course import fmt_allure
from geo import Altitudes, Cap, ecart
from journal import appliquer
from progression import Progression
from ui.carte import Trace, avec_zoom
from ui.widgets import (BRUME, ENCRE, FOND, FOND_2, SIGNAL, SUR_SIGNAL, TRACE, Bande, Bouton, Feuille, Splits, choix,
                        confirmer, echelle, fond, lab, nombre, pulser, unite)

ORIENTS = {"marche": "Sens de course", "boussole": "Boussole", "nord": "Nord en haut"}


def chrono(s):
    """24:13, ou 1:04:13 au-delà d'une heure."""
    s = int(s)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60:02d}:{s % 60:02d}"


class Decompte(FloatLayout):
    """3, 2, 1 en plein écran : chaque seconde, un anneau sauge fait le tour du chiffre en partant du
    point de départ, comme la boucle du logo. À la fin, l'écran s'efface en grandissant sur la carte."""
    arc = NumericProperty(0)

    def __init__(self, **kw):
        super().__init__(opacity=0, **kw)
        fond(self, FOND)
        self.chiffre = lab("", 200, gras=True, chiffres=True, aligne="center", size_hint=(1, 1))
        self.add_widget(self.chiffre)
        echelle(self.chiffre)
        with self.canvas.after:
            Color(*FOND_2)
            self._rail = Line(width=dp(7))
            Color(*TRACE)
            self._anneau = Line(width=dp(7), cap="round")
            Color(*SUR_SIGNAL)
            self._bord = Ellipse()
            Color(*SIGNAL)
            self._point = Ellipse()
        self.bind(pos=self._dessiner, size=self._dessiner, arc=self._dessiner)

    def _dessiner(self, *_):
        cx, cy, r = self.center_x, self.center_y, min(self.width, self.height) * 0.36
        self._rail.circle = (cx, cy, r)
        self._anneau.circle = (cx, cy, r, 0, max(0.1, self.arc))
        for e, rr in ((self._bord, dp(13)), (self._point, dp(10))):
            e.pos, e.size = (cx - rr, cy + r - rr), (2 * rr, 2 * rr)

    def montrer(self, texte):
        Animation.cancel_all(self)
        self.opacity, self.chiffre.text, self.arc = 1, texte, 0
        echelle(self).xyz = (1, 1, 1)
        sc = echelle(self.chiffre)
        sc.xyz, self.chiffre.opacity = (1.35, 1.35, 1), 0
        Animation(xyz=(1, 1, 1), d=0.35, t="out_back").start(sc)
        Animation(opacity=1, d=0.2).start(self.chiffre)
        Animation(arc=360, d=0.95, t="in_out_quad").start(self)

    def effacer(self):
        Animation(xyz=(1.12, 1.12, 1), d=0.35, t="in_quad").start(echelle(self))
        Animation(opacity=0, d=0.35, t="in_quad").start(self)

    def on_touch_down(self, t):  # rien ne passe à travers pendant le décompte
        return self.opacity > 0 or super().on_touch_down(t)


class EcranCourse(Screen):
    def __init__(self, app, **kw):
        super().__init__(name="course", **kw)
        self.app, self.course, self.prog, self.res = app, None, None, None
        self.dernier_evt, self.annonceur, self.sim, self.fini, self.voix_on = 0, None, None, False, True
        self.boussole, self.az, self.btn_cap, self.en_pause = None, None, None, False
        self.voix = Voix(None if platform != "android" else self._activite())

        racine = FloatLayout()
        col = BoxLayout(orientation="vertical")
        self.trace = Trace(suivi=True)
        carte = avec_zoom(self.trace, self.changer_orient)
        self.btn_voix = Bouton("Voix", self.changer_voix, "carte", 48, 15, size_hint=(None, None),
                               width=dp(96), pos_hint={"right": 0.97, "top": 0.97})
        carte.add_widget(self.btn_voix)
        self.bande = Bande()

        # par ordre d'importance en courant : distance, puis temps et allure, puis le reste
        panneau = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(372),
                            padding=[dp(20), dp(2), dp(20), dp(18)], spacing=dp(6))
        self.c_fond = fond(panneau, FOND)
        haut = BoxLayout(size_hint_y=None, height=dp(112))
        self.l_dist = lab("0,00", 104, gras=True, chiffres=True, size_hint_x=0.72)
        self.l_etat = lab("", 18, gras=True, aligne="right", size_hint_x=0.28)
        haut.add_widget(self.l_dist)
        haut.add_widget(self.l_etat)
        milieu = BoxLayout(size_hint_y=None, height=dp(84), spacing=dp(12))
        self.l_temps, self.l_allure = lab("00:00", 54, gras=True, chiffres=True), \
            lab("--:--", 54, gras=True, chiffres=True)
        self.legendes = []
        for val, legende in ((self.l_temps, "temps en mouvement"), (self.l_allure, "allure, min/km")):
            c = BoxLayout(orientation="vertical")
            c.add_widget(val)
            l = lab(legende, 14, BRUME, size_hint_y=None, height=dp(20))
            self.legendes.append(l)
            c.add_widget(l)
            milieu.add_widget(c)
        bas = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(12))
        self.l_vitesse = lab("", 32, gras=True, chiffres=True)
        self.l_dplus = lab("", 32, TRACE, gras=True, chiffres=True)
        bas.add_widget(self.l_vitesse)
        bas.add_widget(self.l_dplus)
        boutons = BoxLayout(size_hint_y=None, height=dp(76), spacing=dp(10))
        self.btn_pause = Bouton("Pause", self.pause_reprise, "encre", 76, 22)
        self.btn_fin = Bouton("Terminer", self.terminer, "contour", 76, 20, size_hint_x=0.75)
        boutons.add_widget(self.btn_pause)
        boutons.add_widget(self.btn_fin)
        for w in (haut, milieu, bas, BoxLayout(), boutons):
            panneau.add_widget(w)
        col.add_widget(carte)
        col.add_widget(self.bande)
        col.add_widget(panneau)
        racine.add_widget(col)
        self.decompte = Decompte(size_hint=(1, 1))
        racine.add_widget(self.decompte)
        self.add_widget(racine)
        self.peindre(False)

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
        self.app.aller("course", "monter")
        self.voix.preparer()
        self.n = 3
        self.decompte.montrer("3")
        self.voix.dire("3")
        Clock.schedule_interval(self._decompter, 1)

    def _decompter(self, dt):
        self.n -= 1
        if self.n > 0:
            self.decompte.montrer(str(self.n))
            self.voix.dire(str(self.n))
            return True
        self.decompte.effacer()
        self.voix.dire("C'est parti")
        self.journal.ecrire("debut", time.time())
        self.lancer_enregistrement()
        self.suivre()
        return False

    def afficher_boucle(self, res):
        self.res, self.fini = res, False
        self.course, self.dernier_evt, self.cap, self.km_vu = None, 0, Cap(), 0
        self.velo = res.get("sport") == "velo"
        self.altitude = Altitudes(res["coords"], res.get("ele"))  # altitude d'après la boucle prévue
        self.legendes[1].text = "vitesse, km/h" if self.velo else "allure, min/km"
        self.prog = Progression(res["coords"])
        self.trace.coords = res["coords"]
        self.trace.fait, self.trace.boucle_faite, self.trace.moi = [], [], []
        self.bande.part, self.bande.alerte = 0, False
        self.bande.gauche.text, self.bande.droite.text = f"{nombre(self.prog.total / 1000)} km à parcourir", ""
        self.l_dist.text, self.l_temps.text, self.l_allure.text = "0,00", "00:00", "--:--"
        self.peindre(False)
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
            self.course = appliquer(self.course, e, self.altitude)
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
        self.l_dist.text = f"{nombre(c.dist / 1000, 2)}{unite('km', 24)}"
        if int(c.dist // 1000) > self.km_vu:  # un kilomètre de plus : la distance bat une fois
            self.km_vu = int(c.dist // 1000)
            pulser(self.l_dist, 1.1, 0.6)
        self.l_temps.text = chrono(c.duree())
        if self.velo:  # à vélo : la vitesse en grand, la moyenne en petit
            self.l_allure.text = nombre(v * 3.6)
            moy = c.dist / c.duree() * 3.6 if c.duree() else 0
            self.l_vitesse.text = f"{nombre(moy)}{unite('km/h moy.', 15)}"
        else:
            self.l_allure.text = fmt_allure(v)
            self.l_vitesse.text = f"{nombre(v * 3.6)}{unite('km/h', 15)}"
        self.l_dplus.text = f"{c.dplus:.0f}{unite('m D+', 15)}"
        if c.en_pause != self.en_pause:
            self.peindre(c.en_pause)
        p, b = self.prog, self.bande
        b.alerte, b.part = p.hors_trace, p.pourcent / 100
        if p.hors_trace:
            b.gauche.text, b.droite.text = "Hors du parcours", f"à {p.ecart:.0f} m"
        else:
            b.gauche.text, b.droite.text = f"{nombre(p.restant / 1000)} km restants", f"{p.pourcent:.0f} %"

    def peindre(self, pause):
        """En pause, le panneau passe en négatif (fondu) : on le voit du coin de l'œil."""
        self.en_pause = pause
        encre, papier = (FOND, ENCRE) if pause else (ENCRE, FOND)
        Animation.cancel_all(self.c_fond)
        Animation(rgba=papier, d=0.25, t="out_quad").start(self.c_fond)
        for l, c in [(l, encre) for l in (self.l_dist, self.l_temps, self.l_allure, self.l_vitesse)] + \
                [(l, (*encre[:3], 0.62)) for l in self.legendes] + [(self.l_dplus, encre if pause else TRACE)]:
            Animation.cancel_all(l, "color")
            Animation(color=c, d=0.25, t="out_quad").start(l)
        self.l_etat.text, self.l_etat.color = ("En pause" if pause else ""), encre
        if pause:
            pulser(self.l_etat, 1.15)
        self.btn_pause.text, self.btn_pause.style = ("Reprendre", "signal") if pause else ("Pause", "encre")
        self.btn_fin.style = "fond" if pause else "contour"

    def pause_reprise(self, *_):
        if not self.course or self.fini:
            return
        self.journal.ecrire("reprise" if self.course.en_pause else "pause", time.time())
        self.lire_journal(0)

    def changer_voix(self, *_):
        self.voix_on = not self.voix_on
        self.journal.poser("voix", self.voix_on)  # lu par le service
        self.btn_voix.text = "Voix" if self.voix_on else "Muet"

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
        if self.velo:
            moy = f"{nombre(c.dist / c.duree() * 3.6) if c.duree() else '--'} km/h"
        else:
            moy = f"{fmt_allure(c.dist / c.duree()) if c.duree() else '--:--'} min/km"
        f = Feuille("Sortie terminée" if self.velo else "Course terminée", Window.height * 0.82)
        f.ajouter(lab(f"{nombre(c.dist / 1000, 2)}{unite('km', 26)}", 84, gras=True, chiffres=True,
                      size_hint_y=None, height=dp(92)))
        f.ajouter(lab(f"en {chrono(c.duree())}, {moy} en moyenne, {c.dplus:.0f} m de D+", 17, BRUME,
                      size_hint_y=None, height=dp(26)))
        f.ajouter(lab("Tes kilomètres", 16, gras=True, size_hint_y=None, height=dp(30)))
        sv = ScrollView()
        splits = Splits()
        splits.remplir(c.splits)
        sv.add_widget(splits)
        f.ajouter(sv)
        ligne = BoxLayout(size_hint_y=None, height=dp(72), spacing=dp(10))
        ligne.add_widget(Bouton("Enregistrer", lambda *_: self.fin_course(f, True), "signal", 72, 21))
        ligne.add_widget(Bouton("Supprimer", lambda b: confirmer(b, "Supprimer ?", lambda: self.fin_course(f, False)),
                                "contour", 72, 18, size_hint_x=0.7))
        f.ajouter(ligne)
        f.ouvrir()

    def fin_course(self, pop, garder):
        pop.fermer()
        act = None
        if garder and self.course.dist > 0:
            act = {**self.course.resume(), "sport": "velo" if self.velo else "course", "nom": self.res.get("nom")}
            self.app.stockage.enregistrer(act)
            self.app.synchroniser_activite(act)
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
        if act:  # la sortie qu'on vient d'enregistrer : GPX, Strava, partage
            self.app.ecran_detail.ouvrir(act["id"], "descendre")
        else:
            self.app.aller("plan", "descendre")

    # --- après un crash : une course du journal n'est pas terminée ---
    def verifier_reprise(self):
        etat, res = self.journal.etat(), self.journal.lire_meta("boucle")
        if etat is None or not res:
            return
        self.voix_on = self.journal.lire_meta("voix") is not False
        self.btn_voix.text = "Voix" if self.voix_on else "Muet"
        self.afficher_boucle(res)
        if etat == "fin":  # terminée mais pas encore enregistrée
            self.app.aller("course", "monter")
            self.lire_journal(0)
            self.fini = True
            self.popup_fin()
            return

        def reprendre():
            self.app.aller("course", "monter")
            self.lancer_enregistrement()
            self.suivre()

        def finir():
            self.app.aller("course", "monter")
            self.lire_journal(0)
            self.terminer()

        choix("Course en cours", "Ta dernière course n'est pas terminée. Tu la reprends ?",
              [("Reprendre", reprendre, "signal"), ("Terminer", finir, "contour")])

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
                self.bande.gauche.text = self.boussole.erreur
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
