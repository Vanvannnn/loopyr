import os, sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [RACINE, os.path.dirname(os.path.abspath(__file__))]

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def postgres(tmp_path_factory):
    """Un vrai PostgreSQL local (pgserver) pour toute la session de tests."""
    pgserver = pytest.importorskip("pgserver")
    from serveur import config, db
    serveur = pgserver.get_server(str(tmp_path_factory.mktemp("pg")), cleanup_mode="stop")
    config.DATABASE_URL = serveur.get_uri()
    yield serveur
    db.fermer()


@pytest.fixture
def base_vide(postgres):
    """Base remise à zéro : chaque test part sans aucune donnée."""
    from serveur import db
    with db.reserve().connection() as con:
        con.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public")
    db.initialiser()
