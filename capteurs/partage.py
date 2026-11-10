"""Fichiers GPX : téléchargement direct sur le téléphone, et partage, deux actions indépendantes.

Android 10+ : le fichier est écrit dans Téléchargements/Loopy par le MediaStore (aucune autorisation demandée,
visible dans l'appli Fichiers et proposé par le sélecteur de fichiers du navigateur, pour l'import sur
strava.com). Un même fichier retéléchargé remplace le précédent au lieu de créer « nom (1).gpx ».
Partager ouvre le menu natif d'Android (messagerie, Drive, une autre app…) avec ce fichier.
Sur PC : un dossier local (exports)."""
import os

from kivy.utils import platform

DOSSIER = "Download/Loopy/"
TYPE = "application/gpx+xml"


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


def telecharger(nom_fichier, texte, dossier_pc):
    """Enregistre le fichier sur l'appareil. Renvoie le message à afficher."""
    if platform != "android":
        return f"GPX enregistré : {_pc(nom_fichier, texte, dossier_pc)}"
    from capteurs.android import version_sdk
    if version_sdk() < 29:
        return "Le téléchargement direct demande Android 10 ou plus : utilise Partager"
    _ecrire_android(nom_fichier, texte)
    return f"Téléchargé : Téléchargements/Loopy/{nom_fichier}"


def partager(nom_fichier, texte, dossier_pc):
    """Ouvre le menu de partage d'Android avec le fichier. Renvoie le message à afficher."""
    if platform != "android":
        return f"Partage disponible sur le téléphone. Fichier : {_pc(nom_fichier, texte, dossier_pc)}"
    from jnius import autoclass, cast
    from capteurs.android import activite, chaine, version_sdk
    if version_sdk() < 29:
        return "Le partage de fichier demande Android 10 ou plus"
    uri = _ecrire_android(nom_fichier, texte)
    Intent = autoclass("android.content.Intent")
    envoi = Intent(Intent.ACTION_SEND)
    envoi.setType(TYPE)
    envoi.putExtra(Intent.EXTRA_STREAM, cast("android.os.Parcelable", uri))
    envoi.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    activite().startActivity(Intent.createChooser(envoi, chaine("Partager le GPX")))
    return "Choisis où envoyer le fichier (il est aussi dans Téléchargements/Loopy)"


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
