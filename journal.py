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
        # v0.5 : altitude GPS (ele), précision verticale et pression du baromètre ; journaux plus anciens complétés
        colonnes = {r[1] for r in self.db.execute("PRAGMA table_info(evts)")}
        for col in ("pres", "vprec"):
            if col not in colonnes:
                try:
                    with self.db:
                        self.db.execute(f"ALTER TABLE evts ADD COLUMN {col} REAL")
                except sqlite3.OperationalError:  # l'autre processus vient de l'ajouter
                    pass

    def ecrire(self, type_, t, lat=None, lon=None, ele=None, prec=None, pres=None, vprec=None):
        with self.db:
            self.db.execute("INSERT INTO evts(type, t, lat, lon, ele, prec, pres, vprec) VALUES (?,?,?,?,?,?,?,?)",
                            (type_, t, lat, lon, ele, prec, pres, vprec))

    def lire(self, apres=0):
        """Événements (id, type, t, lat, lon, ele, prec, pres, vprec) écrits après l'id donné.
        ele : altitude GPS (ou None) ; pres : pression en hPa si le téléphone a un baromètre."""
        return self.db.execute("SELECT id, type, t, lat, lon, ele, prec, pres, vprec FROM evts WHERE id > ? ORDER BY id",
                               (apres,)).fetchall()

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
    """Applique un événement du journal à la course ; renvoie la course (nouvelle si 'debut').
    altitude : un geo.Altimetre, qui choisit l'altitude du dénivelé (baromètre, terrain, GPS lissé)."""
    _, type_, t, lat, lon, ele, prec = evt[:7]
    pres, vprec = (evt[7], evt[8]) if len(evt) > 8 else (None, None)
    if type_ == "debut":
        return Course(debut=t)
    if course is None:
        return None
    if type_ == "point":
        if altitude:
            ele = altitude(lat, lon, gps=ele, vprec=vprec, pression=pres)
            course.seuil = 5 if getattr(altitude, "source", None) == "gps" else 3
        elif pres or (vprec is not None and vprec > 12):
            ele = None  # sans altimètre, une altitude GPS imprécise ne compte pas
        course.ajouter(t, lat, lon, ele, prec)
    elif type_ == "pause":
        course.pause(t)
    elif type_ == "reprise":
        course.reprendre(t)
    elif type_ == "fin":
        course.terminer(t)
    return course
