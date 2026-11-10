import pytest
from aide import ligne_droite
from journal import Journal, appliquer


def test_rejouer_reconstruit_la_course(tmp_path):
    j = Journal(str(tmp_path / "en_cours.db"))
    j.ecrire("debut", 1000.0)
    pts = ligne_droite(600)
    for t, lat, lon in pts[:60]:
        j.ecrire("point", t, lat, lon, None, 5)
    j.ecrire("pause", 1100.0)
    j.ecrire("reprise", 1130.0)
    for t, lat, lon in pts[60:]:
        j.ecrire("point", t + 30, lat, lon, None, 5)
    j.poser("boucle", {"distance": 5000})
    assert j.etat() == "reprise"

    # l'app redémarre : nouvelle connexion, on rejoue tout
    j2 = Journal(str(tmp_path / "en_cours.db"))
    course = None
    for e in j2.lire():
        course = appliquer(course, e, altitude=lambda la, lo, **_: 12.0)
    assert course.dist == pytest.approx(595, rel=0.02)
    assert course.pauses == [[1100.0, 1130.0]]
    assert course.segments[0][0][3] == 12.0
    assert j2.lire_meta("boucle") == {"distance": 5000}
    assert j2.lire(apres=10_000) == []


def test_vider(tmp_path):
    j = Journal(str(tmp_path / "en_cours.db"))
    j.ecrire("debut", 1.0)
    j.vider()
    assert j.etat() is None
