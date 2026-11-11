"""Fichiers GPX : téléchargement direct sur le téléphone.

Android 10+ : le fichier est écrit dans Téléchargements/Loopy par le MediaStore (aucune autorisation demandée,
visible dans l'appli Fichiers et proposé par le sélecteur de fichiers du navigateur, pour l'import sur
strava.com). Un même fichier retéléchargé remplace le précédent au lieu de créer « nom (1).gpx ».
Une notification « GPX téléchargé » suit : la toucher ouvre le fichier dans l'appli choisie (Komoot, un compteur…).
Sur PC : un dossier local (exports)."""
import os
import zlib

from kivy.utils import platform

DOSSIER = "Download/Loopy/"
TYPE = "application/gpx+xml"
CANAL = "loopy_fichiers"


def _pc(nom_fichier, texte, dossier_pc):
    os.makedirs(dossier_pc, exist_ok=True)
    chemin = os.path.join(dossier_pc, nom_fichier)
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(texte)
    return chemin


def _ecrire_android(nom_fichier, texte):
    """Écrit (ou réécrit) Téléchargements/Loopy/nom_fichier. Renvoie l'URI content:// du fichier."""
    from jnius import autoclass
    from capteurs.android import activite
    Downloads = autoclass("android.provider.MediaStore$Downloads")
    resolver = activite().getContentResolver()
    uri = None
    try:  # déjà téléchargé par cette installation : on le remplace
        curseur = resolver.query(Downloads.EXTERNAL_CONTENT_URI, ["_id"],
                                 "relative_path=? AND _display_name=?", [DOSSIER, nom_fichier], None)
        if curseur is not None:
            if curseur.moveToFirst():
                uri = autoclass("android.content.ContentUris").withAppendedId(Downloads.EXTERNAL_CONTENT_URI,
                                                                              curseur.getLong(0))
            curseur.close()
    except Exception:
        uri = None
    sortie = None
    if uri is not None:
        try:
            sortie = resolver.openOutputStream(uri, "wt")
        except Exception:  # fichier créé par une installation précédente : on en crée un nouveau
            uri = None
    if uri is None:
        valeurs = autoclass("android.content.ContentValues")()
        valeurs.put("_display_name", nom_fichier)
        valeurs.put("mime_type", TYPE)
        valeurs.put("relative_path", DOSSIER)
        uri = resolver.insert(Downloads.EXTERNAL_CONTENT_URI, valeurs)
        if uri is None:
            raise OSError("Android a refusé de créer le fichier")
        sortie = resolver.openOutputStream(uri)
    sortie.write(texte.encode("utf-8"))
    sortie.flush()
    sortie.close()
    return uri


def _notifier(nom_fichier, uri):
    """Notification système « GPX téléchargé » ; la toucher propose les applis qui ouvrent le fichier.
    Notifications refusées (Android 13+) : Android ne l'affiche pas, le message dans l'app suffit."""
    try:
        from jnius import autoclass, cast
        from capteurs.android import activite, chaine, version_sdk
        act, sdk = activite(), version_sdk()
        nm = cast("android.app.NotificationManager", act.getSystemService("notification"))
        if sdk >= 26:
            NM = autoclass("android.app.NotificationManager")
            nm.createNotificationChannel(autoclass("android.app.NotificationChannel")(
                CANAL, chaine("Fichiers téléchargés"), NM.IMPORTANCE_DEFAULT))
        Intent, PI = autoclass("android.content.Intent"), autoclass("android.app.PendingIntent")
        voir = Intent(Intent.ACTION_VIEW)
        voir.setDataAndType(uri, TYPE)
        voir.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        ouvrir = Intent.createChooser(voir, chaine("Ouvrir le GPX avec"))  # garde l'autorisation de lecture
        num = 1000 + zlib.crc32(nom_fichier.encode()) % 100000  # même fichier : même notification, remplacée
        pi = PI.getActivity(act, num, ouvrir, PI.FLAG_IMMUTABLE | PI.FLAG_UPDATE_CURRENT)
        B = autoclass("android.app.Notification$Builder")
        b = B(act, CANAL) if sdk >= 26 else B(act)
        b.setContentTitle(cast("java.lang.CharSequence", chaine("GPX téléchargé")))
        b.setContentText(cast("java.lang.CharSequence", chaine(f"{nom_fichier} · touche pour l'ouvrir")))
        b.setSmallIcon(act.getApplicationInfo().icon)
        b.setContentIntent(pi)
        b.setAutoCancel(True)
        nm.notify(num, b.build())
    except Exception as err:  # le fichier est bien enregistré : une notification manquée ne doit pas l'annuler
        print(f"[Loopy] notification GPX impossible : {err}", flush=True)


def telecharger(nom_fichier, texte, dossier_pc):
    """Enregistre le fichier sur l'appareil. Renvoie le message à afficher."""
    if platform != "android":
        return f"GPX enregistré : {_pc(nom_fichier, texte, dossier_pc)}"
    from capteurs.android import version_sdk
    if version_sdk() < 29:
        return "Le téléchargement du GPX demande Android 10 ou plus"
    _notifier(nom_fichier, _ecrire_android(nom_fichier, texte))
    return f"Téléchargé : Téléchargements/Loopy/{nom_fichier}"


def exporter(nom_fichier, texte, dossier_pc):
    """Ancien nom : téléchargement direct."""
    return telecharger(nom_fichier, texte, dossier_pc)


def ouvrir_url(url):
    """Ouvre une page dans le navigateur (connexion à Strava, espace web, import Strava)."""
    if platform != "android":
        import webbrowser
        webbrowser.open(url)
        return
    from jnius import autoclass
    from capteurs.android import activite
    Intent, Uri = autoclass("android.content.Intent"), autoclass("android.net.Uri")
    activite().startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
