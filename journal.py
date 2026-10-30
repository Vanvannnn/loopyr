"""Course en cours, écrite au fil de l'eau dans un fichier sqlite partagé entre l'app et le service GPS.
Tout est un événement : debut, point, pause, reprise, fin. Rejouer le journal reconstruit la Course,
même après un crash de l'app ou si Android l'a mise en veille. Python pur."""
import json, sqlite3

from course import Course

ETATS = ("debut", "pause", "reprise", "fin")


class Journal:
    def __init__(self, chemin):
        self.db = sqlite3.connect(chemin, timeout=5, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")  # sûr si l'app plante, rapide à chaque point
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS evts(id INTEGER PRIMARY KEY, type TEXT, t REAL,
                                            lat REAL, lon REAL, ele REAL, prec REAL);
            CREATE TABLE IF NOT EXISTS meta(cle TEXT PRIMARY KEY, valeur TEXT);""")

    def ecrire(self, type_, t, lat=None, lon=None, ele=None, prec=None):
        with self.db:
            self.db.execute("INSERT INTO evts(type, t, lat, lon, ele, prec) VALUES (?,?,?,?,?,?)",
                            (type_, t, lat, lon, ele, prec))

    def lire(self, apres=0):
        """Événements (id, type, t, lat, lon, ele, prec) écrits après l'id donné."""
        return self.db.execute("SELECT * FROM evts WHERE id > ? ORDER BY id", (apres,)).fetchall()

    def etat(self):
        """Dernier changement d'état (debut, pause, reprise, fin), ou None si aucune course."""
        r = self.db.execute(f"SELECT type FROM evts WHERE type IN {ETATS} ORDER BY id DESC LIMIT 1").fetchone()
        return r[0] if r else None

    def poser(self, cle, valeur):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (cle, json.dumps(valeur)))

    def lire_meta(self, cle):
        r = self.db.execute("SELECT valeur FROM meta WHERE cle = ?", (cle,)).fetchone()
        return json.loads(r[0]) if r else None

    def vider(self):
        with self.db:
            self.db.execute("DELETE FROM evts")
            self.db.execute("DELETE FROM meta")

    def fermer(self):
        self.db.close()


def appliquer(course, evt, altitude=None):
    """Applique un événement du journal à la course ; renvoie la course (nouvelle si 'debut')."""
    _, type_, t, lat, lon, ele, prec = evt
    if type_ == "debut":
        return Course(debut=t)
    if course is None:
        return None
    if type_ == "point":
        if ele is None and altitude:
            ele = altitude(lat, lon)
        course.ajouter(t, lat, lon, ele, prec)
    elif type_ == "pause":
        course.pause(t)
    elif type_ == "reprise":
        course.reprendre(t)
    elif type_ == "fin":
        course.terminer(t)
    return course
