"""Historique des activités : un fichier JSON par activité + un index léger (sans les points).
Toutes les écritures sont atomiques : un crash ne peut pas abîmer l'historique. Python pur."""
import json, os, time

RESUME = ("id", "date", "debut", "distance", "duree", "denivele", "strava_id", "sport", "nom", "id_serveur")
RESUME_ITINERAIRE = ("id", "nom", "sport", "distance", "montee", "cree", "favori", "id_serveur")


def ecrire_json(chemin, donnees):
    tmp = chemin + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(donnees, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, chemin)


def lire_json(chemin):
    with open(chemin, encoding="utf-8") as f:
        return json.load(f)


def mettre_de_cote(chemin):
    """Fichier illisible : on le garde à part (.bak) au lieu de l'écraser."""
    try:
        os.replace(chemin, f"{chemin}.{int(time.time())}.bak")
    except OSError:
        pass


class Stockage:
    """champs : ce que l'index garde de chaque élément ; tri : le champ qui classe (le plus récent d'abord).
    Sert aux activités (réellement faites) et, dans un autre dossier, aux itinéraires enregistrés."""

    def __init__(self, dossier, ancien_profil=None, champs=RESUME, tri="debut"):
        self.dossier, self.champs, self.tri = dossier, champs, tri
        os.makedirs(dossier, exist_ok=True)
        self.chemin_index = os.path.join(dossier, "index.json")
        if ancien_profil and os.path.exists(ancien_profil):
            self._migrer(ancien_profil)

    def _chemin(self, id_):
        return os.path.join(self.dossier, f"{id_}.json")

    def _migrer(self, ancien):
        """Ancien format : toutes les courses dans profil.json, sans heure par point."""
        try:
            courses = lire_json(ancien)
        except (OSError, ValueError):
            mettre_de_cote(ancien)
            return
        for c in courses:
            id_ = c["date"].replace("-", "").replace(":", "").replace(" ", "-") + "00"
            debut = time.mktime(time.strptime(c["date"], "%Y-%m-%d %H:%M"))
            self.enregistrer({**c, "id": id_, "debut": debut, "denivele": c.get("denivele", 0),
                              "splits": [], "segments": [], "strava_id": None})
        os.replace(ancien, ancien + ".migre")

    def index(self):
        try:
            return lire_json(self.chemin_index)
        except FileNotFoundError:
            return []
        except ValueError:
            mettre_de_cote(self.chemin_index)
            return self.reconstruire()

    def reconstruire(self):
        idx = []
        for nom in os.listdir(self.dossier):
            if nom.endswith(".json") and nom != "index.json":
                try:
                    act = lire_json(os.path.join(self.dossier, nom))
                except ValueError:
                    mettre_de_cote(os.path.join(self.dossier, nom))
                    continue
                idx.append({k: act.get(k) for k in self.champs})
        idx.sort(key=lambda a: a.get(self.tri) or 0, reverse=True)
        ecrire_json(self.chemin_index, idx)
        return idx

    def lister(self):
        """Résumés des activités, la plus récente d'abord."""
        return self.index()

    def charger(self, id_):
        return lire_json(self._chemin(id_))

    def enregistrer(self, act):
        ecrire_json(self._chemin(act["id"]), act)
        idx = [a for a in self.index() if a["id"] != act["id"]]
        idx.append({k: act.get(k) for k in self.champs})
        idx.sort(key=lambda a: a.get(self.tri) or 0, reverse=True)
        ecrire_json(self.chemin_index, idx)

    def supprimer(self, id_):
        try:
            os.remove(self._chemin(id_))
        except FileNotFoundError:
            pass
        ecrire_json(self.chemin_index, [a for a in self.index() if a["id"] != id_])
