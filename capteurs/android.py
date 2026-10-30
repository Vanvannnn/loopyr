"""Petits accès à Android via pyjnius (téléphone uniquement : ne pas importer sur PC)."""
from jnius import autoclass, cast

PAQUET = "org.starva.starva"  # package.domain + package.name de buildozer.spec


def activite():
    return autoclass("org.kivy.android.PythonActivity").mActivity


def systeme(contexte, nom, classe):
    """Service système Android (ex. 'location', 'sensor'), converti dans sa classe Java."""
    return cast(classe, contexte.getSystemService(nom))


def version_sdk():
    return autoclass("android.os.Build$VERSION").SDK_INT


def chaine(texte):
    return autoclass("java.lang.String")(texte)
