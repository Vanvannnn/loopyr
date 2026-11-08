"""Export d'un fichier GPX : Téléchargements/Loopy sur Android (puis menu Partager), un dossier local sur PC."""
import os

from kivy.utils import platform


def exporter(nom_fichier, texte, dossier_pc):
    """Écrit le fichier. Renvoie un message pour l'utilisateur."""
    if platform != "android":
        os.makedirs(dossier_pc, exist_ok=True)
        chemin = os.path.join(dossier_pc, nom_fichier)
        with open(chemin, "w", encoding="utf-8") as f:
            f.write(texte)
        return f"GPX enregistré : {chemin}"

    from jnius import autoclass, cast
    from capteurs.android import activite, chaine, version_sdk
    if version_sdk() < 29:
        return "L'export GPX demande Android 10 ou plus"
    act = activite()
    valeurs = autoclass("android.content.ContentValues")()
    valeurs.put("_display_name", nom_fichier)
    valeurs.put("mime_type", "application/gpx+xml")
    valeurs.put("relative_path", "Download/Loopy")
    resolver = act.getContentResolver()
    uri = resolver.insert(autoclass("android.provider.MediaStore$Downloads").EXTERNAL_CONTENT_URI, valeurs)
    sortie = resolver.openOutputStream(uri)
    sortie.write(texte.encode("utf-8"))
    sortie.close()

    Intent = autoclass("android.content.Intent")
    envoi = Intent(Intent.ACTION_SEND)
    envoi.setType("application/gpx+xml")
    envoi.putExtra(Intent.EXTRA_STREAM, cast("android.os.Parcelable", uri))
    envoi.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    act.startActivity(Intent.createChooser(envoi, chaine("Partager la course")))
    return "GPX enregistré dans Téléchargements/Loopy"


def ouvrir_url(url):
    """Ouvre une page dans le navigateur (connexion à Strava, espace web)."""
    if platform != "android":
        import webbrowser
        webbrowser.open(url)
        return
    from jnius import autoclass
    from capteurs.android import activite
    Intent, Uri = autoclass("android.content.Intent"), autoclass("android.net.Uri")
    activite().startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
