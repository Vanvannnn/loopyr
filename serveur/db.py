"""Base SQLite du serveur. Un fichier, mode WAL ; le schéma est créé au démarrage."""
import os, sqlite3

from serveur import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS utilisateurs(
  id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, nom TEXT UNIQUE NOT NULL, mdp TEXT NOT NULL,
  bio TEXT DEFAULT '', sport TEXT DEFAULT 'course', preferences TEXT DEFAULT '{}', avatar TEXT,
  visibilite_profil TEXT DEFAULT 'public', visibilite_activites TEXT DEFAULT 'abonnes',
  masquer_depart INTEGER DEFAULT 1, cree REAL NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(jeton TEXT PRIMARY KEY, utilisateur INTEGER NOT NULL, expire REAL NOT NULL);
CREATE TABLE IF NOT EXISTS reinits(jeton TEXT PRIMARY KEY, utilisateur INTEGER NOT NULL, expire REAL NOT NULL);
CREATE TABLE IF NOT EXISTS itineraires(
  id TEXT PRIMARY KEY, utilisateur INTEGER NOT NULL, nom TEXT NOT NULL, sport TEXT NOT NULL,
  distance REAL NOT NULL, montee REAL, coords TEXT NOT NULL, ele TEXT, resume TEXT,
  favori INTEGER DEFAULT 0, partage INTEGER DEFAULT 0, cree REAL NOT NULL);
CREATE TABLE IF NOT EXISTS activites(
  id TEXT PRIMARY KEY, utilisateur INTEGER NOT NULL, id_client TEXT NOT NULL, nom TEXT NOT NULL,
  sport TEXT NOT NULL, debut REAL NOT NULL, duree REAL, duree_totale REAL, distance REAL NOT NULL,
  denivele REAL, splits TEXT, segments TEXT NOT NULL, itineraire TEXT, visibilite TEXT NOT NULL,
  strava_upload TEXT, strava_statut TEXT, strava_erreur TEXT, strava_activite TEXT, cree REAL NOT NULL,
  description TEXT DEFAULT '', ressenti TEXT,
  UNIQUE(utilisateur, id_client));
CREATE INDEX IF NOT EXISTS activites_par_date ON activites(utilisateur, debut);
CREATE TABLE IF NOT EXISTS abonnements(suiveur INTEGER NOT NULL, suivi INTEGER NOT NULL, cree REAL NOT NULL,
  PRIMARY KEY(suiveur, suivi));
CREATE TABLE IF NOT EXISTS jaimes(utilisateur INTEGER NOT NULL, activite TEXT NOT NULL, PRIMARY KEY(utilisateur, activite));
CREATE TABLE IF NOT EXISTS commentaires(id INTEGER PRIMARY KEY, utilisateur INTEGER NOT NULL, activite TEXT NOT NULL,
  texte TEXT NOT NULL, cree REAL NOT NULL);
CREATE TABLE IF NOT EXISTS strava(utilisateur INTEGER PRIMARY KEY, athlete TEXT, nom TEXT, acces TEXT NOT NULL,
  rafraichissement TEXT NOT NULL, expire REAL NOT NULL, portee TEXT);
CREATE TABLE IF NOT EXISTS etats_oauth(etat TEXT PRIMARY KEY, utilisateur INTEGER NOT NULL, retour TEXT,
  expire REAL NOT NULL);
"""


def ouvrir(chemin=None):
    chemin = chemin or config.DB
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    # autocommit : chaque écriture est validée tout de suite. FastAPI ferme les dépendances après avoir envoyé
    # la réponse : une validation en fin de requête arriverait après que le client a déjà enchaîné.
    con = sqlite3.connect(chemin, timeout=10, check_same_thread=False, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


MIGRATIONS = {"activites": (("description", "TEXT DEFAULT ''"), ("ressenti", "TEXT"))}  # v0.5


def initialiser(chemin=None):
    con = ouvrir(chemin)
    con.executescript(SCHEMA)
    for table, colonnes in MIGRATIONS.items():  # bases créées par une version précédente
        existantes = {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
        for nom, type_ in colonnes:
            if nom not in existantes:
                con.execute(f"ALTER TABLE {table} ADD COLUMN {nom} {type_}")
    con.commit()
    con.close()
