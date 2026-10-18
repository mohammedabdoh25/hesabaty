[app]
title = حساباتي - محاسبة
package.name = hesabati
package.domain = org.hesabati
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,db
version = 0.1.0
requirements = python3,kivy
orientation = portrait
fullscreen = 0

# Android build settings
android.api = 35
android.minapi = 26
android.ndk = 28c
android.ndk_api = 26
android.archs = arm64-v8a + armeabi-v7a
android.accept_sdk_license = True
android.allow_backup = True
android.logcat_filters = *:S python:D

[buildozer]
log_level = 2
warn_on_root = 1
