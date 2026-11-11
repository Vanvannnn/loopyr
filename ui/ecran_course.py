"""Écran 2 : la sortie. Tout passe par le journal (journal.py) : le service GPS (ou le simulateur sur PC) y écrit
les positions, cet écran le relit toutes les 0,5 s pour afficher la sortie, la navigation et les chiffres.

Navigation : un bandeau en haut donne la prochaine consigne du moteur d'itinéraires (flèche, distance, phrase),
la carte suit ta direction avec une grande flèche, le prochain carrefour est marqué. Si tu pars dans l'autre
sens, la boucle est suivie dans ce sens (et recalculée par le moteur à vélo, pour les sens interdits) ; si tu
sors du parcours, un chemin pour le rejoindre est calculé sur le réseau."""
import threading
import time

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, Line, RoundedRectangle, Triangle
from kivy.metrics import dp
from kivy.properties import NumericProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.screenmanager import Screen
from kivy.uix.widget import Widget
from kivy.utils import platform

from annonces import Annonceur
from boucles import ErreurItineraire
from capteurs.voix import Voix
from course import fmt_allure
from geo import Altimetre, Altitudes, Cap, ecart
from journal import appliquer
from progression import Progression, arrondi, cote
from ui.carte import Trace, avec_zoom
from ui.widgets import (BRUME, ENCRE, FOND, FOND_2, SIGNAL, SUR_SIGNAL, TRACE, Bande, Bouton, choix, echelle, fond,
                        lab, nombre, pulser, unite)

ORIENTS = {"marche": "Sens de marche", "boussole": "Boussole", "nord": "Nord en haut"}


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
        self.consigne = lab("", 22, gras=True, aligne="center", size_hint=(0.9, None), height=dp(80),
                            pos_hint={"center_x": 0.5, "y": 0.08})
        self.add_widget(self.chiffre)
        self.add_widget(self.consigne)
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


class Virage(Widget):
    """Le pictogramme de la consigne : flèche à gauche, à droite, tout droit, demi-tour ou rond-point."""
    forme = StringProperty("tout_droit")

    def __init__(self, **kw):
        super().__init__(**kw)
        self.bind(pos=self.dessiner, size=self.dessiner, forme=self.dessiner)

    def dessiner(self, *_):
        self.canvas.clear()
        cx, cy, r = self.center_x, self.center_y, min(self.width, self.height) / 2
        w = r * 0.22
        with self.canvas:
            Color(*FOND)
            if self.forme == "rond_point":
                Line(circle=(cx, cy + r * 0.1, r * 0.42), width=w * 0.7)
                Line(points=[cx, cy - r * 0.9, cx, cy - r * 0.32], width=w)
                Line(points=[cx + r * 0.3, cy + r * 0.4, cx + r * 0.75, cy + r * 0.8], width=w)
                Triangle(points=[cx + r * 0.95, cy + r, cx + r * 0.45, cy + r * 0.92, cx + r * 0.87, cy + r * 0.5])
                return
            if self.forme == "demi_tour":
                Line(points=[cx + r * 0.4, cy - r * 0.8, cx + r * 0.4, cy + r * 0.2], width=w)
                Line(ellipse=(cx - r * 0.4, cy - r * 0.2, r * 0.8, r * 0.8, -90, 90), width=w)
                Triangle(points=[cx - r * 0.75, cy - r * 0.1, cx - r * 0.05, cy - r * 0.1, cx - r * 0.4, cy - r * 0.75])
                return
            sens = {"gauche": -1, "droite": 1}.get(self.forme, 0)
            if not sens:
                Line(points=[cx, cy - r * 0.9, cx, cy + r * 0.3], width=w)
                Triangle(points=[cx - r * 0.55, cy + r * 0.25, cx + r * 0.55, cy + r * 0.25, cx, cy + r * 0.95])
                return
            Line(points=[cx - sens * r * 0.35, cy - r * 0.9, cx - sens * r * 0.35, cy + r * 0.05,
                         cx + sens * r * 0.25, cy + r * 0.05], width=w, joint="round")
            Triangle(points=[cx + sens * r * 0.2, cy + r * 0.6, cx + sens * r * 0.2, cy - r * 0.5,
                             cx + sens * r * 0.95, cy + r * 0.05])


class Consigne(BoxLayout):
    """Bandeau de navigation, en haut de la carte : pictogramme, distance au carrefour, phrase."""

    def __init__(self, **kw):
        super().__init__(size_hint=(0.94, None), height=dp(96), padding=[dp(14), dp(10)], spacing=dp(12),
                         pos_hint={"center_x": 0.5, "top": 0.985}, opacity=0, **kw)
        with self.canvas.before:
            self._c = Color(*ENCRE)
            self._fond = RoundedRectangle(radius=[dp(18)])
        self.bind(pos=self._placer, size=self._placer)
        self.virage = Virage(size_hint_x=None, width=dp(72))
        texte = BoxLayout(orientation="vertical")
        self.l_dist = lab("", 34, FOND, gras=True, chiffres=True, size_hint_y=0.55)
        self.l_texte = lab("", 18, FOND, gras=True, size_hint_y=0.45, valign="middle")
        texte.add_widget(self.l_dist)
        texte.add_widget(self.l_texte)
        self.add_widget(self.virage)
        self.add_widget(texte)
        self.cle = None

    def _placer(self, *_):
        self._fond.pos, self._fond.size = self.pos, self.size

    def montrer(self, texte, distance=None, forme="tout_droit", alerte=False):
        cle = (texte, forme, alerte)
        self.l_texte.text = texte
        self.l_dist.text = arrondi(distance) if distance is not None else ""
        self.l_dist.size_hint_y = 0.55 if distance is not None else 0.001  # sans distance : la phrase a 2 lignes
        self.virage.forme = forme
        self._c.rgba = SIGNAL if alerte else ENCRE
        if cle != self.cle:  # nouvelle consigne : elle se signale
            self.cle = cle
            if self.opacity < 1:
                Animation(opacity=1, d=0.25).start(self)
            pulser(self, 1.04, 0.4)

    def cacher(self):
        self.cle = None
        Animation(opacity=0, d=0.25).start(self)


class EcranCourse(Screen):
    def __init__(self, app, **kw):
        super().__init__(name="course", **kw)
        self.app, self.course, self.prog, self.res = app, None, None, None
        self.dernier_evt, self.annonceur, self.sim, self.fini, self.voix_on = 0, None, None, False, True
        self.boussole, self.az, self.btn_cap, self.en_pause = None, None, None, False
        self.rejoint, self.prog_rejoindre, self.t_rejoindre, self.message = None, None, 0, None
        self.voix = Voix(None if platform != "android" else self._activite())

        racine = FloatLayout()
        col = BoxLayout(orientation="vertical")
        self.trace = Trace(suivi=True)
        carte = avec_zoom(self.trace, self.changer_orient)
        self.btn_voix = Bouton("Voix", self.changer_voix, "carte", 48, 15, size_hint=(None, None),
                               width=dp(96), pos_hint={"right": 0.97, "y": 0.02})
        carte.add_widget(self.btn_voix)
        self.consigne = Consigne()
        carte.add_widget(self.consigne)
        self.bande = Bande()

        # par ordre d'importance en mouvement : distance, puis temps et allure, puis le reste en petit
        panneau = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(352),
                            padding=[dp(20), dp(2), dp(20), dp(16)], spacing=dp(4))
        self.c_fond = fond(panneau, FOND)
        haut = BoxLayout(size_hint_y=None, height=dp(104))
        self.l_dist = lab("0,00", 96, gras=True, chiffres=True, size_hint_x=0.72)
        self.l_etat = lab("", 18, gras=True, aligne="right", size_hint_x=0.28)
        haut.add_widget(self.l_dist)
        haut.add_widget(self.l_etat)
        milieu = BoxLayout(size_hint_y=None, height=dp(80), spacing=dp(12))
        self.l_temps, self.l_allure = lab("00:00", 52, gras=True, chiffres=True), \
            lab("--:--", 52, gras=True, chiffres=True)
        self.legendes = []
        for val, legende in ((self.l_temps, "temps en mouvement"), (self.l_allure, "allure, min/km")):
            c = BoxLayout(orientation="vertical")
            c.add_widget(val)
            l = lab(legende, 14, BRUME, size_hint_y=None, height=dp(20))
            self.legendes.append(l)
            c.add_widget(l)
            milieu.add_widget(c)
        # dénivelé en direct (D+ en sauge, la couleur de la boucle), D-, altitude, et la moyenne
        bas = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(8))
        self.petits = []
        for couleur, legende in ((TRACE, "D+"), (None, "D−"), (None, "altitude"), (None, "moyenne")):
            c = BoxLayout(orientation="vertical")
            v = lab("–", 26, couleur, gras=True, chiffres=True)
            l = lab(legende, 13, BRUME, size_hint_y=None, height=dp(18))
            c.add_widget(v)
            c.add_widget(l)
            self.petits.append((v, l, couleur))
            bas.add_widget(c)
        self.legende_moy = self.petits[3][1]
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
        """Depuis l'écran de la boucle : affiche la boucle, compte 3-2-1 puis lance la sortie."""
        if platform == "android" and not self.app.reglages.get("batterie_vue"):
            try:
                from capteurs.gps import demander_sans_economie, economie_batterie_active
                if economie_batterie_active():
                    return self._avertir_batterie(res, demander_sans_economie)
            except Exception:
                pass
        self.journal.vider()
        self.journal.poser("boucle", res)
        self.journal.poser("voix", self.voix_on)
        self.afficher_boucle(res)
        self.app.aller("course", "monter")
        self.voix.preparer()
        self.n = 3
        self.decompte.consigne.text = self.prog.consigne_depart() if self.prog.consignes else ""
        self.decompte.montrer("3")
        self.voix.dire("3")
        Clock.schedule_interval(self._decompter, 1)

    def _avertir_batterie(self, res, demander):
        """Sans cette autorisation, beaucoup de téléphones coupent le GPS écran verrouillé au bout de quelques
        minutes : on l'explique une fois, avant la première sortie."""
        def autoriser():
            self.app.sauver_reglages(batterie_vue=True)
            demander()

        def plus_tard():
            self.app.sauver_reglages(batterie_vue=True)
            self.preparer(res)

        choix("Suivi écran verrouillé",
              "Pour que le GPS continue quand le téléphone est verrouillé, autorise Loopy à ignorer l'économie "
              "de batterie (Android le demande). Sinon, certaines marques coupent le suivi au bout de quelques "
              "minutes.", [("Autoriser", autoriser, "signal"), ("Plus tard", plus_tard, "contour")], hauteur=dp(340))

    def _decompter(self, dt):
        self.n -= 1
        if self.n > 0:
            self.decompte.montrer(str(self.n))
            self.voix.dire(str(self.n))
            return True
        self.decompte.effacer()
        depart = self.prog.consigne_depart() if self.prog.consignes else ""
        self.voix.dire(("C'est parti. " + depart.replace("Départ : ", "")) if depart else "C'est parti")
        self.journal.ecrire("debut", time.time())
        self.lancer_enregistrement()
        self.suivre()
        if depart:
            proche = self.prog.prochaine()
            forme = cote(proche[2]) if proche and proche[1] <= 150 else "tout_droit"
            self.message = (depart, time.time() + 12, forme)
            self.consigne.montrer(depart, None, forme)
        return False

    def afficher_boucle(self, res):
        self.res, self.fini = res, False
        self.course, self.dernier_evt, self.cap, self.km_vu = None, 0, Cap(), 0
        self.velo = res.get("sport") == "velo"
        self.altimetre = Altimetre(Altitudes(res["coords"], res.get("ele")))
        self.legendes[1].text = "vitesse, km/h" if self.velo else "allure, min/km"
        self.legende_moy.text = "moy., km/h" if self.velo else "vitesse, km/h"
        self.prog = Progression(res["coords"], res.get("hints"))
        self.prog_rejoindre, self.rejoint = None, None
        self.trace.coords = res["coords"]
        self.trace.fait, self.trace.boucle_faite, self.trace.moi = [], [], []
        self.trace.prochain, self.trace.rejoindre = [], []
        self.bande.part, self.bande.alerte = 0, False
        self.bande.gauche.text, self.bande.droite.text = f"{nombre(self.prog.total / 1000)} km à parcourir", ""
        self.l_dist.text, self.l_temps.text, self.l_allure.text = "0,00", "00:00", "--:--"
        for v, _, _ in self.petits:
            v.text = "–"
        self.consigne.cacher()
        self.peindre(False)
        Window.allow_screensaver = False  # écran allumé pendant la sortie

    def lancer_enregistrement(self):
        """Démarre (ou relance) ce qui écrit les positions dans le journal."""
        if platform == "android":
            from capteurs.gps import demarrer_service
            demarrer_service(self.app.chemin_journal, self.res.get("sport"))  # sans effet s'il tourne déjà
        else:
            from capteurs.simulateur import Simulateur
            self.sim = Simulateur(self.journal, self.res["coords"], self.res.get("ele"))
            self.sim.demarrer()
            # sur Android, c'est le service qui annonce (même écran éteint)
            self.annonceur = Annonceur(self.res["coords"], self.voix.dire, self.voix.vibrer, lambda: self.voix_on,
                                       consignes=self.res.get("hints"), sport=self.res.get("sport") or "course",
                                       boucle=lambda: self.journal.lire_meta("boucle"))

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
            try:
                from capteurs.gps import arreter_service
                arreter_service()
            except Exception:  # le service s'arrête de toute façon en lisant « fin » dans le journal
                pass
        self.annonceur = None

    # --- pendant la sortie ---
    def lire_journal(self, dt):
        dernier = None
        for e in self.journal.lire(apres=self.dernier_evt):
            self.dernier_evt = e[0]
            self.course = appliquer(self.course, e, self.altimetre)
            if self.annonceur:
                self.annonceur.traiter(e)
            if e[1] == "point" and self.course and not self.course.en_pause:
                self.prog.maj(e[3], e[4], e[2], e[6])
                self._evenement(self.prog.evenement, (e[3], e[4]))
                if self.prog_rejoindre:
                    self.prog_rejoindre.maj(e[3], e[4], e[2], e[6])
                dernier = (e[3], e[4])
        if dernier:
            self.trace.cap = self.cap.maj(dernier)
            self.trace.fait = self.course.trace
            self.trace.boucle_faite = self.prog.partie_faite()
            self.trace.moi = list(dernier)
            proche = self.prog.point_prochaine()
            self.trace.prochain = list(proche) if proche else []
        if self.course:
            self.maj_stats()
            self.maj_consigne()

    def _evenement(self, evt, pos):
        if evt == "inverse":
            self.trace.coords = list(self.prog.pts)
            self._publier_boucle(list(self.prog.pts), self._hints_de(self.prog))
            self.message = ("Tu fais la boucle dans l'autre sens : on la suit dans ce sens", time.time() + 8, "demi_tour")
            if self.velo:  # à vélo, les sens interdits comptent : le moteur recalcule la boucle dans ce sens
                self._recalculer_sens(pos)
        elif evt == "mauvais_sens":
            self.message = ("Tu t'éloignes de l'arrivée : fais demi-tour", time.time() + 10, "demi_tour")
        elif evt == "hors":
            self._rejoindre(pos)
        elif evt in ("retour", "raccourci"):
            self.prog_rejoindre, self.trace.rejoindre = None, []
        elif evt == "arrivee":
            self.message = ("Tu es arrivé : boucle terminée" if self.prog.boucle else "Tu es arrivé", time.time() + 30,
                            "tout_droit")

    @staticmethod
    def _hints_de(prog):
        """Les consignes d'une progression (éventuellement inversée), au format du moteur."""
        return [list(h) for h in prog.consignes_brutes]

    def _publier_boucle(self, coords, hints):
        """La boucle a changé en route : on la note dans le journal, le service (annonces) la relit."""
        self.res = {**self.res, "coords": coords, "hints": hints}
        self.journal.poser("boucle", self.res)
        self.journal.ecrire("boucle", time.time())

    def _en_fond(self, travail, fini):
        def fil():
            try:
                r = travail()
            except (ErreurItineraire, OSError, ValueError, KeyError) as e:
                r = e
            Clock.schedule_once(lambda dt: fini(r))
        threading.Thread(target=fil, daemon=True).start()

    def _recalculer_sens(self, pos):
        pts = self.prog.pts
        n = len(pts)
        etapes = [pts[0]] + [pts[int(n * k / 6)] for k in range(1, 6)] + [pts[-1]]

        def fini(r):
            if isinstance(r, Exception) or self.fini or not self.course:
                return  # sans réseau : on garde la boucle inversée, consignes miroir
            self.prog = Progression(r["coords"], r["hints"])
            self.prog.maj(pos[0], pos[1], time.time())
            self.trace.coords = r["coords"]
            self._publier_boucle(r["coords"], r["hints"])
        self._en_fond(lambda: self.app.moteur.itineraire(etapes, "velo"), fini)

    def _rejoindre(self, pos):
        """Hors du parcours : le moteur calcule le chemin jusqu'à la boucle, un peu plus loin que là où tu l'as
        quittée. Une demande à la fois, pas plus d'une par minute."""
        if self.t_rejoindre and time.time() - self.t_rejoindre < 60:
            return
        self.t_rejoindre = time.time()
        cible = self.prog.point_a(self.prog.fait + 150)

        def fini(r):
            if isinstance(r, Exception) or not self.prog.hors_trace:
                return
            self.prog_rejoindre = Progression(r["coords"], r["hints"])
            self.trace.rejoindre = r["coords"]
        self._en_fond(lambda: self.app.moteur.itineraire([pos, cible], self.res.get("sport") or "course"), fini)

    def maj_consigne(self):
        p = self.prog
        if self.message and time.time() < self.message[1]:
            return self.consigne.montrer(self.message[0], None, self.message[2])
        if p.hors_trace:
            if self.prog_rejoindre and self.prog_rejoindre.prochaine():
                texte, d, cmd = self.prog_rejoindre.prochaine()
                return self.consigne.montrer(f"Pour rejoindre : {texte[0].lower()}{texte[1:]}", d, cote(cmd), True)
            return self.consigne.montrer(f"Hors du parcours, à {p.ecart:.0f} m", None, "demi_tour", True)
        prochaine = p.prochaine()
        if prochaine and prochaine[1] <= (1500 if self.velo else 800):
            texte, d, cmd = prochaine
            return self.consigne.montrer(texte, d, cote(cmd))
        if p.consignes and not p.arrive:
            return self.consigne.montrer("Continue sur le tracé", prochaine[1] if prochaine else None, "tout_droit")
        self.consigne.cacher()

    def maj_stats(self):
        c, v = self.course, self.course.vitesse()
        self.l_dist.text = f"{nombre(c.dist / 1000, 2)}{unite('km', 24)}"
        if int(c.dist // 1000) > self.km_vu:  # un kilomètre de plus : la distance bat une fois
            self.km_vu = int(c.dist // 1000)
            pulser(self.l_dist, 1.1, 0.6)
        self.l_temps.text = chrono(c.duree())
        moy = c.dist / c.duree() * 3.6 if c.duree() else 0
        if self.velo:  # à vélo : la vitesse en grand, la moyenne en petit
            self.l_allure.text = nombre(v * 3.6)
            vals = nombre(moy)
        else:
            self.l_allure.text = fmt_allure(v)
            vals = nombre(v * 3.6)
        textes = (f"{c.dplus:.0f}{unite('m', 13)}", f"{c.dmoins:.0f}{unite('m', 13)}",
                  f"{c.alt:.0f}{unite('m', 13)}" if c.alt is not None else "–", vals)
        for (lbl, _, _), t in zip(self.petits, textes):
            lbl.text = t
        if c.en_pause != self.en_pause:
            self.peindre(c.en_pause)
        p, b = self.prog, self.bande
        b.alerte, b.part = p.hors_trace, p.pourcent / 100
        if p.hors_trace:
            b.gauche.text, b.droite.text = "Hors du parcours", f"à {p.ecart:.0f} m"
        elif p.arrive:
            b.gauche.text, b.droite.text = "Boucle terminée" if p.boucle else "Arrivé", "100 %"
        else:
            b.gauche.text, b.droite.text = f"{nombre(p.restant / 1000)} km restants", f"{p.pourcent:.0f} %"

    def peindre(self, pause):
        """En pause, le panneau passe en négatif (fondu) : on le voit du coin de l'œil."""
        self.en_pause = pause
        encre, papier = (FOND, ENCRE) if pause else (ENCRE, FOND)
        Animation.cancel_all(self.c_fond)
        Animation(rgba=papier, d=0.25, t="out_quad").start(self.c_fond)
        cibles = [(l, encre) for l in (self.l_dist, self.l_temps, self.l_allure)] + \
            [(l, (*encre[:3], 0.62)) for l in self.legendes] + \
            [(v, encre if (pause or c is None) else c) for v, _, c in self.petits]
        for l, c in cibles:
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
        """Terminer : on fige la sortie (« fin » dans le journal), on arrête le GPS, puis le récapitulatif.
        Rien n'est effacé ici : le journal garde tout jusqu'à ce que la sortie soit enregistrée."""
        if not self.course or self.fini:
            return
        self.fini = True
        self.journal.ecrire("fin", time.time())
        self.lire_journal(0)
        self.arreter_enregistrement()
        self.consigne.cacher()
        self.app.ecran_fin.ouvrir(self.course, self.res, self.journal.lire_meta("barometre"))

    def apres_fin(self):
        """Appelé par l'écran de fin, une fois la sortie enregistrée (ou supprimée)."""
        self.course, self.prog_rejoindre = None, None
        self.trace.fait, self.trace.boucle_faite, self.trace.rejoindre, self.trace.prochain = [], [], [], []
        if self.boussole:
            self.boussole.activer(False)
        Clock.unschedule(self.maj_boussole)
        self.trace.orient, self.trace.az = "marche", None
        if self.btn_cap:
            self.btn_cap.text = ORIENTS["marche"]
        Window.allow_screensaver = True

    # --- après un crash ou une fermeture : une sortie du journal n'est pas terminée ---
    def verifier_reprise(self):
        etat, res = self.journal.etat(), self.journal.lire_meta("boucle")
        if etat is None or not res:
            return
        self.voix_on = self.journal.lire_meta("voix") is not False
        self.btn_voix.text = "Voix" if self.voix_on else "Muet"
        self.afficher_boucle(res)
        if etat == "fin":  # terminée mais pas encore enregistrée : le récapitulatif revient
            self.lire_journal(0)
            self.fini = True
            if self.course:
                self.app.ecran_fin.ouvrir(self.course, res, self.journal.lire_meta("barometre"))
            return

        def reprendre():
            self.app.aller("course", "monter")
            self.lancer_enregistrement()
            self.suivre()

        def finir():
            self.app.aller("course", "monter")
            self.lire_journal(0)
            self.terminer()

        choix("Sortie en cours", "Ta dernière sortie n'est pas terminée. Tu la reprends ?",
              [("Reprendre", reprendre, "signal"), ("Terminer", finir, "contour")])

    def au_retour(self):
        """L'app revient au premier plan (écran déverrouillé) : on relit tout de suite ce que le service a noté."""
        if self.course and not self.fini and self.app.sm.current == "course":
            self.lire_journal(0)

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
