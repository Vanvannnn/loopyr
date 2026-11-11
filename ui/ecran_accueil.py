"""Accueil (la carte autour de toi, ta semaine) puis la création d'une boucle en deux gestes :
le sport (vélo ou course), puis la distance et le départ."""
import os
import threading
import time

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.screenmanager import Screen
from kivy.uix.widget import Widget

from boucles import SPORTS, ErreurItineraire, chercher_lieu
from ui import widgets
from ui.carte import Trace, avec_zoom
from ui.logo import Symbole
from ui.widgets import (BRUME, FOND, FOND_2, MARQUE, SIGNAL, Bouton, Feuille, Pas, Segmente, apparaitre,
                        champ, echelle, fond, lab, liste_defilante, nombre, titre_ecran, unite)

MA_POSITION, SUR_LA_CARTE = "gps", "carte"
EMOJIS = os.path.join(os.path.dirname(__file__), "emoji")
TEXTES = {
    "velo": ("Je pars à vélo", "Crée une boucle adaptée au cyclisme, aux distances plus longues et aux routes et "
                               "pistes cyclables adaptées."),
    "course": ("Je pars courir", "Crée une boucle adaptée à la course à pied, aux chemins piétons, aux parcs et aux "
                                 "espaces agréables pour courir."),
}


def lire_distance(texte, sport):
    """Distance saisie (km, virgule acceptée) -> (mètres, None) ou (None, message)."""
    s = SPORTS[sport]
    try:
        km = float((texte or "").replace(",", "."))
    except ValueError:
        return None, "Distance invalide"
    if not s["mini"] <= km <= s["maxi"]:
        return None, f"Entre {s['mini']} et {s['maxi']} km pour le {s['nom']}"
    return km * 1000, None


class EcranAccueil(Screen):
    def __init__(self, app, **kw):
        super().__init__(name="accueil", **kw)
        self.app = app
        col = BoxLayout(orientation="vertical")
        self.trace = Trace()
        carte = avec_zoom(self.trace)
        marque = BoxLayout(size_hint=(None, None), size=(dp(132), dp(44)), spacing=dp(6),
                           padding=[dp(6), dp(4), dp(12), dp(4)], pos_hint={"x": 0.03, "top": 0.97})
        fond(marque, (*FOND[:3], 0.94), dp(12))
        # point pêche cerclé d'encre le jour (la pêche seule ne se voit pas sur le lin), plein la nuit
        self.symbole = Symbole(MARQUE, SIGNAL, MARQUE if widgets.theme == "jour" else SIGNAL,
                               size_hint=(None, None), size=(dp(36), dp(36)))
        marque.add_widget(self.symbole)
        marque.add_widget(lab("Loopy", 27, gras=True, chiffres=True))
        carte.add_widget(marque)
        carte.add_widget(Bouton("Ma position", lambda *_: app.actualiser_position(), "carte", 44, 15,
                                size_hint=(None, None), width=dp(124), pos_hint={"right": 0.97, "top": 0.97}))
        col.add_widget(carte)

        panneau = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(250),
                            padding=[dp(20), dp(14), dp(20), dp(16)], spacing=dp(6))
        fond(panneau, FOND)
        self.l_semaine = lab("", 44, gras=True, chiffres=True, size_hint_y=None, height=dp(52))
        self.l_resume = lab("", 15, BRUME, size_hint_y=None, height=dp(44))
        self.l_gps = lab("", 14, BRUME, size_hint_y=None, height=dp(38))
        self.btn = Bouton("Créer une boucle", lambda *_: app.aller("sport"), "signal", 68, 21)
        for w in (self.l_semaine, self.l_resume, self.l_gps, Widget(), self.btn):
            panneau.add_widget(w)
        col.add_widget(panneau)
        self.add_widget(col)
        self.bind(on_pre_enter=self.remplir)

    def on_enter(self, *_):
        if not self.app.logo_vu:  # une fois par lancement : la boucle du logo se trace
            self.app.logo_vu = True
            self.symbole.animer()

    def remplir(self, *_):
        from ui.ecran_profil import km_par_semaine
        acts = self.app.stockage.lister()
        semaine = km_par_semaine(acts, time.time(), 1)[0][1]
        self.l_semaine.text = f"{nombre(semaine)}{unite('km cette semaine', 18)}"
        n_it = len(self.app.itineraires.lister())
        if acts:
            a = acts[0]
            quoi = "Sortie vélo" if a.get("sport") == "velo" else "Course"
            self.l_resume.text = (f"Dernière sortie : {quoi.lower()} de {nombre(a['distance'] / 1000)} km. "
                                  f"{n_it} boucle{'s' if n_it > 1 else ''} enregistrée{'s' if n_it > 1 else ''}.")
        else:
            self.l_resume.text = "Pas encore de sortie : crée ta première boucle."

    def etat_gps(self, texte):
        self.l_gps.text = texte

    def position(self, lat, lon, cap):
        self.trace.cap = cap
        self.trace.moi = [lat, lon]
        if not self.trace.centre:
            self.trace.centre = [lat, lon]


class CarteSport(ButtonBehavior, BoxLayout):
    """Un grand choix : titre en Barlow, une phrase qui dit ce que le moteur va chercher."""

    def __init__(self, sport, action, **kw):
        super().__init__(orientation="vertical", padding=[dp(22), dp(18)], spacing=dp(6), **kw)
        titre, texte = TEXTES[sport]
        echelle(self)
        self._c = fond(self, FOND_2, dp(18))
        self.add_widget(Widget())
        # émoji en image (Noto Emoji, Apache 2.0) : la police de Kivy n'affiche pas les émojis couleur
        self.add_widget(Image(source=os.path.join(EMOJIS, f"{sport}.png"), size_hint=(None, None), size=(dp(48), dp(48)),
                              fit_mode="contain"))
        self.add_widget(lab(titre, 40, gras=True, chiffres=True, size_hint_y=None, height=dp(52)))
        self.add_widget(lab(texte, 16, BRUME, size_hint_y=None, height=dp(66), valign="top"))
        self.bind(state=lambda *_: setattr(self._c, "rgba", widgets.FOND_2 if self.state == "normal" else
                                           [v * 0.92 for v in widgets.FOND_2[:3]] + [1]),
                  on_release=lambda *_: action(sport))


class EcranSport(Screen):
    def __init__(self, app, **kw):
        super().__init__(name="sport", **kw)
        self.app = app
        col = BoxLayout(orientation="vertical", padding=[dp(20), dp(10), dp(20), dp(20)], spacing=dp(14))
        col.add_widget(lab("Tu pars comment ?", 40, gras=True, chiffres=True, size_hint_y=None, height=dp(64)))
        for sport in ("velo", "course"):
            col.add_widget(CarteSport(sport, self.choisir))
        self.add_widget(col)

    def choisir(self, sport):
        self.app.creation["sport"] = sport
        self.app.ecran_distance.preparer()
        self.app.aller("distance")


class EcranDistance(Screen):
    def __init__(self, app, **kw):
        super().__init__(name="distance", **kw)
        self.app, self.lieu, self.arrivee = app, None, None
        col = BoxLayout(orientation="vertical")
        self.barre = titre_ecran("", lambda *_: app.aller("sport", "retour"))
        col.add_widget(self.barre)
        sv, c = liste_defilante(10)
        c.padding = [dp(20), dp(4), dp(20), dp(20)]
        self.forme = Segmente((("boucle", "Une boucle"), ("trajet", "De A à B")), "boucle")
        self.question = lab("", 22, gras=True, size_hint_y=None, height=dp(60))
        self.pas = Pas("Distance", "km", 10, 1, 1, 100, decimales=1)
        self.puces = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        self.saisie = champ("Autre distance, en km", nombre_=True)
        self.saisie.bind(text=self._saisie)
        self.relief = Segmente((("", "Peu importe"), ("plat", "Plat"), ("vallonne", "Vallonné")), "")
        self.depart = Segmente(((MA_POSITION, "De ma position"), (SUR_LA_CARTE, "D'un point choisi")), MA_POSITION)
        self.l_depart = lab("", 15, BRUME, size_hint_y=None, height=dp(40))
        cherche, self.recherche = self._recherche("Ou cherche une ville, une adresse", "depart")
        cherche_b, self.recherche_b = self._recherche("Ville, adresse, lieu…", "arrivee")
        self.l_arrivee = lab("", 15, BRUME, size_hint_y=None, height=dp(40))
        self.l_erreur = lab("", 15, widgets.ALERTE, gras=True, size_hint_y=None, height=dp(24))
        # ce qui ne vaut que pour une boucle (distance, relief) ou que pour un trajet (arrivée), échangé au choix
        self.bloc_boucle, self.bloc_trajet = (BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(10))
                                              for _ in range(2))
        for b, ws in ((self.bloc_boucle, (self.pas, self.puces, self.saisie, lab("Relief", 17, gras=True,
                                          size_hint_y=None, height=dp(30)), self.relief)),
                      (self.bloc_trajet, (lab("Arrivée", 17, gras=True, size_hint_y=None, height=dp(30)),
                                          self.l_arrivee, cherche_b))):
            b.bind(minimum_height=b.setter("height"))
            for w in ws:
                b.add_widget(w)
        for w in (self.forme, self.question, self.bloc_boucle, lab("Départ", 17, gras=True, size_hint_y=None,
                  height=dp(30)), self.depart, self.l_depart, cherche, self.l_erreur):
            c.add_widget(w)
        self.contenu = c
        col.add_widget(sv)
        bas = BoxLayout(size_hint_y=None, height=dp(92), padding=[dp(20), dp(10), dp(20), dp(12)])
        fond(bas, FOND)
        self.btn_generer = Bouton("", self.generer, "signal", 70, 21)
        bas.add_widget(self.btn_generer)
        col.add_widget(bas)
        self.add_widget(col)
        self.depart.bind(choix=lambda *_: self.maj_depart())
        self.forme.bind(choix=lambda *_: self.maj_forme())
        self.maj_forme()

    def _recherche(self, indice, cible):
        ligne = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(8))
        saisie = champ(indice)
        ligne.add_widget(saisie)
        ligne.add_widget(Bouton("Chercher", lambda *_: self.chercher(saisie, cible), "contour", 52, 16,
                                size_hint_x=None, width=dp(110)))
        return ligne, saisie

    def maj_forme(self):
        trajet = self.forme.choix == "trajet"
        ancien, nouveau = (self.bloc_boucle, self.bloc_trajet) if trajet else (self.bloc_trajet, self.bloc_boucle)
        if ancien.parent:
            i = self.contenu.children.index(ancien)
            self.contenu.remove_widget(ancien)
            self.contenu.add_widget(nouveau, index=i)
        self.question.text = "Où veux-tu aller ?" if trajet else "Quelle distance souhaites-tu parcourir ?"
        self.btn_generer.text = "Trouver mes itinéraires" if trajet else "Générer mes boucles"
        self.l_erreur.text = ""
        self.maj_depart()

    def preparer(self):
        sport = self.app.creation["sport"]
        s = SPORTS[sport]
        self.barre.titre.text = "À vélo" if sport == "velo" else "En courant"
        prefs = self.app.reglages.get("preferences", {})
        defaut = prefs.get(f"distance_{sport}") or (30 if sport == "velo" else 10)
        self.pas.pas = 1 if sport == "velo" else 0.5
        self.pas.mini, self.pas.maxi = s["mini"], s["maxi"]
        self.pas.valeur = defaut
        self.puces.clear_widgets()
        for km in s["suggestions"]:
            self.puces.add_widget(Bouton(f"{km} km", lambda b, k=km: self._puce(k), "contour", 44, 15))
        self.saisie.text = ""
        self.l_erreur.text = ""
        self.maj_forme()

    def _puce(self, km):
        self.saisie.text = ""
        self.pas.valeur = km

    def _saisie(self, *_):
        d, _ = lire_distance(self.saisie.text, self.app.creation["sport"])
        if d:
            self.pas.valeur = round(d / 1000, 1)

    def maj_depart(self):
        self.l_arrivee.text = (f"Arrivée : {self.arrivee[0]}" if self.arrivee else
                               "Cherche l'arrivée, ou tu la toucheras sur la carte.")
        if self.lieu and self.depart.choix == SUR_LA_CARTE:
            self.l_depart.text = f"Départ : {self.lieu[0]}"
        elif self.depart.choix == SUR_LA_CARTE:
            self.l_depart.text = "Tu toucheras la carte pour placer ton départ."
        elif self.app.gps_pos:
            self.l_depart.text = "Départ : ta position actuelle."
        else:
            self.l_depart.text = "Position pas encore connue : choisis un point ou cherche un lieu."

    def chercher(self, saisie, cible):
        q = saisie.text.strip()
        if len(q) < 2:
            return
        self.l_erreur.text = ""
        (self.l_arrivee if cible == "arrivee" else self.l_depart).text = "Recherche…"

        def fil():
            try:
                res = chercher_lieu(q)
            except ErreurItineraire as e:
                res = str(e)
            Clock.schedule_once(lambda dt: self._resultats(res, cible))
        threading.Thread(target=fil, daemon=True).start()

    def _resultats(self, res, cible):
        if isinstance(res, str) or not res:
            self.l_erreur.text = res if isinstance(res, str) else "Aucun lieu trouvé"
            self.maj_depart()
            return
        f = Feuille("Choisis le lieu", dp(120) + dp(64) * len(res))
        for nom, lat, lon in res:
            court = ", ".join(nom.split(", ")[:3])
            f.ajouter(Bouton(court, lambda b, n=court, la=lat, lo=lon: f.fermer(lambda: self._lieu(n, la, lo, cible)),
                             "contour", 56, 15, shorten=True, shorten_from="right"))
        f.ouvrir()

    def _lieu(self, nom, lat, lon, cible="depart"):
        if cible == "arrivee":
            self.arrivee = (nom, lat, lon)
        else:
            self.lieu = (nom, lat, lon)
            self.depart.choix = SUR_LA_CARTE
        self.maj_depart()

    def generer(self, *_):
        sport = self.app.creation["sport"]
        point = (self.lieu[1], self.lieu[2]) if (self.lieu and self.depart.choix == SUR_LA_CARTE) else None
        if self.forme.choix == "trajet":
            self.app.creation.update(forme="trajet", mode=self.depart.choix, point=point,
                                     arrivee=self.arrivee[1:] if self.arrivee else None)
            self.app.ecran_plan.lancer()
            self.app.aller("plan")
            return
        texte = self.saisie.text.strip() or str(self.pas.valeur)
        distance, err = lire_distance(texte, sport)
        if err:
            self.l_erreur.text = err
            apparaitre(self.l_erreur)
            return
        self.app.creation.update(forme="boucle", distance=distance, relief=self.relief.choix or None,
                                 mode=self.depart.choix, point=point)
        self.app.ecran_plan.lancer()
        self.app.aller("plan")
