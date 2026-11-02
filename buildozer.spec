[app]
title = Loopy
package.name = starva
package.domain = org.starva
source.dir = .
source.include_exts = py,db,ttf
icon.filename = %(source.dir)s/logo/icone.png
presplash.filename = %(source.dir)s/logo/lancement.png
android.presplash_color = #F4EFE6
source.exclude_dirs = tests, cache, bin, .venv, .git, logo
source.exclude_patterns = prepare_data.py, elev_cache.json, requirements-*.txt
version = 0.3
requirements = hostpython3==3.11.5,python3==3.11.5,kivy==2.3.1,plyer,pyjnius,sqlite3,android
orientation = portrait
# GPS de la course : tourne en premier plan, même écran éteint (classe Java org.starva.starva.ServiceSuivi)
services = Suivi:service/suivi.py:foreground:foregroundServiceType=location
android.permissions = ACCESS_FINE_LOCATION,ACCESS_COARSE_LOCATION,FOREGROUND_SERVICE,FOREGROUND_SERVICE_LOCATION,POST_NOTIFICATIONS,WAKE_LOCK,VIBRATE
android.api = 33
android.minapi = 24
android.archs = arm64-v8a
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
