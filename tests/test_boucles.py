import json

import pytest

import boucles
from geo import Plan, haversine


class Faux:
    """Routeur de test : lignes droites entre les points, allongées d'un facteur fixe (le « réseau »)."""

    def __init__(self, facteur=1.3, tags=None, aller_retour=False, echec=False):
        self.facteur, self.tags, self.aller_retour, self.echec, self.n = facteur, tags or {}, aller_retour, echec, 0

    def itineraire(self, points, sport):
        self.n += 1
        if self.echec:
            raise boucles.ErreurItineraire("Pas de route ou de chemin praticable à cet endroit")
        if self.aller_retour:  # va au premier point de passage et revient par le même chemin
            points = [points[0], points[1], points[0]]
        coords = []
        for a, b in zip(points, points[1:]):
            for k in range(10):
                coords.append((round(a[0] + (b[0] - a[0]) * k / 10, 6), round(a[1] + (b[1] - a[1]) * k / 10, 6)))
        coords.append(tuple(points[-1]))
        d = sum(haversine(a, b) for a, b in zip(points, points[1:])) * self.facteur
        return {"coords": coords, "ele": [10] * len(coords), "distance": d, "montee": d / 1000 * 5,
                "troncons": [(d, self.tags)]}


DEP = (44.8067, -0.6311)


def test_boucle_fermee_au_depart_et_a_la_bonne_distance():
    out = boucles.generer(DEP, 10000, "course", Faux(), graine=1)
    assert out["propositions"] and not out["message"]
    for p in out["propositions"]:
        assert p["coords"][0] == p["coords"][-1] == DEP
        assert abs(p["distance"] - 10000) / 10000 < 0.03


def test_calibrage_peu_de_requetes():
    f = Faux(facteur=1.6)  # réseau très sinueux : le premier rayon est trop grand
    out = boucles.generer(DEP, 20000, "velo", f, graine=3)
    assert len(out["propositions"]) == 3
    assert f.n <= 10


def test_zone_suit_la_distance():
    petite = boucles.generer(DEP, 5000, "course", Faux(), graine=1)["zone"]["rayon"]
    grande = boucles.generer(DEP, 60000, "velo", Faux(), graine=1)["zone"]["rayon"]
    assert grande > 8 * petite


def test_partout_dans_le_monde():
    for dep in ((48.853, 2.35), (35.01, 135.77), (-33.86, 151.2), (64.14, -21.9)):
        out = boucles.generer(dep, 8000, "course", Faux(), graine=2)
        assert out["propositions"][0]["coords"][0] == dep


def test_aller_retour_refuse_avec_explication():
    out = boucles.generer(DEP, 10000, "course", Faux(aller_retour=True), graine=1)
    assert out["propositions"] == []
    assert "allers-retours" in out["message"]


def test_moteur_en_echec():
    out = boucles.generer(DEP, 10000, "course", Faux(echec=True), graine=1)
    assert out["propositions"] == [] and "praticable" in out["message"]


def test_distance_et_sport_valides():
    with pytest.raises(ValueError):
        boucles.generer(DEP, 500, "course", Faux())
    with pytest.raises(ValueError):
        boucles.generer(DEP, 10000, "ski", Faux())


def test_propositions_variees():
    out = boucles.generer(DEP, 10000, "course", Faux(), graine=4)
    ps = out["propositions"]
    for i, a in enumerate(ps):
        for b in ps[i + 1:]:
            assert boucles.recouvrement_entre(a["coords"], b["coords"]) < 0.6


def test_recouvrement():
    a, b, c = (44.80, -0.63), (44.81, -0.63), (44.81, -0.62)
    assert boucles.recouvrement([a, b, a]) == pytest.approx(0.5)
    assert boucles.recouvrement([a, b, c, a]) == 0


def test_cercle_passe_par_le_depart():
    pts = boucles.cercle(DEP, 2000, 90, 3)
    plan = Plan(*DEP)
    centre = plan.latlon(2000, 0)
    for p in [DEP, *pts]:
        assert haversine(p, centre) == pytest.approx(2000, rel=0.01)
    assert pts[1][1] > DEP[1]  # le point opposé au départ est à l'est (cap 90)


def test_revetement_et_confiance():
    assert boucles.revetement({"highway": "path", "surface": "asphalt"}) == ("revetu", True)
    assert boucles.revetement({"highway": "residential"}) == ("revetu", False)  # déduit
    assert boucles.revetement({"highway": "track"}) == ("inconnu", False)  # jamais supposé
    assert boucles.revetement({"highway": "track", "surface": "gravel"}) == ("non_revetu", True)
    r = boucles.resume_voies([(600, {"highway": "cycleway", "surface": "asphalt"}), (400, {"highway": "residential"})])
    assert r["surface_connue"] == pytest.approx(0.6) and r["surface_deduite"] == pytest.approx(0.4)


def test_deux_sports_deux_preferences():
    chemin_terre = boucles.resume_voies([(1000, {"highway": "track", "surface": "dirt"})])
    route = boucles.resume_voies([(1000, {"highway": "tertiary", "surface": "asphalt"})])
    assert boucles.qualite(route, "velo") > boucles.qualite(chemin_terre, "velo")
    assert boucles.qualite(chemin_terre, "course") > boucles.qualite(route, "course")
    escaliers = boucles.resume_voies([(1000, {"highway": "steps"})])
    assert boucles.qualite(escaliers, "course") == 0


def test_lecture_reponse_brouter(monkeypatch):
    rep = {"features": [{"properties": {"track-length": "1234", "filtered ascend": "12", "messages": [
        ["Longitude", "Latitude", "Elevation", "Distance", "WayTags"],
        ["0", "0", "10", "1000", "highway=cycleway surface=asphalt"],
        ["0", "0", "10", "234", "highway=residential"]]},
        "geometry": {"coordinates": [[-0.63, 44.8, 10.0], [-0.62, 44.81, 12.5]]}}]}
    br = boucles.BRouter("http://moteur")
    appels = []

    def http(url, donnees=None):
        appels.append(url)
        if url.endswith("/profile"):
            return 200, json.dumps({"profileid": f"custom_{len(appels)}"})
        if len([a for a in appels if "lonlats" in a]) == 1:
            return 500, ""  # profil oublié par le serveur : renvoyé une fois, puis ça passe
        return 200, json.dumps(rep)

    monkeypatch.setattr(br, "_http", http)
    it = br.itineraire([(44.8, -0.63), (44.81, -0.62)], "velo")
    assert it["distance"] == 1234 and it["montee"] == 12
    assert it["coords"][0] == (44.8, -0.63) and it["ele"][1] == 12.5
    assert it["troncons"][0] == (1000.0, {"highway": "cycleway", "surface": "asphalt"})
    assert sum(a.endswith("/profile") for a in appels) == 2


def test_erreurs_lisibles():
    assert "praticable" in boucles.traduire_erreur("from-position not mapped in existing datafile")
    assert "données" in boucles.traduire_erreur("datafile W30_N40.rd5 not found")
