"""Client du serveur Loopy pour l'app (Python pur, urllib) : le même compte que sur le site.
L'app fonctionne sans compte ni serveur : génération, course, historique et GPX restent locaux.
Avec un compte : activités et boucles synchronisées, communauté, envoi vers Strava."""
import json, urllib.error, urllib.parse, urllib.request

from boucles import AGENT, contexte_ssl


class ErreurCompte(Exception):
    def __init__(self, message, code=0):
        super().__init__(message)
        self.code = code


class Compte:
    def __init__(self, url, jeton=None, timeout=20):
        self.url, self.jeton, self.timeout = (url or "").rstrip("/"), jeton, timeout

    @property
    def connecte(self):
        return bool(self.url and self.jeton)

    def _req(self, methode, chemin, corps=None):
        if not self.url:
            raise ErreurCompte("Aucun serveur Loopy configuré (Profil > Serveur)")
        h = {"User-Agent": AGENT, "Accept": "application/json"}
        data = None
        if corps is not None:
            h["Content-Type"] = "application/json"
            data = json.dumps(corps).encode()
        if self.jeton:
            h["Authorization"] = f"Bearer {self.jeton}"
        req = urllib.request.Request(self.url + chemin, data=data, headers=h, method=methode)
        ssl = contexte_ssl() if self.url.startswith("https") else None
        try:
            with urllib.request.urlopen(req, timeout=self.timeout, context=ssl) as r:
                texte = r.read().decode()
                return json.loads(texte) if texte else None
        except urllib.error.HTTPError as e:
            try:
                detail = json.loads(e.read().decode()).get("detail")
            except Exception:
                detail = None
            if isinstance(detail, list):  # erreurs de validation
                detail = " ; ".join(d.get("msg", "").replace("Value error, ", "") for d in detail)
            if e.code == 401 and chemin not in ("/api/sessions", "/api/comptes"):
                self.jeton = None  # session expirée ou révoquée
            raise ErreurCompte(detail or f"Erreur du serveur ({e.code})", e.code)
        except (urllib.error.URLError, OSError, ValueError):
            raise ErreurCompte("Serveur Loopy injoignable : vérifie ta connexion et l'adresse du serveur")

    # --- compte ---
    def connecter(self, email, mdp):
        r = self._req("POST", "/api/sessions", {"email": email, "mot_de_passe": mdp})
        self.jeton = r["jeton"]
        return r["utilisateur"]

    def inscrire(self, nom, email, mdp):
        r = self._req("POST", "/api/comptes", {"nom": nom, "email": email, "mot_de_passe": mdp})
        self.jeton = r["jeton"]
        return r["utilisateur"]

    def deconnecter(self):
        try:
            self._req("DELETE", "/api/sessions")
        except ErreurCompte:
            pass
        self.jeton = None

    def moi(self):
        return self._req("GET", "/api/moi")

    def modifier(self, **champs):
        return self._req("PATCH", "/api/moi", champs)

    # --- synchronisation ---
    def envoyer_activite(self, act):
        """Activité réellement faite (points horodatés). Renvoie la version du serveur (avec son id)."""
        corps = {k: act.get(k) for k in ("nom", "sport", "debut", "duree", "duree_totale", "distance", "denivele",
                                         "splits", "segments")}
        corps["sport"] = corps["sport"] or "course"
        corps["splits"] = corps["splits"] or []
        return self._req("PUT", f"/api/moi/activites/{urllib.parse.quote(act['id'])}", corps)

    def enregistrer_itineraire(self, it):
        return self._req("POST", "/api/itineraires", {k: it.get(k) for k in (
            "nom", "sport", "distance", "montee", "coords", "ele", "resume_voies", "favori")})

    def modifier_itineraire(self, id_serveur, **champs):
        return self._req("PATCH", f"/api/itineraires/{id_serveur}", champs)

    def modifier_activite(self, id_serveur, **champs):
        return self._req("PATCH", f"/api/activites/{id_serveur}", champs)

    # --- communauté ---
    def fil(self):
        return self._req("GET", "/api/fil")

    def itineraires_partages(self):
        return self._req("GET", "/api/communaute/itineraires")

    def aimer(self, id_activite, oui=True):
        self._req("POST" if oui else "DELETE", f"/api/activites/{id_activite}/jaime")

    # --- Strava ---
    def lien_strava(self):
        return self._req("POST", "/api/strava/connexion?retour=" + urllib.parse.quote("/strava-ok.html"))["url"]

    def envoyer_strava(self, id_serveur):
        return self._req("POST", f"/api/activites/{id_serveur}/strava")

    def suivre_strava(self, id_serveur):
        return self._req("GET", f"/api/activites/{id_serveur}/strava")
