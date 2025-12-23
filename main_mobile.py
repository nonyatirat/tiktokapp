import threading
import asyncio
import json
import os
import urllib.request
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.clock import mainthread
from kivy.core.audio import SoundLoader
from kivy.storage.jsonstore import JsonStore
from plyer import tts

# นำเข้าไลบรารี TikTokLive
from TikTokLive import TikTokLiveClient
from TikTokLive.events import (
    ConnectEvent, DisconnectEvent, CommentEvent, 
    JoinEvent, LikeEvent, ShareEvent, FollowEvent, GiftEvent
)

# ==========================================
# ⚙️ การตั้งค่าและข้อมูลพื้นฐาน (Config)
# ==========================================
PROFILES_URL = "https://drive.google.com/uc?export=download&id=1JwYT50rCTKsbsTHZUYmnJOjgI_rbtvH_"
SOUND_DIR = "sound"  # โฟลเดอร์เก็บไฟล์เสียง

MESSAGES = {
    "Join": "ยินดีต้อนรับ {name} ค่ะ",
    "Like": "ขอบคุณ {name} ที่กดถูกใจค่ะ",
    "Share": "ขอบคุณ {name} ที่แชร์ไลฟ์ค่ะ",
    "Follow": "ขอบคุณ {name} ที่กดติดตามค่ะ",
    "Gift": "ขอบคุณ {name} ส่ง {gift} ให้ค่ะ",
    "Welcome": "กำลังเชื่อมต่อช่อง {name}",
    "Connect": "เชื่อมต่อสำเร็จแล้วค่ะ",
    "Disconnect": "สัญญาณหลุดค่ะ"
}

# ==========================================
# 🔊 ระบบจัดการเสียง (Mobile Audio Manager)
# ==========================================
class MobileAudioManager:
    def speak(self, text):
        try:
            print(f"Speaking: {text}")
            tts.speak(text)
        except Exception as e:
            print(f"TTS Error: {e}")

    def play_sfx(self, event_name):
        try:
            for ext in ['.mp3', '.wav', '.ogg']:
                filename = os.path.join(SOUND_DIR, f"{event_name}{ext}")
                if os.path.exists(filename):
                    sound = SoundLoader.load(filename)
                    if sound:
                        sound.play()
                    break
        except Exception as e:
            print(f"SFX Error: {e}")

audio_mgr = MobileAudioManager()

# ==========================================
# 🔐 หน้าจอที่ 1: ตรวจสอบสิทธิ์ (Login Screen)
# ==========================================
class LoginScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.store = JsonStore("user_settings.json")
        layout = BoxLayout(orientation='vertical', padding=30, spacing=20)

        layout.add_widget(Label(text="ลงทะเบียนใช้งาน (Mobile)", font_size='24sp', bold=True, size_hint=(1, 0.2)))

        self.txt_username = TextInput(hint_text="กรอกชื่อช่อง TikTok ของคุณ", multiline=False, size_hint=(1, 0.15))
        if self.store.exists('user'):
            self.txt_username.text = self.store.get('user')['username']
        layout.add_widget(self.txt_username)

        self.lbl_status = Label(text="กรุณาตรวจสอบสิทธิ์ก่อนใช้งาน", color=(1, 1, 0, 1), size_hint=(1, 0.1))
        layout.add_widget(self.lbl_status)

        self.btn_check = Button(text="ตรวจสอบสิทธิ์ (Check License)", size_hint=(1, 0.15), background_color=(0, 0.5, 1, 1))
        self.btn_check.bind(on_press=self.check_license)
        layout.add_widget(self.btn_check)

        self.add_widget(layout)

    def check_license(self, instance):
        username = self.txt_username.text.strip()
        if not username:
            self.lbl_status.text = "กรุณากรอกชื่อช่องก่อนครับ"
            return

        self.lbl_status.text = "กำลังตรวจสอบกับ Server..."
        audio_mgr.speak("กำลังตรวจสอบสิทธิ์")
        threading.Thread(target=self._do_fetch, args=(username,), daemon=True).start()

    def _do_fetch(self, username):
        try:
            with urllib.request.urlopen(PROFILES_URL, timeout=10) as url:
                data = json.loads(url.read().decode())
            
            found = False
            user_data = None
            
            for profile in data:
                if profile.get('username', '').lower() == username.lower():
                    found = True
                    user_data = profile
                    break
            
            self._on_result(found, user_data, username)
        except Exception as e:
            self._update_label(f"เชื่อมต่อล้มเหลว: {e}", (1, 0, 0, 1))

    @mainthread
    def _update_label(self, text, color):
        self.lbl_status.text = text
        self.lbl_status.color = color

    @mainthread
    def _on_result(self, found, user_data, username):
        if found:
            name = user_data.get('name', 'User')
            self.lbl_status.text = f"อนุญาต: {name}"
            self.lbl_status.color = (0, 1, 0, 1)
            audio_mgr.speak(f"ยินดีต้อนรับ {name}")
            self.store.put('user', username=username, name=name)
            self.manager.current = 'dashboard'
        else:
            self.lbl_status.text = "ไม่พบสิทธิ์การใช้งานช่องนี้"
            self.lbl_status.color = (1, 0, 0, 1)
            audio_mgr.speak("ไม่พบสิทธิ์การใช้งาน")

# ==========================================
# 📺 หน้าจอที่ 2: แดชบอร์ด (Live Dashboard)
# ==========================================
class DashboardScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.client = None
        self.loop = None
        self.is_running = False

        layout = BoxLayout(orientation='vertical', padding=20, spacing=10)
        
        self.lbl_title = Label(text="พร้อมใช้งาน", font_size='20sp', size_hint=(1, 0.1))
        layout.add_widget(self.lbl_title)

        self.btn_action = Button(text="เริ่มเชื่อมต่อ (Start)", size_hint=(1, 0.15), background_color=(0, 0.8, 0, 1))
        self.btn_action.bind(on_press=self.toggle_live)
        layout.add_widget(self.btn_action)

        self.scroll = ScrollView(size_hint=(1, 0.7))
        self.lbl_log = Label(text="Log เริ่มต้น...\n", size_hint_y=None, markup=True, halign='left', valign='top')
        self.lbl_log.bind(texture_size=self.lbl_log.setter('size'))
        self.scroll.add_widget(self.lbl_log)
        layout.add_widget(self.scroll)

        btn_back = Button(text="เปลี่ยนบัญชี", size_hint=(1, 0.1))
        btn_back.bind(on_press=self.go_back)
        layout.add_widget(btn_back)

        self.add_widget(layout)

    def on_enter(self):
        store = JsonStore("user_settings.json")
        if store.exists('user'):
            self.username = store.get('user')['username']
            self.lbl_title.text = f"ช่อง: {self.username}"

    def toggle_live(self, instance):
        if not self.is_running:
            self.is_running = True
            self.btn_action.text = "หยุด (Stop)"
            self.btn_action.background_color = (1, 0, 0, 1)
            
            msg = MESSAGES["Welcome"].format(name=self.username)
            self.log(msg)
            audio_mgr.speak(msg)
            
            threading.Thread(target=self.run_client, daemon=True).start()
        else:
            self.is_running = False
            self.btn_action.text = "เริ่มเชื่อมต่อ (Start)"
            self.btn_action.background_color = (0, 0.8, 0, 1)
            self.stop_client()

    def run_client(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.client = TikTokLiveClient(unique_id=self.username)

        @self.client.on(ConnectEvent)
        async def on_connect(e):
            self.log("[color=00ff00]Connected![/color]")
            audio_mgr.speak(MESSAGES["Connect"])
            audio_mgr.play_sfx("Connect")

        @self.client.on(DisconnectEvent)
        async def on_disconnect(e):
            self.log("[color=ff0000]Disconnected[/color]")
            audio_mgr.speak(MESSAGES["Disconnect"])
            audio_mgr.play_sfx("Disconnect")

        @self.client.on(CommentEvent)
        async def on_comment(e):
            self.log(f"{e.user.nickname}: {e.comment}")
            audio_mgr.speak(f"{e.user.nickname} บอกว่า {e.comment}")

        @self.client.on(GiftEvent)
        async def on_gift(e):
            msg = MESSAGES["Gift"].format(name=e.user.nickname, gift=e.gift.info.name)
            self.log(f"[color=ffff00]GIFT: {e.gift.info.name}[/color]")
            audio_mgr.speak(msg)
            audio_mgr.play_sfx("Gift")

        @self.client.on(LikeEvent)
        async def on_like(e):
            pass 

        @self.client.on(ShareEvent)
        async def on_share(e):
            msg = MESSAGES["Share"].format(name=e.user.nickname)
            self.log("Share received")
            audio_mgr.speak(msg)
            audio_mgr.play_sfx("Share")

        @self.client.on(FollowEvent)
        async def on_follow(e):
            msg = MESSAGES["Follow"].format(name=e.user.nickname)
            self.log("New Follower")
            audio_mgr.speak(msg)
            audio_mgr.play_sfx("Follow")

        @self.client.on(JoinEvent)
        async def on_join(e):
            msg = MESSAGES["Join"].format(name=e.user.nickname)
            self.log(f"Join: {e.user.nickname}")
            audio_mgr.speak(msg)
            audio_mgr.play_sfx("Join")

        try:
            self.client.run()
        except Exception as e:
            self.log(f"Error: {e}")
            self.is_running = False
            self.reset_ui()

    def stop_client(self):
        if self.client and self.loop:
            asyncio.run_coroutine_threadsafe(self.client.stop(), self.loop)

    def go_back(self, instance):
        if self.is_running: self.stop_client()
        self.manager.current = 'login'

    @mainthread
    def log(self, text):
        if len(self.lbl_log.text) > 3000: self.lbl_log.text = self.lbl_log.text[-1000:]
        self.lbl_log.text += f"\n{text}"

    @mainthread
    def reset_ui(self):
        self.btn_action.text = "เริ่มเชื่อมต่อ (Start)"
        self.btn_action.background_color = (0, 0.8, 0, 1)

class TikTokApp(App):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(LoginScreen(name='login'))
        sm.add_widget(DashboardScreen(name='dashboard'))
        return sm

if __name__ == '__main__':
    if not os.path.exists(SOUND_DIR):
        os.makedirs(SOUND_DIR)
    TikTokApp().run()