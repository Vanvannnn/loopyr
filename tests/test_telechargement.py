"""Page de téléchargement : l'APK publié est servi avec le bon type, et la page pointe vers lui."""
import hashlib, os

import pytest
from fastapi.testclient import TestClient

from serveur import config

APK = os.path.join(config.SITE, "downloads", "loopy.apk")


@pytest.mark.skipif(not os.path.exists(APK), reason="APK non publié dans website/downloads")
def test_apk_servi(base_vide):
    from serveur.app import app
    with TestClient(app) as c:
        r = c.head("/downloads/loopy.apk")
        assert r.status_code == 200 and r.headers["content-type"] == "application/vnd.android.package-archive"
        assert int(r.headers["content-length"]) == os.path.getsize(APK)
        page = c.get("/telecharger.html").text
        assert 'href="/downloads/loopy.apk"' in page and "iPhone" in page
        with open(APK, "rb") as f:  # l'empreinte affichée doit être celle du fichier publié
            assert hashlib.sha256(f.read()).hexdigest() in page


def test_manifeste_pwa(base_vide):
    """iPhone : le site s'installe sur l'écran d'accueil (manifeste servi, référencé par les pages)."""
    from serveur.app import app
    with TestClient(app) as c:
        r = c.get("/manifest.webmanifest")
        assert r.status_code == 200 and r.headers["content-type"].startswith("application/manifest+json")
        m = r.json()
        assert m["display"] == "standalone" and {i["sizes"] for i in m["icons"]} == {"192x192", "512x512"}
        for page in ("/", "/creer.html", "/telecharger.html"):
            assert 'rel="manifest"' in c.get(page).text and "apple-touch-icon" in c.get(page).text
