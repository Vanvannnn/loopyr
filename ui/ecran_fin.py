"""Fin de sortie : le récapitulatif (carte du trajet réel, statistiques), un nom proposé et modifiable, le ressenti
et une description facultatifs, puis Enregistrer.

L'enregistrement est fait une seule fois, dans cet ordre : l'activité est écrite sur le téléphone (écriture
atomique), puis seulement le journal de la sortie est vidé, puis la synchronisation part en arrière-plan.
Si l'app est interrompue entre-temps, le journal est toujours là : au prochain lancement, ce récapitulatif
revient, et l'enregistrement (même identifiant) remplace la même activité au lieu d'en créer une seconde."""
import logging
import threading
import time

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import Screen

from boucles import ErreurItineraire, lieu_de
from course import fmt_allure, nom_auto
from ui.carte import Trace
from ui.ecran_course import chrono
from ui.widgets import (BRUME, ENCRE, FOND, TRACE, ALERTE, Bouton, Segmente, apparaitre, champ, confirmer, fond, lab,
                        liste_defilante, nombre, unite)

RESSENTIS = (("facile", "Facile"), ("bien", "Bien"), ("dur", "Dur"), ("epuisant", "Épuisant"))
SOURCES_DPLUS = {"baro": "baromètre du téléphone", "terrain": "relief le long de la boucle (modèle de terrain)",
                 "gps": "altitude GPS lissée (approximative)"}


def stats(c, velo):
    """[(valeur, légende)] du récapitulatif, uniquement ce qui est mesuré."""
    duree = c.duree()
    if velo:
        moy = (f"{nombre(c.dist / duree * 3.6)}", "vitesse moy., km/h") if duree else ("–", "vitesse moy.")
    else:
        moy = (fmt_allure(c.dist / duree) if duree else "–", "allure moy., min/km")
    vmax = (nombre(c.vmax * 3.6), "vitesse max, km/h") if c.vmax >= 1 else ("–", "vitesse max")
    return [(chrono(c.duree_totale()), "durée totale"), (chrono(duree), "en mouvement"), moy,
            (f"{c.dplus:.0f} m", "dénivelé +"), (f"{c.dmoins:.0f} m", "dénivelé −"), vmax]


class EcranFin(Screen):
    def __init__(self, app, **kw):
        super().__init__(name="fin", **kw)
        self.app, self.course, self.res, self.enregistre, self.nom_touche = app, None, None, False, False
        col = BoxLayout(orientation="vertical")
        self.trace = Trace()
        self.trace.size_hint_y = 0.34
        col.add_widget(self.trace)
        sv, contenu = liste_defilante(8)
        sv.size_hint_y = 0.66
        contenu.padding = [dp(20), dp(10), dp(20), dp(20)]
        fond(contenu, FOND)
        self.l_titre = lab("", 20, gras=True, size_hint_y=None, height=dp(30))
        self.l_dist = lab("", 76, gras=True, chiffres=True, size_hint_y=None, height=dp(84))
        grille = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(124), spacing=dp(6))
        self.cases = []
        for _ in range(2):
            ligne = BoxLayout(spacing=dp(10))
            for _ in range(3):
                c = BoxLayout(orientation="vertical")
                v = lab("", 26, gras=True, chiffres=True)
                l = lab("", 13, BRUME, size_hint_y=None, height=dp(18))
                c.add_widget(v)
                c.add_widget(l)
                self.cases.append((v, l))
                ligne.add_widget(c)
            grille.add_widget(ligne)
        self.l_source = lab("", 13, BRUME, size_hint_y=None, height=dp(22))
        self.nom = champ("Nom de la sortie")
        self.nom.bind(text=self._nom_modifie)
        self.ressenti = Segmente(RESSENTIS, "", hauteur=50)
        self.description = champ("Description ou ressenti (facultatif)", multiline=True, height=dp(96))
        self.l_info = lab("", 15, BRUME, size_hint_y=None, height=dp(24))
        ligne = BoxLayout(size_hint_y=None, height=dp(72), spacing=dp(10))
        self.btn_ok = Bouton("Enregistrer", self.enregistrer, "signal", 72, 21)
        self.btn_suppr = Bouton("Supprimer", lambda b: confirmer(b, "Supprimer ?", self.supprimer), "contour", 72, 18,
                                size_hint_x=0.6)
        ligne.add_widget(self.btn_ok)
        ligne.add_widget(self.btn_suppr)
        for w in (self.l_titre, self.l_dist, grille, self.l_source, lab("Nom", 15, gras=True, size_hint_y=None,
                  height=dp(22)), self.nom, lab("Comment ça s'est passé ?", 15, gras=True, size_hint_y=None,
                  height=dp(26)), self.ressenti, self.description, self.l_info, ligne):
            contenu.add_widget(w)
        col.add_widget(sv)
        self.add_widget(col)

    def _nom_modifie(self, *_):
        if getattr(self, "_remplissage", False):
            return
        self.nom_touche = True

    def ouvrir(self, course, res, barometre=None):
        self.course, self.res, self.enregistre, self.nom_touche = course, res or {}, False, False
        velo = self.res.get("sport") == "velo"
        c = course
        self.l_titre.text = ("Sortie vélo terminée" if velo else "Course terminée")
        self.l_dist.text = f"{nombre(c.dist / 1000, 2)}{unite('km', 24)}"
        for (v, l), (valeur, legende) in zip(self.cases, stats(c, velo)):
            v.text, l.text = valeur, legende
        source = getattr(getattr(self.app.ecran_course, "altimetre", None), "source", None)
        self.l_source.text = (f"Dénivelé : {SOURCES_DPLUS[source]}" if source in SOURCES_DPLUS else
                              "Dénivelé : aucune altitude fiable pendant la sortie")
        self.trace.autres = [self.res["coords"]] if self.res.get("coords") else []
        self.trace.coords = c.trace if len(c.trace) >= 2 else (self.res.get("coords") or [])
        try:  # déjà écrite (app interrompue juste après l'enregistrement) : on reprend ce qui avait été saisi
            deja = self.app.stockage.charger(c.resume()["id"])
        except (OSError, ValueError):
            deja = {}
        self._remplissage = True
        self.nom.text = deja.get("nom") or nom_auto(self.res.get("sport"), c.debut, c.dist)
        self.description.text = deja.get("description") or ""
        self._remplissage = False
        self.nom_touche = bool(deja.get("nom"))
        self.ressenti.choix = deja.get("ressenti") or ""
        self.l_info.text = ""
        self.btn_ok.disabled = self.btn_suppr.disabled = False
        self.app.aller("fin", "monter")
        if c.trace:
            self._chercher_lieu(c.trace[0], velo)

    def _chercher_lieu(self, point, velo):
        """« Course matinale à Pessac » : la commune du départ (OpenStreetMap), si le réseau répond vite."""
        c = self.course

        def fil():
            try:
                lieu = lieu_de(*point)
            except (ErreurItineraire, OSError, ValueError):
                return
            if lieu:
                Clock.schedule_once(lambda dt: self._lieu(c, lieu))
        threading.Thread(target=fil, daemon=True).start()

    def _lieu(self, c, lieu):
        if c is self.course and not self.nom_touche and not self.enregistre:
            self._remplissage = True
            self.nom.text = nom_auto(self.res.get("sport"), c.debut, c.dist, lieu)
            self._remplissage = False

    def activite(self):
        c = self.course
        act = {**c.resume(), "sport": "velo" if self.res.get("sport") == "velo" else "course",
               "nom": self.nom.text.strip()[:100] or nom_auto(self.res.get("sport"), c.debut, c.dist),
               "description": self.description.text.strip()[:2000], "ressenti": self.ressenti.choix or None,
               "source_denivele": getattr(getattr(self.app.ecran_course, "altimetre", None), "source", None),
               "boucle": self.res.get("nom")}
        return act

    def enregistrer(self, *_):
        if self.enregistre or not self.course:  # une seule fois, même avec deux appuis rapides
            return
        self.enregistre = True
        self.btn_ok.disabled = self.btn_suppr.disabled = True
        act = None
        if self.course.dist > 0 and self.course.segments[0]:
            act = self.activite()
            try:
                self.app.stockage.enregistrer(act)
            except OSError as err:  # téléphone plein… : on ne vide surtout pas le journal
                logging.exception("enregistrement de l'activité")
                self.l_info.text = f"Enregistrement impossible : {err}. La sortie reste en attente."
                self.l_info.color = ALERTE
                self.enregistre = False
                self.btn_ok.disabled = self.btn_suppr.disabled = False
                return
        self._terminer(act)

    def supprimer(self):
        if self.enregistre:
            return
        self.enregistre = True
        self._terminer(None)

    def _terminer(self, act):
        try:
            self.app.journal.vider()
        except Exception:  # le journal sera vidé au prochain lancement (l'activité, elle, est déjà écrite)
            logging.exception("vidage du journal")
        self.app.ecran_course.apres_fin()
        self.course = None
        if act:
            self.app.synchroniser_activite(act)
            self.app.ecran_detail.ouvrir(act["id"], "descendre")
        else:
            self.app.aller("accueil", "descendre")
