[app]
title = Starva
package.name = starva
package.domain = org.starva
source.dir = .
source.include_exts = py,db
version = 0.1
requirements = hostpython3==3.11.5,python3==3.11.5,kivy==2.3.1,plyer,pyjnius,sqlite3,android
orientation = portrait
android.permissions = ACCESS_FINE_LOCATION,ACCESS_COARSE_LOCATION
android.archs = arm64-v8a
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
