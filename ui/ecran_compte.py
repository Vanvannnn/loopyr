"""Profil (compte Loopy, préférences, confidentialité, Strava, thème) et Communauté (fil des personnes suivies,
boucles partagées). Sans compte, l'app reste entière : seules ces fonctions sociales le demandent."""
import threading
import time

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import Screen

from capteurs.partage import ouvrir_url
from compte import ErreurCompte
from ui import widgets
from ui.widgets import (BRUME, Bouton, Segmente, champ, confirmer, lab, liste_defilante, nombre, titre_ecran)
from ui.ecran_profil import VISIBILITES, rythme


def en_fond(travail, fini):
    """travail() dans un fil (réseau), puis fini(résultat ou ErreurCompte) dans le fil de Kivy."""
    def fil():
        try:
            r = travail()
        except ErreurCompte as e:
            r = e
        Clock.schedule_once(lambda dt: fini(r))
    threading.Thread(target=fil, daemon=True).start()


def section(texte):
    return lab(texte, 26, gras=True, chiffres=True, size_hint_y=None, height=dp(46))


class EcranProfil(Screen):
    def __init__(self, app, **kw):
        super().__init__(name="profil", **kw)
        self.app, self.moi = app, None
        col = BoxLayout(orientation="vertical")
        self.barre = titre_ecran("Profil")
        col.add_widget(self.barre)
        sv, self.c = liste_defilante(10)
        self.c.padding = [dp(20), dp(4), dp(20), dp(28)]
        col.add_widget(sv)
        self.add_widget(col)
        self.bind(on_pre_enter=lambda *_: self.remplir())

    def message(self, texte):
        self.l_msg.text = texte

    def remplir(self):
        self.c.clear_widgets()
        self.l_msg = lab("", 15, widgets.TRACE, gras=True, size_hint_y=None, height=dp(44))
        if self.app.compte.connecte:
            self.c.add_widget(lab("Chargement du profil…", 16, BRUME, size_hint_y=None, height=dp(30)))
            en_fond(self.app.compte.moi, self._profil)
        else:
            self._connexion()

    # --- sans compte ---
    def _connexion(self):
        c = self.c
        c.add_widget(lab("Ton compte Loopy enregistre tes boucles et tes sorties, ouvre la communauté et "
                         "l'envoi vers Strava. Le même compte sert sur le site.", 16, BRUME,
                         size_hint_y=None, height=dp(66)))
        self.mode = Segmente((("connexion", "Se connecter"), ("inscription", "Créer un compte")), "connexion")
        self.nom = champ("Nom d'utilisateur (a-z, 0-9, _ . -)")
        self.email = champ("Adresse e-mail")
        self.mdp = champ("Mot de passe (8 caractères au moins)", motdepasse=True)
        self.btn = Bouton("Se connecter", self.valider, "encre", 60, 19)

        def changer(*_):
            inscr = self.mode.choix == "inscription"
            self.nom.disabled, self.nom.opacity, self.nom.height = not inscr, 1 if inscr else 0, dp(52) if inscr else 0
            self.btn.text = "Créer mon compte" if inscr else "Se connecter"
        self.mode.bind(choix=changer)
        for w in (self.mode, self.nom, self.email, self.mdp, self.l_msg, self.btn):
            c.add_widget(w)
        changer()
        c.add_widget(Bouton("Mot de passe oublié", lambda *_: self.ouvrir("/mot-de-passe.html"), "discret", 48, 15))
        self._reglages_app()

    def valider(self, *_):
        inscr = self.mode.choix == "inscription"
        nom, email, mdp = self.nom.text.strip().lower(), self.email.text.strip(), self.mdp.text
        self.btn.disabled = True
        self.message("Connexion…")
        travail = (lambda: self.app.compte.inscrire(nom, email, mdp)) if inscr else \
            (lambda: self.app.compte.connecter(email, mdp))

        def fini(r):
            self.btn.disabled = False
            if isinstance(r, ErreurCompte):
                self.message(str(r))
                return
            self.app.sauver_reglages(jeton=self.app.compte.jeton)
            self.app.synchroniser_tout()
            self.remplir()
        en_fond(travail, fini)

    # --- avec compte ---
    def _profil(self, r):
        self.c.clear_widgets()
        if isinstance(r, ErreurCompte):
            if not self.app.compte.connecte:  # session expirée
                self.app.sauver_reglages(jeton=None)
                return self.remplir()
            self.c.add_widget(lab(str(r), 16, widgets.ALERTE, size_hint_y=None, height=dp(60)))
            self.c.add_widget(Bouton("Réessayer", lambda *_: self.remplir(), "contour", 56))
            self._reglages_app()
            return
        self.moi, c = r, self.c
        self.barre.titre.text = r["nom"]
        self.app.sauver_reglages(preferences=r.get("preferences") or {}, visibilite=r["visibilite_activites"])
        ps = r["stats"]["par_sport"]
        resume = [f"{nombre(ps[s]['distance'] / 1000, 0)} km {'à vélo' if s == 'velo' else 'en courant'}"
                  for s in ("course", "velo") if s in ps]
        c.add_widget(lab(", ".join(resume) or "Pas encore de sortie synchronisée", 18, gras=True,
                         size_hint_y=None, height=dp(34)))
        c.add_widget(section("Toi"))
        self.bio = champ("Présentation", r.get("bio") or "", multiline=True, height=dp(88))
        self.sport = Segmente((("course", "Course à pied"), ("velo", "Vélo")), r.get("sport") or "course")
        c.add_widget(self.bio)
        c.add_widget(lab("Sport favori", 15, BRUME, size_hint_y=None, height=dp(24)))
        c.add_widget(self.sport)
        c.add_widget(section("Préférences de parcours"))
        prefs = r.get("preferences") or {}
        self.d_course = champ("Distance habituelle en course (km)", str(prefs.get("distance_course") or ""), nombre_=True)
        self.d_velo = champ("Distance habituelle à vélo (km)", str(prefs.get("distance_velo") or ""), nombre_=True)
        c.add_widget(self.d_course)
        c.add_widget(self.d_velo)
        c.add_widget(section("Confidentialité"))
        c.add_widget(lab("Qui voit mes nouvelles sorties", 15, BRUME, size_hint_y=None, height=dp(24)))
        self.vis = Segmente(VISIBILITES, r["visibilite_activites"])
        c.add_widget(self.vis)
        c.add_widget(lab("Masquer aux autres le début et la fin de mes tracés (300 m)", 15, BRUME,
                         size_hint_y=None, height=dp(40)))
        self.masque = Segmente((("1", "Oui"), ("0", "Non")), "1" if r["masquer_depart"] else "0")
        c.add_widget(self.masque)
        c.add_widget(self.l_msg)
        c.add_widget(Bouton("Enregistrer le profil", self.enregistrer, "encre", 60, 19))

        c.add_widget(section("Strava"))
        st = r["strava"]
        if not st["configure"]:
            c.add_widget(lab("Pour mettre une sortie sur Strava : ouvre-la dans Historique et touche « Vers Strava ». "
                             "Loopy enregistre son GPX et t'explique comment l'importer sur strava.com.", 15, BRUME,
                             size_hint_y=None, height=dp(66)))
        elif st["connecte"]:
            c.add_widget(lab(f"Relié au compte Strava de {st['athlete'] or 'ton compte'}. Envoie une sortie depuis "
                             "son détail (Historique).", 15, BRUME, size_hint_y=None, height=dp(44)))
        else:
            c.add_widget(lab("Relie Strava pour y envoyer tes sorties terminées. La page d'autorisation s'ouvre "
                             "dans le navigateur ; reviens ensuite ici.", 15, BRUME, size_hint_y=None, height=dp(62)))
            c.add_widget(Bouton("Relier mon compte Strava", self.relier_strava, "encre", 58, 18))
        c.add_widget(Bouton("Ouvrir mon espace sur le site", lambda *_: self.ouvrir("/espace.html"), "contour", 56, 17))
        c.add_widget(lab("Photo de profil, abonnements et suppression du compte : sur le site.", 14, BRUME,
                         size_hint_y=None, height=dp(40)))
        self._reglages_app()
        c.add_widget(Bouton("Se déconnecter", self.deconnecter, "contour", 56, 17))

    def enregistrer(self, *_):
        prefs = dict(self.moi.get("preferences") or {})
        for cle, w in (("distance_course", self.d_course), ("distance_velo", self.d_velo)):
            try:
                prefs[cle] = float(w.text.replace(",", ".")) if w.text.strip() else None
            except ValueError:
                return self.message("Distance invalide")
        champs = dict(bio=self.bio.text, sport=self.sport.choix, preferences=prefs,
                      visibilite_activites=self.vis.choix, masquer_depart=self.masque.choix == "1")
        self.message("Enregistrement…")

        def fini(r):
            if isinstance(r, ErreurCompte):
                return self.message(str(r))
            self.moi.update(r)
            self.app.sauver_reglages(preferences=prefs, visibilite=self.vis.choix)
            self.message("Profil enregistré")
        en_fond(lambda: self.app.compte.modifier(**champs), fini)

    def relier_strava(self, *_):
        def fini(r):
            if isinstance(r, ErreurCompte):
                return self.message(str(r))
            ouvrir_url(r)
            self.message("Autorise Loopy dans le navigateur, puis reviens : touche Profil pour actualiser.")
        en_fond(self.app.compte.lien_strava, fini)

    def deconnecter(self, btn):
        def go():
            en_fond(self.app.compte.deconnecter, lambda r: (self.app.sauver_reglages(jeton=None), self.remplir()))
        confirmer(btn, "Se déconnecter ?", go)

    def ouvrir(self, chemin):
        if self.app.compte.url:
            ouvrir_url(self.app.compte.url + chemin)
        else:
            self.message("Indique d'abord l'adresse du serveur Loopy (en bas).")

    # --- réglages de l'app (avec ou sans compte) ---
    def _reglages_app(self):
        c = self.c
        c.add_widget(section("L'app"))
        c.add_widget(Bouton("Thème jour" if widgets.theme == "nuit" else "Thème nuit",
                            lambda *_: self.app.changer_theme(), "contour", 56, 17))
        c.add_widget(lab("Adresse du serveur Loopy (déjà réglée ; à changer seulement pour un autre serveur)", 15, BRUME,
                         size_hint_y=None, height=dp(44)))
        self.url = champ("https://…", self.app.compte.url)
        c.add_widget(self.url)
        c.add_widget(lab("Moteur d'itinéraires (BRouter)", 15, BRUME, size_hint_y=None, height=dp(24)))
        self.moteur = champ("https://brouter.de/brouter", self.app.moteur.url)
        c.add_widget(self.moteur)
        self.l_reg = lab("", 14, BRUME, size_hint_y=None, height=dp(24))
        c.add_widget(self.l_reg)
        c.add_widget(Bouton("Enregistrer les adresses", self.adresses, "contour", 52, 16))

    def adresses(self, *_):
        url, moteur = self.url.text.strip().rstrip("/"), self.moteur.text.strip().rstrip("/")
        url = url or self.app.serveur_defaut  # champ vidé : retour au serveur Loopy officiel
        self.url.text = url
        for u in (url, moteur):
            if u and not u.startswith(("http://", "https://")):
                self.l_reg.text = "Une adresse commence par https://"
                return
        if url != self.app.compte.url:  # autre serveur : la session ne vaut plus
            self.app.compte.url, self.app.compte.jeton = url, None
        self.app.moteur.url = moteur or "https://brouter.de/brouter"
        self.app.moteur.ids.clear()  # nos profils sont à renvoyer au nouveau moteur
        self.app.sauver_reglages(serveur=url, moteur=self.app.moteur.url, jeton=self.app.compte.jeton)
        self.l_reg.text = "Adresses enregistrées"


class EcranCommunaute(Screen):
    def __init__(self, app, **kw):
        super().__init__(name="communaute", **kw)
        self.app = app
        col = BoxLayout(orientation="vertical", spacing=dp(6))
        col.add_widget(titre_ecran("Communauté"))
        self.onglet = Segmente((("fil", "Mon fil"), ("boucles", "Boucles partagées")), "fil")
        self.onglet.bind(choix=lambda *_: self.remplir())
        haut = BoxLayout(size_hint_y=None, height=dp(60), padding=[dp(20), 0, dp(20), dp(8)])
        haut.add_widget(self.onglet)
        col.add_widget(haut)
        sv, self.c = liste_defilante(4)
        self.c.padding = [dp(20), 0, dp(20), dp(20)]
        col.add_widget(sv)
        self.add_widget(col)
        self.bind(on_pre_enter=lambda *_: self.remplir())

    def remplir(self):
        c = self.c
        c.clear_widgets()
        if not self.app.compte.connecte:
            c.add_widget(lab("Connecte-toi pour suivre d'autres sportifs, voir leurs sorties et les boucles qu'ils "
                             "partagent.", 17, BRUME, size_hint_y=None, height=dp(70)))
            c.add_widget(Bouton("Me connecter", lambda *_: self.app.aller("profil"), "encre", 60))
            return
        c.add_widget(lab("Chargement…", 16, BRUME, size_hint_y=None, height=dp(30)))
        fil = self.onglet.choix == "fil"
        en_fond(self.app.compte.fil if fil else self.app.compte.itineraires_partages,
                lambda r: self._liste(r, fil))

    def _liste(self, r, fil):
        c = self.c
        c.clear_widgets()
        if isinstance(r, ErreurCompte):
            c.add_widget(lab(str(r), 16, widgets.ALERTE, size_hint_y=None, height=dp(60)))
            return
        if not r:
            c.add_widget(lab("Ton fil est vide : suis des sportifs depuis la communauté du site." if fil else
                             "Aucune boucle partagée pour l'instant.", 16, BRUME, size_hint_y=None, height=dp(60)))
            c.add_widget(Bouton("Trouver des sportifs", lambda *_: self.ouvrir("/communaute.html"), "contour", 56))
            return
        for x in r:
            c.add_widget(self._ligne_activite(x) if fil else self._ligne_boucle(x))

    def _ligne_activite(self, a):
        b = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(120), padding=[0, dp(8)], spacing=dp(2))
        jour = time.strftime("%d/%m", time.localtime(a["debut"]))
        b.add_widget(lab(f"{a['auteur']}, {a['nom']}", 17, gras=True, shorten=True, shorten_from="right",
                         size_hint_y=None, height=dp(26)))
        b.add_widget(lab(f"{nombre(a['distance'] / 1000, 2)} km, {rythme(a)}, le {jour}", 16, BRUME, chiffres=True,
                         size_hint_y=None, height=dp(24)))
        ligne = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        btn = Bouton(f"{'Je n’aime plus' if a['aime'] else 'J’aime'} ({a['jaimes']})", None, "contour", 48, 15)
        btn.bind(on_release=lambda w: self.aimer(a, w))
        ligne.add_widget(btn)
        ligne.add_widget(Bouton(f"Commenter ({a['commentaires']})",
                                lambda *_: self.ouvrir(f"/activite.html?id={a['id']}"), "discret", 48, 15))
        b.add_widget(ligne)
        return b

    def _ligne_boucle(self, i):
        b = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(66), padding=[0, dp(8)])
        b.add_widget(lab(i["nom"], 17, gras=True, shorten=True, shorten_from="right"))
        b.add_widget(lab(f"{i['auteur']}, {'vélo' if i['sport'] == 'velo' else 'course'}, "
                         f"{nombre(i['distance'] / 1000)} km, {(i.get('montee') or 0):.0f} m D+", 15, BRUME))
        return b

    def aimer(self, a, btn):
        oui = not a["aime"]

        def fini(r):
            if isinstance(r, ErreurCompte):
                return
            a["aime"], a["jaimes"] = oui, a["jaimes"] + (1 if oui else -1)
            btn.text = f"{'Je n’aime plus' if oui else 'J’aime'} ({a['jaimes']})"
        en_fond(lambda: self.app.compte.aimer(a["id"], oui), fini)

    def ouvrir(self, chemin):
        if self.app.compte.url:
            ouvrir_url(self.app.compte.url + chemin)
