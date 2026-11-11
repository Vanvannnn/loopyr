[app]
title = Loopy
package.name = starva
package.domain = org.starva
source.dir = .
source.include_exts = py,ttf,brf
icon.filename = %(source.dir)s/logo/icone.png
presplash.filename = %(source.dir)s/logo/lancement.png
android.presplash_color = #F4EFE6
source.exclude_dirs = tests, bin, .venv, .git, logo, serveur, website, outils, docs
source.exclude_patterns = requirements-*.txt, compte_rendu*.md
version = 0.5
# openssl + certifi : HTTPS (moteur d'itinéraires, tuiles OSM, serveur Loopy) avec des certificats à jour
requirements = hostpython3==3.11.5,python3==3.11.5,kivy==2.3.1,plyer,pyjnius,sqlite3,android,openssl,certifi
orientation = portrait
# GPS de la sortie : premier plan, même écran verrouillé ; sticky : relancé si Android le tue, et il survit quand
# on balaie l'app des applis récentes (classe Java org.starva.starva.ServiceSuivi).
# package.name et package.domain restent « starva » : les changer créerait une autre app et ferait perdre
# l'historique déjà enregistré sur le téléphone. Le nom affiché partout est « Loopy » (title).
services = Suivi:service/suivi.py:foreground:sticky:foregroundServiceType=location
android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_FINE_LOCATION,ACCESS_COARSE_LOCATION,FOREGROUND_SERVICE,FOREGROUND_SERVICE_LOCATION,POST_NOTIFICATIONS,WAKE_LOCK,VIBRATE,REQUEST_IGNORE_BATTERY_OPTIMIZATIONS
android.api = 33
android.minapi = 24
android.archs = arm64-v8a
# java/ : petites classes Java (écoute de la boussole sans rappel vers Python)
android.add_src = java
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
