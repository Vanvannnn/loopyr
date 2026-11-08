"""Intégration Strava (API officielle v3) : OAuth, rafraîchissement des jetons, envoi d'une activité terminée
et suivi de son traitement. Le secret client ne quitte jamais le serveur.
Docs : https://developers.strava.com/docs/authentication/ et https://developers.strava.com/docs/uploads/"""
import time
import urllib.parse

import httpx

from serveur import config

AUTORISER = "https://www.strava.com/oauth/authorize"
JETON = "https://www.strava.com/api/v3/oauth/token"
REVOQUER = "https://www.strava.com/oauth/revoke"
ENVOIS = "https://www.strava.com/api/v3/uploads"
PORTEE = "activity:write,activity:read"


class ErreurStrava(Exception):
    pass


client = httpx.Client(timeout=30)  # remplacé dans les tests


def url_autorisation(etat):
    return AUTORISER + "?" + urllib.parse.urlencode({
        "client_id": config.STRAVA_ID, "redirect_uri": f"{config.URL_PUBLIQUE}/api/strava/retour",
        "response_type": "code", "approval_prompt": "auto", "scope": PORTEE, "state": etat})


def _jeton(donnees):
    r = client.post(JETON, data={"client_id": config.STRAVA_ID, "client_secret": config.STRAVA_SECRET, **donnees})
    if r.status_code != 200:
        raise ErreurStrava(f"Strava a refusé l'autorisation ({r.status_code})")
    return r.json()


def echanger(code):
    """Code reçu au retour d'autorisation -> jetons et athlète."""
    return _jeton({"code": code, "grant_type": "authorization_code"})


def jeton_valide(con, uid):
    """Jeton d'accès utilisable (rafraîchi s'il expire dans moins d'une minute), ou ErreurStrava."""
    ligne = con.execute("SELECT * FROM strava WHERE utilisateur=?", (uid,)).fetchone()
    if not ligne:
        raise ErreurStrava("Compte Strava non connecté")
    if ligne["expire"] > time.time() + 60:
        return ligne["acces"]
    j = _jeton({"grant_type": "refresh_token", "refresh_token": ligne["rafraichissement"]})
    # Strava peut renvoyer un nouveau jeton de rafraîchissement : l'ancien ne marche alors plus
    con.execute("UPDATE strava SET acces=?, rafraichissement=?, expire=? WHERE utilisateur=?",
                (j["access_token"], j.get("refresh_token", ligne["rafraichissement"]), j["expires_at"], uid))
    con.commit()
    return j["access_token"]


def revoquer(jeton):
    try:
        client.post(REVOQUER, data={"token": jeton}, auth=(config.STRAVA_ID, config.STRAVA_SECRET))
    except httpx.HTTPError:
        pass  # on oublie les jetons de toute façon


def envoyer(acces, texte_gpx, nom, sport, id_externe):
    """POST /uploads : renvoie l'objet statut de Strava (id_str, status, error, activity_id)."""
    r = client.post(ENVOIS, headers={"Authorization": f"Bearer {acces}"},
                    data={"data_type": "gpx", "name": nom, "sport_type": sport, "external_id": id_externe},
                    files={"file": (f"{id_externe}.gpx", texte_gpx.encode("utf-8"), "application/gpx+xml")})
    if r.status_code == 429:
        raise ErreurStrava("Limite de requêtes Strava atteinte : réessaie dans 15 minutes")
    if r.status_code not in (200, 201, 400):
        raise ErreurStrava(f"Envoi refusé par Strava ({r.status_code})")
    return r.json()


def statut(acces, id_envoi):
    """GET /uploads/:id (à appeler au plus une fois par seconde)."""
    r = client.get(f"{ENVOIS}/{id_envoi}", headers={"Authorization": f"Bearer {acces}"})
    if r.status_code == 429:
        raise ErreurStrava("Limite de requêtes Strava atteinte : réessaie dans 15 minutes")
    if r.status_code != 200:
        raise ErreurStrava(f"Suivi de l'envoi impossible ({r.status_code})")
    return r.json()


def interpreter(rep):
    """Statut Strava -> ('en_cours' | 'pret' | 'erreur', id de l'activité ou None, erreur ou None)."""
    if rep.get("error"):
        return "erreur", None, rep["error"]
    if rep.get("activity_id"):
        return "pret", str(rep["activity_id"]), None
    return "en_cours", None, None
