"""Configuration du serveur, par variables d'environnement (voir docs/CONFIGURATION.md). Aucun secret dans le code."""
import os

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DONNEES = os.environ.get("LOOPY_DONNEES", os.path.join(RACINE, "serveur", "donnees"))
DB = os.path.join(DONNEES, "loopy.db")
URL_PUBLIQUE = os.environ.get("LOOPY_URL_PUBLIQUE", "http://localhost:8000").rstrip("/")
COOKIE_SECURE = URL_PUBLIQUE.startswith("https://")
STRAVA_ID = os.environ.get("STRAVA_CLIENT_ID", "")
STRAVA_SECRET = os.environ.get("STRAVA_CLIENT_SECRET", "")
SMTP = {k: os.environ.get(f"SMTP_{k.upper()}", "") for k in ("hote", "port", "utilisateur", "mot_de_passe", "expediteur")}
SITE = os.path.join(RACINE, "website")


def strava_configure():
    return bool(STRAVA_ID and STRAVA_SECRET)
