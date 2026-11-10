"""Les boucles proposées : la carte, le choix entre les propositions, ce qu'on sait de chacune (distance réelle,
D+, types de voies, revêtement et la part réellement connue), puis GPX, enregistrement ou départ."""
import threading
import time

from kivy.clock import Clock
from kivy.graphics import Color, Line, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import Screen
from kivy.utils import platform

import boucles
from gpx import gpx_itineraire, nom_itineraire
from ui import widgets
from ui.carte import Trace, avec_zoom
from ui.widgets import (BRUME, ENCRE, FOND, FOND_2, Bouton, Repartition, apparaitre, fond, lab, nombre, titre_ecran)

COULEURS_VOIES = (("cyclable", "TRACE"), ("chemin", "CHEMIN"), ("rue", "ROUTE"), ("grand_axe", "SIGNAL"),
                  ("escaliers", "ALERTE"))
NOMS_VOIES = {"cyclable": "pistes cyclables", "chemin": "chemins", "rue": "rues calmes", "grand_axe": "grands axes",
              "escaliers": "escaliers"}


def phrase_voies(resume, distance):
    """Les deux types de voies principaux, en clair : « 62 % rues calmes, 30 % pistes cyclables »."""
    v = sorted(resume["voies"].items(), key=lambda kv: -kv[1])
    return ", ".join(f"{round(m / distance * 100)} % {NOMS_VOIES[k]}" for k, m in v[:2] if m / distance >= 0.05)


class MiniTrace(Trace):
    """Carte miniature (vraies tuiles OpenStreetMap) : on ne la manipule pas, on la touche pour choisir."""

    def on_touch_down(self, t):
        return False

    def on_touch_move(self, t):
        return False

    def on_touch_up(self, t):
        return False


def part_revetue(p):
    r = (p.get("resume_voies") or {}).get("revetement") or {}
    tot = sum(r.values())
    return round(r.get("revetu", 0) / tot * 100) if tot else None


class CarteBoucle(ButtonBehavior, BoxLayout):
    """Une proposition : sa carte, son départ, sa distance, son D+ et sa surface. Touchée : elle est choisie."""

    def __init__(self, lettre, p, action, **kw):
        super().__init__(orientation="vertical", padding=dp(4), spacing=dp(2), **kw)
        with self.canvas.before:
            Color(*FOND_2)
            self._fond = RoundedRectangle(radius=[dp(12)])
            self._c_bord = Color(*ENCRE[:3], 0)
            self._bord = Line(width=dp(2))
        self.bind(pos=self._placer, size=self._placer, on_release=lambda *_: action())
        self.carte = MiniTrace()
        self.carte.coords = p["coords"]
        self.add_widget(self.carte)
        rev = part_revetue(p)
        self.add_widget(lab(f"{lettre}  {nombre(p['distance'] / 1000)} km", 17, gras=True, chiffres=True,
                            size_hint_y=None, height=dp(22), aligne="center"))
        self.add_widget(lab(f"{p['montee']:.0f} m D+" + (f"\n{rev} % revêtu" if rev is not None else ""), 12,
                            BRUME, size_hint_y=None, height=dp(32), aligne="center"))

    def _placer(self, *_):
        self._fond.pos, self._fond.size = self.pos, self.size
        self._bord.rounded_rectangle = (self.x + dp(1), self.y + dp(1), self.width - dp(2), self.height - dp(2), dp(12))

    def choisie(self, oui):
        self._c_bord.a = 1 if oui else 0


class EcranPlan(Screen):
    def __init__(self, app, **kw):
        super().__init__(name="plan", **kw)
        self.app, self.res, self.choix_i, self.calcul, self.depart = app, None, 0, False, None
        self.itineraire = None  # boucle déjà enregistrée qu'on revoit (pas de nouvelle génération)
        col = BoxLayout(orientation="vertical")
        self.retour_vers = "distance"
        self.barre = titre_ecran("", lambda *_: app.aller(self.retour_vers, "retour"))
        col.add_widget(self.barre)
        self.trace = Trace()
        col.add_widget(avec_zoom(self.trace))

        panneau = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(464),
                            padding=[dp(20), dp(8), dp(20), dp(14)], spacing=dp(6))
        fond(panneau, FOND)
        self.info = lab("", 19, gras=True, size_hint_y=None, height=dp(44))
        self.props = BoxLayout(size_hint_y=None, height=dp(0), spacing=dp(8))  # les miniatures
        self.l_details = lab("", 15, BRUME, size_hint_y=None, height=dp(40))
        self.voies = Repartition()
        self.l_revet = lab("", 14, BRUME, size_hint_y=None, height=dp(36))
        ligne = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(8))
        self.btn_gpx = Bouton("GPX", self.gpx, "contour", 52, 16)
        self.btn_garder = Bouton("Enregistrer", self.garder, "contour", 52, 16)
        self.btn_autre = Bouton("Autres boucles", self.lancer, "contour", 52, 16)
        for b in (self.btn_gpx, self.btn_garder, self.btn_autre):
            ligne.add_widget(b)
        self.btn_partir = Bouton("Partir", self.demarrer, "signal", 64, 22)
        for w in (self.info, self.props, self.l_details, self.voies, self.l_revet, ligne, self.btn_partir):
            panneau.add_widget(w)
        col.add_widget(panneau)
        self.add_widget(col)
        self.actifs(False)

    def actifs(self, oui):
        for b in (self.btn_gpx, self.btn_garder, self.btn_partir):
            b.disabled = not oui
        self.btn_autre.disabled = self.calcul or self.itineraire is not None

    # --- génération ---
    def lancer(self, *_):
        """Depuis l'écran distance (ou « Autres boucles ») : départ, puis recherche en arrière-plan."""
        if self.calcul:
            return
        c, self.itineraire, self.retour_vers = self.app.creation, None, "distance"
        sport, dist = c["sport"], c["distance"]
        self.barre.titre.text = f"{'Vélo' if sport == 'velo' else 'Course'}, {nombre(dist / 1000)} km"
        self.res = None
        self.trace.coords, self.trace.autres, self.trace.zone = [], [], []
        self.props.clear_widgets()
        self.props.height, self.cartes = 0, []
        self.l_details.text = self.l_revet.text = ""
        self.voies.remplir([])
        self.actifs(False)
        if c["mode"] == "carte" and not c.get("point"):
            self.depart = None
            self.trace.centre = list(self.app.gps_pos or self.app.derniere_position() or [])
            self.trace.choix = self.point_choisi
            self.info.text = "Touche la carte pour placer ton départ"
            if not self.trace.centre:
                self.info.text = "Cherche un lieu (écran précédent) ou touche la carte pour placer ton départ"
            return
        self.trace.choix = None
        depart = c.get("point") if c["mode"] == "carte" else self.app.gps_pos
        if depart is None:
            self.info.text = "Position GPS pas encore connue : choisis un point ou cherche un lieu"
            return
        self.chercher(tuple(depart))

    def point_choisi(self, lat, lon):
        self.app.creation["point"] = (lat, lon)
        self.trace.choix = None
        self.chercher((lat, lon))

    def chercher(self, depart):
        c = self.app.creation
        self.depart = depart
        self.trace.depart = list(depart)
        self.trace.centre = list(depart)
        rayon = c["distance"] / (2 * 3.1416 * boucles.SPORTS[c["sport"]]["detour"])
        self.trace.rayon_vue = rayon * 2.4
        self.trace.zone = [depart[0], depart[1], rayon * 2]
        self.calcul = True
        self.actifs(False)
        self.info.text = f"Recherche de boucles de {nombre(c['distance'] / 1000)} km autour du départ…"
        threading.Thread(target=self._calcul, args=(depart, c["distance"], c["sport"], c.get("relief")),
                         daemon=True).start()

    def _calcul(self, depart, distance, sport, relief):
        try:
            res = boucles.generer(depart, distance, sport, self.app.moteur, relief=relief)
        except Exception as err:  # ne jamais laisser l'écran bloqué
            res = {"propositions": [], "message": str(err) or "La génération a échoué", "zone": None}
        Clock.schedule_once(lambda dt: self.afficher(res))

    def afficher(self, res):
        self.calcul = False
        self.res, self.choix_i = res, 0
        if res.get("zone"):
            z = res["zone"]
            self.trace.zone = [*z["centre"], z["rayon"]]
        if not res["propositions"]:
            self.info.text = res["message"] or "Aucune boucle trouvée"
            self.actifs(False)
            apparaitre(self.info)
            return
        self.props.clear_widgets()
        n = len(res["propositions"])
        self.cartes = []
        if n > 1:
            for i, p in enumerate(res["propositions"]):
                c = CarteBoucle("ABCDE"[i], p, lambda i=i: self.choisir(i))
                self.cartes.append(c)
                self.props.add_widget(c)
        self.props.height = dp(162) if n > 1 else 0
        self.choisir(0, animer=True)
        self.actifs(True)

    def choisir(self, i, animer=True):
        self.choix_i = i
        for j, c in enumerate(getattr(self, "cartes", [])):
            c.choisie(j == i)
        props, p = self.res["propositions"], self.res["propositions"][i]
        self.trace.autres = [q["coords"] for j, q in enumerate(props) if j != i]
        self.trace.tracer(p["coords"]) if animer else setattr(self.trace, "coords", p["coords"])
        cible = self.res.get("cible", p["distance"])
        ecart = (p["distance"] - cible) / cible * 100
        self.info.text = (f"{nombre(p['distance'] / 1000, 2)} km, {p['montee']:.0f} m de D+"
                          + (f"  ({ecart:+.0f} %)" if abs(ecart) >= 1 else ""))
        self.l_details.text = self.res.get("message") or phrase_voies(p["resume_voies"], p["distance"])
        rv = p["resume_voies"]
        self.voies.remplir([(rv["voies"][k], getattr(widgets, c)) for k, c in COULEURS_VOIES])
        r = rv["revetement"]
        tot = sum(r.values()) or 1
        self.l_revet.text = (f"Revêtu {round(r['revetu'] / tot * 100)} %, non revêtu {round(r['non_revetu'] / tot * 100)} %"
                             f", inconnu {round(r['inconnu'] / tot * 100)} %. Surface indiquée dans OpenStreetMap "
                             f"sur {round(rv['surface_connue'] * 100)} % du tracé.")
        if not self.itineraire:
            self.btn_garder.text = "Enregistrer"
        apparaitre(self.info)

    def proposition(self):
        if not self.res or not self.res["propositions"]:
            return None
        p = self.res["propositions"][self.choix_i]
        sport = self.res.get("sport") or self.app.creation["sport"]
        return {**boucles.alleger(p), "sport": sport,
                "nom": p.get("nom") or f"Boucle {nombre(p['distance'] / 1000)} km ({'vélo' if sport == 'velo' else 'course'})"}

    # --- une boucle déjà enregistrée ---
    def montrer_itineraire(self, it):
        self.itineraire, self.retour_vers = it, "historique"
        self.app.creation.update(sport=it["sport"], distance=it["distance"])
        self.barre.titre.text = it["nom"]
        res = {"propositions": [{**it, "montee": it.get("montee") or 0,
                                 "resume_voies": it.get("resume_voies") or boucles.resume_voies([])}],
               "sport": it["sport"], "cible": it["distance"], "message": "", "zone": None}
        self.trace.zone, self.trace.depart = [], []
        self.afficher(res)
        self.btn_garder.text = "Retirer des favoris" if it.get("favori") else "Favorite"
        self.app.aller("plan")

    # --- actions ---
    def gpx(self, *_):
        """GPX de l'itinéraire (le tracé prévu, sans heure ni performance) : télécharger ou partager."""
        from ui.widgets import choix
        if self.proposition():
            choix("GPX de la boucle", "Le tracé prévu, pour un compteur GPS, Strava (itinéraire) ou une autre app.",
                  [("Télécharger", lambda: self._gpx(False), "signal"), ("Partager", lambda: self._gpx(True), "contour")],
                  hauteur=dp(260))

    def _gpx(self, partager):
        p = self.proposition()
        nom = nom_itineraire(p["distance"], p["sport"])
        texte = gpx_itineraire(p["coords"], p["sport"], p["distance"], p["montee"], p.get("ele"), p["nom"])
        try:
            self.l_details.text = (self.app.partager_gpx if partager else self.app.exporter_gpx)(nom, texte)
        except Exception as err:
            self.l_details.text = f"{'Partage' if partager else 'Téléchargement'} impossible : {err}"

    def garder(self, *_):
        if self.itineraire:  # boucle déjà enregistrée : le bouton bascule « favorite »
            it = self.itineraire
            it["favori"] = not it.get("favori")
            self.app.itineraires.enregistrer(it)
            self.btn_garder.text = "Retirer des favoris" if it["favori"] else "Favorite"
            self.app.synchroniser_itineraire(it)
            return
        p = self.proposition()
        if not p:
            return
        it = {**p, "id": time.strftime("%Y%m%d-%H%M%S"), "cree": time.time(), "favori": False, "id_serveur": None}
        self.app.itineraires.enregistrer(it)
        self.btn_garder.text, self.btn_garder.disabled = "Enregistrée", True
        self.app.synchroniser_itineraire(it)

    def demarrer(self, *_):
        p = self.proposition()
        if not p:
            return
        if platform == "android":
            if not self.app.gps_pos or self.app.gps_age > 30:
                self.info.text = "Attends le signal GPS avant de partir"
                return
            if self.app.gps_prec and self.app.gps_prec > 30:
                self.info.text = f"GPS encore imprécis ({self.app.gps_prec:.0f} m) : attends un peu"
                return
        self.app.ecran_course.preparer({k: p[k] for k in ("coords", "ele", "distance", "montee", "sport", "nom", "hints")
                                        if k in p})
