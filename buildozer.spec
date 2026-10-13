[app]
# (str) Title of your application
title = حساباتي - محاسبة
# (str) Package name
package.name = hesabati
# (str) Package domain (needed for android/ios packaging)
package.domain = org.hesabati
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,db
version = 0.1.0
requirements = python3,kivy
orientation = portrait
fullscreen = 0
android.api = 33
android.minapi = 23
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = True
android.logcat_filters = *:S python:D

[buildozer]
log_level = 2
warn_on_root = 1
