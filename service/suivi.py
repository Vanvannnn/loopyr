"""Service Android en premier plan, lancé au départ d'une course (capteurs/gps.py: demarrer_service).
Il tourne dans son propre processus et continue écran éteint : il écrit chaque position GPS dans le
journal de la course et fait les annonces vocales. L'app relit le journal pour afficher la course.
Il s'arrête de lui-même quand le journal indique la fin de la course."""
import os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jnius import PythonJavaClass, autoclass, cast, java_method

from annonces import Annonceur
from capteurs.voix import Voix
from journal import Journal

FRAICHEUR = 10  # s : un fix plus ancien est ignoré


class Ecoute(PythonJavaClass):
    __javainterfaces__ = ["android/location/LocationListener"]

    def __init__(self, journal):
        super().__init__()
        self.journal = journal
        self.horloge = autoclass("android.os.SystemClock")

    @java_method("(Landroid/location/Location;)V")
    def onLocationChanged(self, loc):
        # âge du fix mesuré sur l'horloge système monotone : insensible à l'heure GPS du téléphone
        age = (self.horloge.elapsedRealtimeNanos() - loc.getElapsedRealtimeNanos()) / 1e9
        if age > FRAICHEUR:
            return
        prec = loc.getAccuracy() if loc.hasAccuracy() else None
        self.journal.ecrire("point", time.time() - age, loc.getLatitude(), loc.getLongitude(), None, prec)

    # Android 12+ peut livrer les positions par lots : méthodes « par défaut » de l'interface,
    # que le proxy pyjnius doit implémenter lui-même
    @java_method("(Ljava/util/List;)V", name="onLocationChanged")
    def onLocationsChanged(self, locs):
        for i in range(locs.size()):
            self.onLocationChanged(locs.get(i))

    @java_method("(I)V")
    def onFlushComplete(self, code):
        pass

    @java_method("(Ljava/lang/String;)V")
    def onProviderEnabled(self, fournisseur):
        pass

    @java_method("(Ljava/lang/String;)V")
    def onProviderDisabled(self, fournisseur):
        pass

    @java_method("(Ljava/lang/String;ILandroid/os/Bundle;)V")
    def onStatusChanged(self, fournisseur, statut, extras):
        pass


def principal():
    chemin = os.environ["PYTHON_SERVICE_ARGUMENT"]
    journal = Journal(chemin)
    service = autoclass("org.kivy.android.PythonService").mService
    lm = cast("android.location.LocationManager", service.getSystemService("location"))
    ecoute = Ecoute(Journal(chemin))  # sa propre connexion : appelée depuis un autre fil
    # uniquement le GPS : les positions « réseau » sont trop imprécises pour une course
    lm.requestLocationUpdates("gps", 1000, 0.0, ecoute, autoclass("android.os.Looper").getMainLooper())
    verrou = cast("android.os.PowerManager", service.getSystemService("power")).newWakeLock(1, "starva:course")
    verrou.acquire()  # 1 = PARTIAL_WAKE_LOCK : le processeur reste éveillé écran éteint

    voix = Voix(service)
    voix.preparer()
    annonceur = Annonceur((journal.lire_meta("boucle") or {}).get("coords", []), voix.dire, voix.vibrer,
                          lambda: journal.lire_meta("voix") is not False)
    dernier = 0
    try:
        while True:
            for e in journal.lire(apres=dernier):
                dernier = e[0]
                annonceur.traiter(e)
            if journal.etat() in (None, "fin"):
                break
            time.sleep(1)
    finally:
        lm.removeUpdates(ecoute)
        verrou.release()
        voix.fermer()
        journal.fermer()
        service.stopSelf()


principal()
