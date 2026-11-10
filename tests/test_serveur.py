import time

import pytest
from fastapi.testclient import TestClient

from serveur import config, strava


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DONNEES", str(tmp_path))
    monkeypatch.setattr(config, "DB", str(tmp_path / "loopy.db"))
    from serveur import app as appli
    appli.limiteur.appels.clear()
    with TestClient(appli.app) as c:
        yield c


def compte(c, nom="alice", email=None):
    r = c.post("/api/comptes", json={"email": email or f"{nom}@exemple.fr", "nom": nom, "mot_de_passe": "motdepasse1"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['jeton']}"}


def activite(visibilite=None):
    t0 = 1_700_000_000.0
    seg = [[t0 + i * 5, 44.80 + i * 0.0003, -0.63, 20.0] for i in range(60)]  # ~2 km vers le nord
    d = {"sport": "course", "debut": t0, "duree": 295, "distance": 1970, "denivele": 4, "segments": [seg]}
    return {**d, "visibilite": visibilite} if visibilite else d


def test_inscription_connexion_deconnexion(client):
    h = compte(client)
    assert client.get("/api/moi", headers=h).json()["nom"] == "alice"
    assert client.post("/api/comptes", json={"email": "alice@exemple.fr", "nom": "autre", "mot_de_passe": "motdepasse1"}).status_code == 409
    assert client.post("/api/sessions", json={"email": "alice@exemple.fr", "mot_de_passe": "mauvais"}).status_code == 401
    r = client.post("/api/sessions", json={"email": "ALICE@exemple.fr", "mot_de_passe": "motdepasse1"})
    h2 = {"Authorization": f"Bearer {r.json()['jeton']}"}
    client.delete("/api/sessions", headers=h2)
    assert client.get("/api/moi", headers=h2).status_code == 401
    assert client.get("/api/moi", headers=h).status_code == 200


def test_validation_inscription(client):
    for d in ({"email": "pas-un-mail", "nom": "bob", "mot_de_passe": "motdepasse1"},
              {"email": "b@x.fr", "nom": "B o", "mot_de_passe": "motdepasse1"},
              {"email": "b@x.fr", "nom": "bob", "mot_de_passe": "court"}):
        assert client.post("/api/comptes", json=d).status_code == 422


def test_cookie_du_site_et_protection_csrf(client):
    client.post("/api/comptes", json={"email": "c@x.fr", "nom": "cece", "mot_de_passe": "motdepasse1"})
    assert client.get("/api/moi").status_code == 200  # cookie HttpOnly posé par l'inscription
    assert client.patch("/api/moi", json={"bio": "x"}).status_code == 403  # sans l'en-tête du site
    assert client.patch("/api/moi", json={"bio": "x"}, headers={"X-Loopy": "1"}).json()["bio"] == "x"


def test_mot_de_passe_oublie(client, capsys):
    compte(client)
    assert client.post("/api/mot-de-passe/oubli", json={"email": "inconnu@x.fr"}).status_code == 202
    client.post("/api/mot-de-passe/oubli", json={"email": "alice@exemple.fr"})
    jeton = capsys.readouterr().out.split("reinitialiser.html#")[1].split()[0]
    assert client.post("/api/mot-de-passe/reinit", json={"jeton": jeton, "mot_de_passe": "nouveau-mdp"}).status_code == 200
    assert client.post("/api/mot-de-passe/reinit", json={"jeton": jeton, "mot_de_passe": "encore-un"}).status_code == 400
    assert client.post("/api/sessions", json={"email": "alice@exemple.fr", "mot_de_passe": "nouveau-mdp"}).status_code == 200


def test_limite_de_debit(client):
    for _ in range(10):
        client.post("/api/sessions", json={"email": "x@x.fr", "mot_de_passe": "mauvais"})
    assert client.post("/api/sessions", json={"email": "x@x.fr", "mot_de_passe": "mauvais"}).status_code == 429


def test_profil_et_avatar(client):
    h = compte(client)
    r = client.patch("/api/moi", headers=h, json={"bio": "Coureuse du dimanche", "sport": "velo",
                                                   "preferences": {"relief": "plat"}, "visibilite_activites": "public"})
    assert r.json()["sport"] == "velo" and r.json()["preferences"] == {"relief": "plat"}
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 100
    r = client.post("/api/moi/avatar", headers=h, files={"fichier": ("a.png", png, "image/png")})
    assert client.get(r.json()["avatar"]).content == png
    assert client.post("/api/moi/avatar", headers=h, files={"fichier": ("a.svg", b"<svg/>", "image/svg+xml")}).status_code == 415


def test_itineraires_favoris_gpx_et_partage(client):
    h = compte(client)
    coords = [[44.80 + i * 0.001, -0.63] for i in range(30)] + [[44.80, -0.63]]
    r = client.post("/api/itineraires", headers=h, json={"nom": "Tour du parc", "sport": "velo", "distance": 10240,
                                                          "montee": 85, "coords": coords})
    i = r.json()["id"]
    client.patch(f"/api/itineraires/{i}", headers=h, json={"favori": True, "partage": True})
    assert [x["id"] for x in client.get("/api/itineraires?favoris=true", headers=h).json()] == [i]
    g = client.get(f"/api/itineraires/{i}/gpx", headers=h)
    assert 'filename="boucle_10km_velo.gpx"' in g.headers["content-disposition"] and "<time>" not in g.text
    client.cookies.clear()  # un visiteur
    commu = client.get("/api/communaute/itineraires").json()
    assert commu[0]["nom"] == "Tour du parc" and "coords" not in commu[0]
    assert len(commu[0]["trace"]) < len(coords)  # départ masqué pour les autres


def test_activites_visibilite_et_vie_privee(client):
    ha, hb = compte(client, "alice"), compte(client, "bob")
    a = client.put("/api/moi/activites/20231114-221320", headers=ha, json=activite()).json()
    assert a["visibilite"] == "abonnes"  # réglage par défaut du compte
    assert client.put("/api/moi/activites/20231114-221320", headers=ha, json=activite()).json()["id"] == a["id"]
    assert client.get(f"/api/activites/{a['id']}", headers=hb).status_code == 404  # bob ne suit pas alice
    client.post("/api/utilisateurs/alice/abonnement", headers=hb)
    vue = client.get(f"/api/activites/{a['id']}", headers=hb).json()
    assert vue["strava"] is None and vue["id_client"] is None
    assert len(vue["trace"]) < 60  # 300 m retirés au début et à la fin
    assert vue["trace"][0][0] > 44.802
    client.cookies.clear()
    assert client.get(f"/api/activites/{a['id']}").status_code == 404  # anonyme
    client.patch(f"/api/activites/{a['id']}", headers=ha, json={"visibilite": "prive"})
    assert client.get(f"/api/activites/{a['id']}", headers=hb).status_code == 404
    assert client.get(f"/api/activites/{a['id']}/gpx", headers=hb).status_code == 404
    assert "<time>2023-11-14T22:13:20Z</time>" in client.get(f"/api/activites/{a['id']}/gpx", headers=ha).text


def test_fil_jaimes_commentaires(client):
    ha, hb = compte(client, "alice"), compte(client, "bob")
    a = client.put("/api/moi/activites/x1", headers=ha, json=activite("public")).json()
    client.post("/api/utilisateurs/alice/abonnement", headers=hb)
    assert [x["id"] for x in client.get("/api/fil", headers=hb).json()] == [a["id"]]
    client.post(f"/api/activites/{a['id']}/jaime", headers=hb)
    client.post(f"/api/activites/{a['id']}/commentaires", headers=hb, json={"texte": "Bravo !"})
    vue = client.get(f"/api/activites/{a['id']}", headers=ha).json()
    assert vue["jaimes"] == 1 and vue["commentaires"] == 1
    assert client.get(f"/api/activites/{a['id']}/commentaires").json()[0]["auteur"] == "bob"
    p = client.get("/api/utilisateurs/alice").json()
    assert p["abonnes"] == 1 and p["stats"]["par_sport"]["course"]["nombre"] == 1
    client.cookies.clear()
    assert [x["id"] for x in client.get("/api/communaute/activites").json()] == [a["id"]]


def test_suppression_du_compte(client):
    ha, hb = compte(client, "alice"), compte(client, "bob")
    a = client.put("/api/moi/activites/x1", headers=ha, json=activite("public")).json()
    client.post(f"/api/activites/{a['id']}/jaime", headers=hb)
    assert client.delete("/api/moi", headers=ha).status_code == 204
    assert client.get("/api/utilisateurs/alice").status_code == 404
    assert client.get(f"/api/activites/{a['id']}").status_code == 404


def test_strava_non_configure(client, monkeypatch):
    monkeypatch.setattr(config, "STRAVA_ID", "")
    h = compte(client)
    assert client.get("/api/strava", headers=h).json() == {"configure": False, "connecte": False, "athlete": None}
    assert client.post("/api/strava/connexion", headers=h).status_code == 503


class FauxStrava:
    """Les réponses documentées de Strava (OAuth, /uploads), sans réseau."""

    def __init__(self):
        self.appels, self.polls = [], 0

    def post(self, url, data=None, files=None, headers=None, auth=None):
        self.appels.append((url, data, files, headers))
        if url == strava.JETON:
            if data["grant_type"] == "authorization_code":
                assert data["client_secret"] == "secret" and data["code"] == "le-code"
                return Rep(200, {"access_token": "acces1", "refresh_token": "rafr1", "expires_at": time.time() + 21600,
                                 "athlete": {"id": 42, "firstname": "Alice", "lastname": "L."}})
            return Rep(200, {"access_token": "acces2", "refresh_token": "rafr2", "expires_at": time.time() + 21600})
        if url == strava.ENVOIS:
            assert headers["Authorization"] == "Bearer acces2"  # jeton rafraîchi avant l'envoi
            return Rep(201, {"id_str": "777", "status": "Your activity is still being processed.", "error": None,
                             "activity_id": None})
        return Rep(200, {})

    def get(self, url, headers=None):
        self.polls += 1
        return Rep(200, {"id_str": "777", "status": "Your activity is ready.", "error": None, "activity_id": 153243126})


class Rep:
    def __init__(self, code, data):
        self.status_code, self._d = code, data

    def json(self):
        return self._d


def test_strava_connexion_envoi_et_suivi(client, monkeypatch):
    monkeypatch.setattr(config, "STRAVA_ID", "1234")
    monkeypatch.setattr(config, "STRAVA_SECRET", "secret")
    faux = FauxStrava()
    monkeypatch.setattr(strava, "client", faux)
    h = compte(client)
    url = client.post("/api/strava/connexion", headers=h).json()["url"]
    assert "client_id=1234" in url and "activity%3Awrite" in url and "secret" not in url
    etat = url.split("state=")[1]
    r = client.get(f"/api/strava/retour?state={etat}&code=le-code&scope=read,activity:write,activity:read",
                   follow_redirects=False)
    assert r.headers["location"] == "/espace.html?strava=ok#profil"
    assert client.get(f"/api/strava/retour?state={etat}&code=le-code&scope=activity:write").status_code == 400
    assert client.get("/api/strava", headers=h).json()["athlete"] == "Alice L."

    from serveur import db
    con = db.ouvrir()
    con.execute("UPDATE strava SET expire=?", (time.time() - 10,))  # jeton expiré : il sera rafraîchi
    con.commit()
    a = client.put("/api/moi/activites/x1", headers=h, json=activite()).json()
    r = client.post(f"/api/activites/{a['id']}/strava", headers=h).json()
    assert r["statut"] == "en_cours"
    envoi = [x for x in faux.appels if x[0] == strava.ENVOIS][0]
    assert envoi[1]["data_type"] == "gpx" and envoi[1]["sport_type"] == "Run"
    assert b"<time>" in envoi[2]["file"][1]
    r = client.get(f"/api/activites/{a['id']}/strava", headers=h).json()
    assert r["statut"] == "pret" and r["url"] == "https://www.strava.com/activities/153243126"
    assert client.post(f"/api/activites/{a['id']}/strava", headers=h).json()["statut"] == "pret"  # pas de doublon
    assert con.execute("SELECT rafraichissement FROM strava").fetchone()[0] == "rafr2"


def test_strava_permission_refusee(client, monkeypatch):
    monkeypatch.setattr(config, "STRAVA_ID", "1234")
    monkeypatch.setattr(config, "STRAVA_SECRET", "secret")
    h = compte(client)
    etat = client.post("/api/strava/connexion", headers=h).json()["url"].split("state=")[1]
    r = client.get(f"/api/strava/retour?state={etat}&code=c&scope=read", follow_redirects=False)
    assert "strava=permission" in r.headers["location"]


def test_generation_par_le_serveur(client, monkeypatch):
    from serveur import app as appli
    from tests.test_boucles import Faux
    monkeypatch.setattr(appli, "routeur", Faux())
    r = client.post("/api/boucles", json={"sport": "course", "distance_km": 10, "lat": 48.85, "lon": 2.35})
    p = r.json()["propositions"]
    assert p and "troncons" not in p[0] and p[0]["coords"][0] == [48.85, 2.35]
    assert client.post("/api/boucles", json={"sport": "course", "distance_km": 0.2, "lat": 48.85, "lon": 2.35}).status_code == 422


def test_description_et_ressenti_prive(client):
    """v0.5 : la description se partage, le ressenti reste à son auteur ; les deux se modifient ensuite."""
    h, h2 = compte(client), compte(client, "bob")
    corps = {**activite("public"), "nom": "Course du soir", "description": "Jambes lourdes", "ressenti": "dur"}
    a = client.put("/api/moi/activites/x1", json=corps, headers=h).json()
    assert a["description"] == "Jambes lourdes" and a["ressenti"] == "dur"
    vu = client.get(f"/api/activites/{a['id']}", headers=h2).json()
    assert vu["description"] == "Jambes lourdes" and vu["ressenti"] is None
    r = client.patch(f"/api/activites/{a['id']}", json={"nom": "Renommée", "ressenti": "bien"}, headers=h)
    assert r.json()["nom"] == "Renommée" and r.json()["ressenti"] == "bien"
    assert client.put("/api/moi/activites/x2", json={**corps, "ressenti": "super"}, headers=h).status_code == 422
