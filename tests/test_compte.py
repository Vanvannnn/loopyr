"""Le client de l'app contre le vrai serveur (uvicorn sur un port libre, base temporaire)."""
import socket, threading, time

import pytest
import uvicorn

from compte import Compte, ErreurCompte
from geo import Altitudes
from stockage import RESUME_ITINERAIRE, Stockage


@pytest.fixture(scope="module")
def url(postgres):
    from serveur import db
    with db.reserve().connection() as con:
        con.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public")
    from serveur.app import app
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    serveur = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=serveur.run, daemon=True).start()
    for _ in range(50):
        if serveur.started:
            break
        time.sleep(0.1)
    yield f"http://127.0.0.1:{port}"
    serveur.should_exit = True


def test_compte_synchronisation_communaute(url):
    c = Compte(url)
    assert not c.connecte
    with pytest.raises(ErreurCompte) as e:
        c.connecter("personne@x.fr", "motdepasse1")
    assert e.value.code == 401
    c.inscrire("lea", "lea@x.fr", "motdepasse1")
    assert c.connecte and c.moi()["nom"] == "lea"
    act = {"id": "20261108-081405", "sport": "velo", "debut": 1_700_000_000.0, "duree": 600, "distance": 4000,
           "denivele": 12, "splits": None, "segments": [[[1_700_000_000.0 + i, 44.8 + i * 0.001, -0.63, None] for i in range(30)]]}
    a = c.envoyer_activite(act)
    assert a["sport"] == "velo" and c.envoyer_activite(act)["id"] == a["id"]  # renvoi idempotent
    it = c.enregistrer_itineraire({"nom": "Boucle", "sport": "course", "distance": 5000, "montee": 20,
                                   "coords": [[44.8, -0.63], [44.81, -0.63], [44.8, -0.63]], "favori": True})
    assert c.modifier_itineraire(it["id"], partage=True)["partage"] is True
    assert c.fil()[0]["id"] == a["id"]
    c.modifier_activite(a["id"], visibilite="public")
    c.aimer(a["id"])
    assert c.fil()[0]["jaimes"] == 1
    with pytest.raises(ErreurCompte) as e:
        c.lien_strava()  # pas d'identifiants Strava sur ce serveur de test
    assert e.value.code == 503
    c.deconnecter()
    assert not c.connecte


def test_serveur_injoignable():
    with pytest.raises(ErreurCompte, match="injoignable"):
        Compte("http://127.0.0.1:9").moi()
    with pytest.raises(ErreurCompte, match="Aucun serveur"):
        Compte("").moi()


def test_altitudes_depuis_la_boucle():
    alt = Altitudes([(44.8, -0.63), (44.8005, -0.63)], [10.0, 12.0])
    assert alt(44.80049, -0.63001) == pytest.approx(12.0, abs=0.05)
    assert alt(44.80025, -0.63) == pytest.approx(11.0, abs=0.05)  # interpolée le long du tronçon
    assert alt(44.9, -0.63) is None  # loin de la boucle


def test_stockage_des_itineraires(tmp_path):
    s = Stockage(str(tmp_path / "itineraires"), champs=RESUME_ITINERAIRE, tri="cree")
    s.enregistrer({"id": "a", "nom": "Vieux", "sport": "velo", "distance": 1, "cree": 1, "coords": [[0, 0]]})
    s.enregistrer({"id": "b", "nom": "Récent", "sport": "course", "distance": 2, "cree": 2, "coords": [[0, 0]]})
    assert [x["id"] for x in s.lister()] == ["b", "a"] and "coords" not in s.lister()[0]
    assert s.charger("a")["coords"] == [[0, 0]]
