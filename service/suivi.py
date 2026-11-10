"""Service Android en premier plan, lancé au départ d'une sortie (capteurs/gps.py: demarrer_service).
Il tourne dans son propre processus et continue écran verrouillé : il écrit chaque position GPS (avec l'altitude
GPS et, si le téléphone en a un, la pression du baromètre) dans le journal de la sortie, fait les annonces
vocales et tient à jour la notification « Loopy — Course à pied / Cyclisme » (durée, distance, état).
L'app relit le journal pour afficher la sortie. Le service s'arrête de lui-même quand le journal indique la fin.

Il est « sticky » : si Android le tue (mémoire), il est relancé et reprend le même journal ; il ne s'arrête plus
quand on balaie l'app dans les applis récentes."""
import os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jnius import PythonJavaClass, autoclass, cast, java_method

from annonces import Annonceur
from capteurs.voix import Voix
from journal import Journal

FRAICHEUR = 10  # s : un fix plus ancien est ignoré
CANAL = "loopy_sortie"
ID_NOTIF = 1  # celui du service (getServiceId) : on remplace sa notification au lieu d'en ajouter une
FICHIER_CHEMIN = "journal_en_cours.txt"  # écrit par l'app : sert si Android relance le service sans argument


class Barometre(PythonJavaClass):
    __javainterfaces__ = ["android/hardware/SensorEventListener"]

    def __init__(self):
        super().__init__()
        self.hpa, self.t = None, 0

    @java_method("(Landroid/hardware/Sensor;I)V")
    def onAccuracyChanged(self, capteur, precision):
        pass

    @java_method("(Landroid/hardware/SensorEvent;)V")
    def onSensorChanged(self, evt):
        v = evt.values[0]
        self.hpa = v if self.hpa is None else self.hpa + 0.2 * (v - self.hpa)  # lissage léger (bruit ~0,1 hPa)
        self.t = time.time()

    def valeur(self):
        return self.hpa if self.hpa and time.time() - self.t < 10 else None


class Ecoute(PythonJavaClass):
    __javainterfaces__ = ["android/location/LocationListener"]

    def __init__(self, journal, barometre):
        super().__init__()
        self.journal, self.baro = journal, barometre
        self.horloge = autoclass("android.os.SystemClock")
        self.sdk = autoclass("android.os.Build$VERSION").SDK_INT

    @java_method("(Landroid/location/Location;)V")
    def onLocationChanged(self, loc):
        # âge du fix mesuré sur l'horloge système monotone : insensible à l'heure GPS du téléphone
        age = (self.horloge.elapsedRealtimeNanos() - loc.getElapsedRealtimeNanos()) / 1e9
        if age > FRAICHEUR:
            return
        prec = loc.getAccuracy() if loc.hasAccuracy() else None
        ele = vprec = None
        if loc.hasAltitude():
            ele = loc.getAltitude()  # au-dessus de l'ellipsoïde : décalé de quelques dizaines de m, mais le D+ n'en dépend pas
            if self.sdk >= 34 and loc.hasMslAltitude():
                ele = loc.getMslAltitudeMeters()
            if self.sdk >= 26 and loc.hasVerticalAccuracy():
                vprec = loc.getVerticalAccuracyMeters()
        self.journal.ecrire("point", time.time() - age, loc.getLatitude(), loc.getLongitude(), ele, prec,
                            self.baro.valeur() if self.baro else None, vprec)

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


class Notification:
    """La notification du service : « Loopy — Course à pied », « 24:13 · 4,52 km · en cours ».
    Toucher la notification ramène à l'app (et à la sortie en cours)."""

    def __init__(self, service):
        self.service = service
        self.sdk = autoclass("android.os.Build$VERSION").SDK_INT
        self.texte = None
        if self.sdk >= 26:
            NM = autoclass("android.app.NotificationManager")
            canal = autoclass("android.app.NotificationChannel")(CANAL, "Sortie en cours", NM.IMPORTANCE_LOW)
            canal.setDescription("Durée et distance pendant une course ou une sortie vélo")
            canal.setShowBadge(False)
            canal.setLockscreenVisibility(1)  # VISIBILITY_PUBLIC : lisible écran verrouillé
            self.nm = cast("android.app.NotificationManager", service.getSystemService("notification"))
            self.nm.createNotificationChannel(canal)
        Intent, PI = autoclass("android.content.Intent"), autoclass("android.app.PendingIntent")
        ouvrir = Intent(service, autoclass("org.kivy.android.PythonActivity"))
        ouvrir.setFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_REORDER_TO_FRONT)
        self.retour = PI.getActivity(service, 0, ouvrir, PI.FLAG_IMMUTABLE | PI.FLAG_UPDATE_CURRENT)
        self.icone = service.getApplicationInfo().icon

    def montrer(self, titre, texte):
        if texte == self.texte:
            return
        self.texte = texte
        String = autoclass("java.lang.String")
        B = autoclass("android.app.Notification$Builder")
        b = B(self.service, CANAL) if self.sdk >= 26 else B(self.service)
        b.setContentTitle(cast("java.lang.CharSequence", String(titre)))
        b.setContentText(cast("java.lang.CharSequence", String(texte)))
        b.setSmallIcon(self.icone)
        b.setContentIntent(self.retour)
        b.setOngoing(True)
        b.setOnlyAlertOnce(True)
        b.setShowWhen(False)
        b.setCategory("workout" if self.sdk >= 30 else "progress")
        b.setVisibility(1)
        # même identifiant que le service : la notification de premier plan est remplacée, pas doublée
        self.service.startForeground(ID_NOTIF, b.build())


def resume(course, sport):
    """« 24:13 · 4,52 km · en cours » à partir de la course rejouée par l'annonceur."""
    if course is None:
        return "Départ…"
    s = int(course.duree())
    duree = f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60:02d}:{s % 60:02d}"
    etat = "en pause" if course.en_pause else "en cours"
    return f"{duree} · {course.dist / 1000:.2f} km · {etat}".replace(".", ",")


def chemin_journal(service):
    """L'argument donné par l'app ; s'il manque (relance par Android), le dernier chemin qu'elle a noté."""
    chemin = os.environ.get("PYTHON_SERVICE_ARGUMENT") or ""
    if chemin:
        return chemin
    try:
        with open(os.path.join(service.getFilesDir().getAbsolutePath(), FICHIER_CHEMIN), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def principal():
    service = autoclass("org.kivy.android.PythonService").mService
    chemin = chemin_journal(service)
    if not chemin or not os.path.exists(chemin):
        service.stopSelf()
        return
    journal = Journal(chemin)
    if journal.etat() in (None, "fin"):  # relancé alors que la sortie est déjà finie : rien à faire
        journal.fermer()
        service.stopSelf()
        return
    boucle = journal.lire_meta("boucle") or {}
    sport = boucle.get("sport") or "course"
    titre = "Loopy — Cyclisme" if sport == "velo" else "Loopy — Course à pied"
    notif = Notification(service)
    notif.montrer(titre, "Départ…")

    sm = cast("android.hardware.SensorManager", service.getSystemService("sensor"))
    capteur = sm.getDefaultSensor(6)  # TYPE_PRESSURE : absent sur beaucoup de téléphones
    baro = Barometre() if capteur is not None else None
    looper = autoclass("android.os.Looper").getMainLooper()
    if baro:
        sm.registerListener(baro, capteur, 1000000)  # une mesure par seconde suffit
    journal.poser("barometre", baro is not None)  # l'app dit d'où vient le dénivelé, sans inventer de capteur

    lm = cast("android.location.LocationManager", service.getSystemService("location"))
    ecoute = Ecoute(Journal(chemin), baro)  # sa propre connexion : appelée depuis un autre fil
    # uniquement le GPS : les positions « réseau » sont trop imprécises pour une sortie
    lm.requestLocationUpdates("gps", 1000, 0.0, ecoute, looper)
    verrou = cast("android.os.PowerManager", service.getSystemService("power")).newWakeLock(1, "loopy:sortie")
    verrou.acquire()  # 1 = PARTIAL_WAKE_LOCK : le processeur reste éveillé écran éteint

    voix = Voix(service)
    voix.preparer()
    annonceur = Annonceur(boucle.get("coords", []), voix.dire, voix.vibrer,
                          lambda: journal.lire_meta("voix") is not False, consignes=boucle.get("hints"),
                          sport=sport, boucle=lambda: journal.lire_meta("boucle"))
    dernier, prochaine_notif = 0, 0
    try:
        while True:
            for e in journal.lire(apres=dernier):
                dernier = e[0]
                annonceur.traiter(e)
            if journal.etat() in (None, "fin"):
                break
            if time.time() >= prochaine_notif:
                prochaine_notif = time.time() + 5
                try:
                    notif.montrer(titre, resume(annonceur.course, sport))
                except Exception:  # la notification n'est qu'un affichage : le suivi continue
                    pass
            time.sleep(1)
    finally:
        lm.removeUpdates(ecoute)
        if baro:
            sm.unregisterListener(baro)
        verrou.release()
        voix.fermer()
        journal.fermer()
        service.stopSelf()


principal()
