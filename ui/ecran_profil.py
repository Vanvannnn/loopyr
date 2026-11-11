"""L'historique : les activités réellement faites, les boucles enregistrées et favorites ; le détail d'une
activité (tracé, splits, GPX de l'activité, envoi vers Strava, visibilité)."""
import threading
import time

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.graphics import Color, Line, Rectangle, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.properties import NumericProperty
from kivy.uix.widget import Widget

from course import fmt_allure
from gpx import exportable, gpx
from ui.carte import Trace, avec_zoom
from ui.ecran_course import chrono
from compte import ErreurCompte
from ui.widgets import (BRUME, ENCRE, FOND, FOND_2, ROUTE, TRACE, Bouton, Croissance, Feuille, Segmente, Splits, apparaitre,
                        champ, echelle, confirmer, desarmer, fond, hexa_de, lab, nombre, unite)

JOURS = ("lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim.")
MOIS = ("janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc.")
SEMAINE = 7 * 86400


def allure_moy(act):
    return fmt_allure(act["distance"] / act["duree"]) if act.get("duree") else "--:--"


def rythme(act):
    """Allure (min/km) en course, vitesse moyenne (km/h) à vélo."""
    if act.get("sport") == "velo":
        return f"{nombre(act['distance'] / act['duree'] * 3.6) if act.get('duree') else '--'} km/h"
    return f"{allure_moy(act)} /km"


def debut(act):
    """Heure de départ (epoch), y compris pour les courses d'avant, qui n'avaient que la date."""
    if act.get("debut"):
        return act["debut"]
    try:
        return time.mktime(time.strptime(act["date"], "%Y-%m-%d %H:%M"))
    except (KeyError, ValueError):
        return 0


def date_fr(act):
    t = time.localtime(debut(act))
    return f"{JOURS[t.tm_wday]} {t.tm_mday} {MOIS[t.tm_mon - 1]}, {t.tm_hour}h{t.tm_min:02d}"


def duree_longue(s):
    h, m = int(s // 3600), int(s % 3600 // 60)
    return f"{h} h {m:02d}" if h else f"{m} min"


def lundi(t):
    """Début (epoch, minuit local) de la semaine de t."""
    j = time.localtime(t)
    return time.mktime((j.tm_year, j.tm_mon, j.tm_mday - j.tm_wday, 0, 0, 0, 0, 0, -1))


def km_par_semaine(acts, maintenant, n=10):
    """Les n dernières semaines, de la plus ancienne à celle en cours : [(lundi, km)]."""
    fin = lundi(maintenant)
    semaines = [lundi(fin - i * SEMAINE + 3 * 86400) for i in range(n - 1, -1, -1)]  # +3 j : changement d'heure
    km = dict.fromkeys(semaines, 0.0)
    for a in acts:
        l = lundi(debut(a))
        if l in km:
            km[l] += a["distance"] / 1000
    return list(km.items())


class Semaines(BoxLayout):
    """Histogramme des km par semaine : barres encre sur filet, la semaine en cours en sauge.
    Les barres poussent depuis le filet à chaque arrivée sur l'écran."""

    def __init__(self, **kw):
        super().__init__(orientation="vertical", size_hint_y=None, height=dp(150), spacing=dp(4), **kw)
        self.barres = Croissance()
        self.dates = BoxLayout(size_hint_y=None, height=dp(18))
        self.add_widget(self.barres)
        self.add_widget(self.dates)
        self.valeurs = []
        self.barres.bind(pos=self.dessiner, size=self.dessiner, pousse=self.dessiner)

    def remplir(self, valeurs):
        self.valeurs = valeurs
        self.dates.clear_widgets()
        for i, (l, _) in enumerate(valeurs):
            t = time.localtime(l)
            pair = (len(valeurs) - 1 - i) % 2 == 0  # une date sur deux, en finissant par la semaine en cours
            self.dates.add_widget(lab(f"{t.tm_mday}/{t.tm_mon}" if pair else "", 15, BRUME, chiffres=True,
                                      aligne="center"))
        self.barres.faire_pousser(0.8)

    def dessiner(self, *_):
        w = self.barres
        w.canvas.clear()
        if not self.valeurs:
            return
        n, haut = len(self.valeurs), max(km for _, km in self.valeurs) or 1
        larg = w.width / n
        with w.canvas:
            Color(*ROUTE)
            Line(points=[w.x, w.y, w.right, w.y], width=dp(1))
            for i, (_, km) in enumerate(self.valeurs):
                Color(*(TRACE if i == n - 1 else ENCRE))
                retard = i / n * 0.35  # de gauche à droite, la semaine en cours en dernier
                p = max(0.0, min(1.0, (w.pousse - retard) / (1 - retard)))
                h = max(dp(2), (w.height - dp(4)) * km / haut) * p if km else 0
                RoundedRectangle(pos=(w.x + i * larg + larg * 0.18, w.y), size=(larg * 0.64, h),
                                 radius=[dp(3), dp(3), 0, 0])


class Ligne(ButtonBehavior, BoxLayout):
    """Une ligne de liste : deux lignes de texte à gauche, la distance en gros à droite."""

    def __init__(self, haut, bas, km, action, **kw):
        super().__init__(size_hint_y=None, height=dp(74), padding=[0, dp(10)], **kw)
        echelle(self)  # avant le fond : la ligne entière grandit à son arrivée
        with self.canvas.before:
            self._c = Color(*FOND)
            self._fond = Rectangle()
            Color(*FOND_2)
            self._filet = Rectangle()
        self.bind(pos=self._maj, size=self._maj, state=self._maj, on_release=lambda *_: action())
        gauche = BoxLayout(orientation="vertical")
        gauche.add_widget(lab(haut, 17, gras=True, shorten=True, shorten_from="right"))
        gauche.add_widget(lab(bas, 17, BRUME, chiffres=True))
        self.add_widget(gauche)
        self.add_widget(lab(f"{nombre(km, 2)}{unite('km', 15)}", 34, gras=True, chiffres=True,
                            aligne="right", size_hint_x=0.5))

    def _maj(self, *_):
        self._c.rgba = FOND_2 if self.state == "down" else FOND
        self._fond.pos, self._fond.size = (self.x - dp(20), self.y), (self.width + dp(40), self.height)
        self._filet.pos, self._filet.size = (self.x, self.y), (self.width, dp(1))


def barre_titre(titre, retour):
    b = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(6))
    b.add_widget(Bouton("‹ Retour", retour, "discret", 56, 17, size_hint_x=None, width=dp(104)))
    l = lab(titre, 18, gras=True, aligne="right")
    b.add_widget(l)
    b.titre = l
    return b


class EcranHistorique(Screen):
    compte = NumericProperty(0)  # total de km affiché, qui défile jusqu'au vrai total

    def __init__(self, app, **kw):
        super().__init__(name="historique", **kw)
        self.app = app
        col = BoxLayout(orientation="vertical", padding=[dp(20), dp(8), dp(20), 0], spacing=dp(6))
        self.onglet = Segmente((("activites", "Activités"), ("boucles", "Boucles"), ("favoris", "Favorites")),
                               "activites")
        self.onglet.bind(choix=self.remplir)
        col.add_widget(self.onglet)
        sv = ScrollView(do_scroll_x=False)
        self.contenu = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(6))
        self.contenu.bind(minimum_height=self.contenu.setter("height"))
        self.l_totaux = lab("", 80, gras=True, chiffres=True, size_hint_y=None, height=dp(88))
        self.l_soustitre = lab("", 16, BRUME, size_hint_y=None, height=dp(24))
        self.l_semaine = lab("", 16, gras=True, size_hint_y=None, height=dp(44))
        self.semaines = Semaines()
        self.entete = [self.l_totaux, self.l_soustitre, self.l_semaine, self.semaines, Widget(size_hint_y=None, height=dp(14))]
        self.liste = BoxLayout(orientation="vertical", size_hint_y=None)
        self.liste.bind(minimum_height=self.liste.setter("height"))
        sv.add_widget(self.contenu)
        col.add_widget(sv)
        self.add_widget(col)
        self.bind(on_pre_enter=self.remplir)

    def remplir(self, *_):
        self.contenu.clear_widgets()
        self.liste.clear_widgets()
        if self.onglet.choix == "activites":
            for w in self.entete:
                self.contenu.add_widget(w)
            self.activites()
        else:
            self.boucles(self.onglet.choix == "favoris")
        self.contenu.add_widget(self.liste)
        for i, ligne in enumerate(self.liste.children[::-1][:8]):  # les premières arrivent l'une après l'autre
            ligne.opacity = 0
            Clock.schedule_once(lambda dt, l=ligne: apparaitre(l, 0.3, 0.97), 0.2 + 0.05 * i)

    def activites(self):
        acts = self.app.stockage.lister()
        km = sum(a["distance"] for a in acts) / 1000
        temps = sum(a.get("duree") or 0 for a in acts)
        dplus = sum(a.get("denivele") or 0 for a in acts)
        Animation.cancel_all(self, "compte")
        self.compte = 0
        Animation(compte=km, d=0.8, t="out_cubic").start(self)
        n = len(acts)
        self.l_soustitre.text = (f"{n} sortie{'s' if n > 1 else ''}, {duree_longue(temps)} en mouvement, "
                                 f"{dplus:.0f} m de D+")
        semaines = km_par_semaine(acts, time.time())
        self.semaines.remplir(semaines)
        self.l_semaine.text = f"Cette semaine : [color={hexa_de(TRACE)}]{nombre(semaines[-1][1])} km[/color]"
        if not acts:
            self.liste.add_widget(lab("Pas encore de sortie. Une boucle générée n'en est pas une : pars, "
                                      "le GPS enregistre ta sortie.", 17, BRUME, size_hint_y=None, height=dp(70)))
            self.liste.add_widget(Bouton("Créer une boucle", lambda *_: self.app.aller("sport"), "encre", 64))
        for a in acts:
            sport = "Vélo" if a.get("sport") == "velo" else "Course"
            haut = a.get("nom") or f"{sport}, {date_fr(a)}"
            bas = f"{date_fr(a)} · {chrono(a.get('duree') or 0)} · {rythme(a)}" if a.get("nom") else \
                f"{chrono(a.get('duree') or 0)}  {rythme(a)}"
            self.liste.add_widget(Ligne(haut, bas,
                                        a["distance"] / 1000, lambda id_=a["id"]: self.app.ecran_detail.ouvrir(id_)))

    def boucles(self, favoris):
        its = [i for i in self.app.itineraires.lister() if i.get("favori") or not favoris]
        if not its:
            self.liste.add_widget(lab("Aucune boucle favorite. Ouvre une boucle et touche « Favorite »." if favoris else
                                      "Aucune boucle enregistrée. Après une génération, touche « Enregistrer ».",
                                      17, BRUME, size_hint_y=None, height=dp(70)))
        for i in its:
            bas = f"{'Vélo' if i['sport'] == 'velo' else 'Course'}, {(i.get('montee') or 0):.0f} m D+" + \
                  (", favorite" if i.get("favori") else "")
            self.liste.add_widget(Ligne(i["nom"], bas, i["distance"] / 1000, lambda id_=i["id"]: self.ouvrir_boucle(id_)))

    def ouvrir_boucle(self, id_):
        self.app.ecran_plan.montrer_itineraire(self.app.itineraires.charger(id_))

    def on_compte(self, *_):
        self.l_totaux.text = f"{nombre(self.compte)}{unite('km', 22)}"


IMPORT_STRAVA = ("Le GPX de ta sortie est dans Téléchargements/Loopy.\n\n"
                 "1. Touche « Ouvrir strava.com » ci-dessous et connecte-toi.\n"
                 "2. Sur téléphone, menu du navigateur > « Version pour ordinateur » si la page d'import ne "
                 "s'affiche pas.\n"
                 "3. « Choisir un fichier » : Téléchargements > Loopy > le fichier loopy-….gpx.\n"
                 "4. Vérifie le nom et le sport, puis « Enregistrer et afficher ».\n\n"
                 "L'app mobile Strava ne sait pas importer un fichier : c'est le site qui le fait. "
                 "Ce n'est pas un envoi automatique : Strava le réserve aux applications validées.")
URL_IMPORT_STRAVA = "https://www.strava.com/upload/select"
RESSENTIS = {"facile": "facile", "bien": "bien", "dur": "dur", "epuisant": "épuisant"}


VISIBILITES = (("prive", "Moi seul"), ("abonnes", "Abonnés"), ("public", "Tout le monde"))


class EcranDetail(Screen):
    def __init__(self, app, **kw):
        super().__init__(name="detail", **kw)
        self.app, self.act = app, None
        col = BoxLayout(orientation="vertical")
        self.barre = barre_titre("", lambda *_: app.aller("historique", "retour"))
        self.barre.padding = [dp(20), dp(4), dp(20), 0]
        self.trace = Trace()
        panneau = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(560),
                            padding=[dp(20), dp(8), dp(20), dp(14)], spacing=dp(6))
        fond(panneau, FOND)
        self.l_nom = lab("", 20, gras=True, size_hint_y=None, height=dp(28), shorten=True, shorten_from="right")
        self.l_titre = lab("", 60, gras=True, chiffres=True, size_hint_y=None, height=dp(64))
        chiffres = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(12))
        self.cases, self.legendes = [], []
        for legende, couleur in (("temps", None), ("allure, min/km", None), ("dénivelé", TRACE)):
            c = BoxLayout(orientation="vertical")
            v = lab("", 30, couleur or ENCRE, gras=True, chiffres=True)
            c.add_widget(v)
            l = lab(legende, 13, BRUME, size_hint_y=None, height=dp(18))
            c.add_widget(l)
            self.cases.append(v)
            self.legendes.append(l)
            chiffres.add_widget(c)
        self.l_plus = lab("", 14, BRUME, size_hint_y=None, height=dp(20))
        self.l_desc = lab("", 15, size_hint_y=None, height=dp(0), valign="top")
        sv = ScrollView(do_scroll_x=False)
        self.splits = Splits()
        sv.add_widget(self.splits)
        self.l_info = lab("", 14, BRUME, size_hint_y=None, height=dp(40))
        self.visibilite = Segmente(VISIBILITES, "abonnes", hauteur=46)
        self.visibilite.bind(choix=self.changer_visibilite)
        gpx_l = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(8))
        self.btn_gpx = Bouton("GPX", self.exporter, "encre", 56, 16)  # téléchargement direct + notification
        gpx_l.add_widget(self.btn_gpx)
        bas = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(8))
        self.btn_strava = Bouton("Importer sur Strava", self.strava, "contour", 56, 15)
        self.btn_modif = Bouton("Modifier", self.modifier, "contour", 56, 15, size_hint_x=0.6)
        self.btn_suppr = Bouton("Supprimer", self.supprimer, "contour", 56, 15, size_hint_x=0.7)
        for b in (self.btn_strava, self.btn_modif, self.btn_suppr):
            bas.add_widget(b)
        for w in (self.l_nom, self.l_titre, chiffres, self.l_plus, self.l_desc, sv, self.l_info, self.visibilite,
                  gpx_l, bas):
            panneau.add_widget(w)
        for w in (self.barre, avec_zoom(self.trace), panneau):
            col.add_widget(w)
        self.add_widget(col)

    def ouvrir(self, id_, sens="avant"):
        a = self.act = self.app.stockage.charger(id_)
        velo = a.get("sport") == "velo"
        self.barre.titre.text = ("Vélo, " if velo else "Course, ") + date_fr(a)
        self.l_nom.text = a.get("nom") or ("Sortie vélo" if velo else "Course")
        plus = []
        if a.get("denivele_neg") is not None:
            plus.append(f"D− {a['denivele_neg']:.0f} m")
        if a.get("vmax"):
            plus.append(f"vitesse max {nombre(a['vmax'] * 3.6)} km/h")
        if a.get("ressenti") in RESSENTIS:
            plus.append(f"ressenti : {RESSENTIS[a['ressenti']]}")
        self.l_plus.text = " · ".join(plus)
        self.l_desc.text = a.get("description") or ""
        self.l_desc.height = dp(44) if self.l_desc.text else 0
        self.l_titre.text = f"{nombre(a['distance'] / 1000, 2)}{unite('km', 22)}"
        self.legendes[1].text = "vitesse moy., km/h" if velo else "allure, min/km"
        moy = rythme(a).replace(" /km", "").replace(" km/h", "")  # l'unité est dans la légende
        for case, texte in zip(self.cases, (chrono(a.get("duree") or 0), moy,
                                            f"{a.get('denivele') or 0:.0f}{unite('m', 14)}")):
            case.text = texte
        pts = [(p[1], p[2]) for seg in a.get("segments") or () for p in seg] or a.get("trace") or []
        pas = max(1, len(pts) // 1500)
        self.trace.tracer([tuple(p) for p in pts[::pas]], 0.9)
        self.splits.remplir(a.get("splits") or ())
        self.btn_gpx.disabled = not exportable(a)
        self._charge = True
        self.visibilite.choix = a.get("visibilite") or self.app.reglages.get("visibilite", "abonnes")
        self._charge = False
        self.visibilite.disabled = not self.app.compte.connecte
        if not exportable(a):
            self.l_info.text = "Sortie d'avant la mise à jour, sans heure par point : pas d'export"
        elif not self.app.compte.connecte:
            self.l_info.text = "Connecte-toi (Profil) pour la partager avec la communauté."
        else:
            self.l_info.text = "Synchronisée avec ton compte." if a.get("id_serveur") else "Pas encore synchronisée."
        desarmer(self.btn_suppr)
        self.btn_strava.disabled = not exportable(a)
        self.strava_direct = False
        self.btn_strava.text = "Importer sur Strava"
        if self.app.compte.connecte:  # l'envoi direct n'est proposé que s'il marche vraiment pour ce compte
            self._en_fond(self.app.compte.etat_strava, self._etat_strava)
        self.app.aller("detail", sens)

    def _etat_strava(self, r):
        if isinstance(r, dict) and r.get("configure") and r.get("connecte"):
            self.strava_direct = True
            self.btn_strava.text = "Envoyer à Strava"

    def exporter(self, *_):
        """Téléchargement direct du GPX de l'activité (points horodatés), sans passer par le partage."""
        a = self.act
        try:
            self.l_info.text = self.app.exporter_gpx(f"loopy-{a['id']}.gpx", gpx(a))
            return True
        except Exception as err:
            self.l_info.text = f"Téléchargement impossible : {err}"
            return False

    def modifier(self, *_):
        """Nom, ressenti et description, modifiables à tout moment."""
        from ui.ecran_fin import RESSENTIS as CHOIX
        a = self.act
        f = Feuille("Modifier la sortie", dp(470))
        nom = champ("Nom de la sortie", a.get("nom") or "")
        res = Segmente(CHOIX, a.get("ressenti") or "", hauteur=50)
        desc = champ("Description ou ressenti (facultatif)", a.get("description") or "", multiline=True,
                     height=dp(100))

        def valider(*_):
            a["nom"] = nom.text.strip()[:100] or a.get("nom")
            a["ressenti"] = res.choix or None
            a["description"] = desc.text.strip()[:2000]
            self.app.stockage.enregistrer(a)
            f.fermer()
            self.ouvrir(a["id"], "avant")
            if self.app.compte.connecte and a.get("id_serveur"):
                self._en_fond(lambda: self.app.compte.modifier_activite(
                    a["id_serveur"], nom=a["nom"], description=a["description"], ressenti=a["ressenti"]),
                    lambda r: setattr(self.l_info, "text", str(r) if isinstance(r, Exception) else "Modifiée."))
            else:
                self.app.synchroniser_activite(a)
        for w in (nom, res, desc, Bouton("Enregistrer", valider, "signal", 60, 18)):
            f.ajouter(w)
        f.ouvrir()

    def _en_fond(self, travail, fini):
        """travail() dans un fil (réseau), puis fini(résultat ou ErreurCompte) dans le fil de Kivy."""
        def fil():
            try:
                r = travail()
            except (ErreurCompte, KeyError, TypeError) as e:
                r = e if isinstance(e, ErreurCompte) else ErreurCompte("Réponse inattendue du serveur")
            Clock.schedule_once(lambda dt: fini(r))
        threading.Thread(target=fil, daemon=True).start()

    def _id_serveur(self):
        """L'activité doit exister sur le serveur avant d'être partagée ou envoyée : on l'y met si besoin."""
        a = self.act
        if not a.get("id_serveur"):
            r = self.app.compte.envoyer_activite(a)
            a["id_serveur"] = r["id"]  # (KeyError -> message, voir _en_fond)
            self.app.stockage.enregistrer(a)
        return a["id_serveur"]

    def changer_visibilite(self, _, valeur):
        if getattr(self, "_charge", False) or not self.act or not self.app.compte.connecte:
            return
        self.act["visibilite"] = valeur
        self.app.stockage.enregistrer(self.act)
        nom = dict(VISIBILITES)[valeur].lower()
        self._en_fond(lambda: self.app.compte.modifier_activite(self._id_serveur(), visibilite=valeur),
                      lambda r: setattr(self.l_info, "text", r if isinstance(r, Exception) else f"Visible par : {nom}"))

    def strava(self, *_):
        if not self.strava_direct:  # pas d'envoi direct actif pour ce compte : l'import, qui marche toujours
            return self.strava_manuel()
        self.btn_strava.disabled = True
        self.l_info.text = "Envoi à Strava…"
        self._en_fond(lambda: self.app.compte.envoyer_strava(self._id_serveur()), self._strava_suite)

    def _strava_suite(self, r, essais=0):
        if isinstance(r, ErreurCompte):
            self.btn_strava.disabled = False
            if r.code == 503 or "non connecté" in str(r):  # envoi direct non activé : import à la main
                self.strava_manuel()
            else:
                self.l_info.text = str(r)
            return
        if r["statut"] == "pret":
            self.l_info.text = "Sur Strava : c'est fait."
            self.btn_strava.text = "Sur Strava"
            return
        if r["statut"] == "erreur":
            self.l_info.text = f"Strava a refusé : {r['erreur']}"
            self.btn_strava.disabled = False
            return
        if essais >= 30:
            self.l_info.text = "Strava traite encore l'activité : regarde dans quelques minutes."
            self.btn_strava.disabled = False
            return
        self.l_info.text = "Strava traite l'activité…"  # traitement asynchrone : on suit toutes les 2 s
        id_s = self.act["id_serveur"]
        Clock.schedule_once(lambda dt: self._en_fond(lambda: self.app.compte.suivre_strava(id_s),
                                                     lambda r2: self._strava_suite(r2, essais + 1)), 2)

    def strava_manuel(self):
        """Sans envoi direct : le GPX est téléchargé, puis on l'importe sur strava.com (gratuit, sans validation)."""
        from capteurs.partage import ouvrir_url
        if not self.exporter():
            return
        f = Feuille("Importer sur Strava", dp(560))
        f.ajouter(lab(IMPORT_STRAVA, 16, size_hint_y=None, height=dp(330), valign="top"))
        ligne = BoxLayout(size_hint_y=None, height=dp(60), spacing=dp(8))
        ligne.add_widget(Bouton("Ouvrir strava.com", lambda *_: (ouvrir_url(URL_IMPORT_STRAVA), f.fermer()),
                                "signal", 60, 17))
        ligne.add_widget(Bouton("Fermer", lambda *_: f.fermer(), "contour", 60, 17, size_hint_x=0.5))
        f.ajouter(ligne)
        f.ouvrir()

    def supprimer(self, btn):
        def go():
            self.app.stockage.supprimer(self.act["id"])
            self.app.aller("historique", "retour")
        confirmer(btn, "Supprimer ?", go)
