[app]
title = TikTokLiveMobile
package.name = tiktoklivemobile
package.domain = org.nont
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,mp3,wav,ogg,json

# ใส่ requirements ให้ครบถ้วนเพื่อป้องกันแอปเด้ง
requirements = python3,kivy==2.2.1,plyer,TikTokLive,openssl,certifi,chardet,idna,urllib3,requests,aiohttp,websockets

version = 0.1
orientation = portrait
fullscreen = 0

android.permissions = INTERNET, ACCESS_NETWORK_STATE, WAKE_LOCK
android.api = 31
android.minapi = 21
android.ndk = 25b
android.private_storage = True
android.accept_sdk_license = True
p4a.branch = master

[buildozer]
log_level = 2
warn_on_root = 0
