import os
import queue
import sys
import uuid
import time
import threading
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox

import keyboard
import mouse
import pygame
from datetime import datetime
from pathlib import Path

import requests
import customtkinter as ctk
from PIL import Image

from controller_profiles import ps5, xbox
from license_storage import forget_remembered_key, load_remembered_key, save_remembered_key
from alpha_boost import (
    BOOST_FILENAME,
    AlphaBoostError,
    AlphaBoostManager,
    GameInstallation,
    detect_installations,
    resolve_cooked_dir,
    store_modified_file,
)

HORSE_ENTRY = (
    ('down', 'jump'), ('wait', .064), ('up', 'jump'), ('wait', .064),
    ('down', 's'), ('wait', .064), ('up', 's'), ('wait', .064),
    ('down', 'd'), ('wait', .064), ('up', 'd'), ('wait', .064),
    ('wait', .064), ('down', 'e'), ('wait', .064), ('up', 'e'),
    ('wait', .064), ('wait', .48), ('down', 'w'), ('down', 'jump'),
    ('wait', .07), ('up', 'jump'), ('wait', .045), ('up', 'w'), ('wait', .04),
)
HORSE_PAIR = (
    ('down', 's'), ('down', 'jump'), ('wait', .045), ('up', 'jump'),
    ('wait', .045), ('up', 's'), ('wait', .045), ('down', 'w'),
    ('down', 'jump'), ('wait', .045), ('up', 'jump'), ('wait', .045),
    ('up', 'w'), ('wait', .045),
)
MACROS = ['Infinite Dash', 'Stall', 'HorseDash']
CONTROLLER_PLATFORMS = {'Xbox': xbox, 'PS5': ps5}
DEFAULT_CONTROLLER_PLATFORM = 'Xbox'
ACCENT = '#A855F7'
BG = ('#09070D', '#09070D')
CARD = ('#15101D', '#15101D')
SIDE = ('#100C17', '#100C17')
FG = ('#F8F4FC', '#F8F4FC')
MUTED = ('#A99BB8', '#A99BB8')
GREEN = '#42E6A4'
STALL_STEPS = (
    ('press', 'q'), ('wait', .001), ('release', 'q'),
    ('press', 'e'), ('wait', .001), ('release', 'e'),
    ('mouse_press', 'right'), ('wait', .001), ('mouse_release', 'right'),
)

# URL publique de l'API (sans slash final). Surchargeable avec MACRO_API_URL.
def load_api_url():
    configured_url = os.environ.get('MACRO_API_URL', '').strip()
    if configured_url:
        return configured_url.rstrip('/')

    bundle_dir = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
    try:
        return (bundle_dir / 'api_url.txt').read_text(encoding='utf-8').strip().rstrip('/')
    except FileNotFoundError:
        return ''


API_URL = load_api_url()


# Donnees conservees dans le profil Windows (le dossier d'un .exe PyInstaller est temporaire).
DEVICE_DIR = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'MacroClientV6'
DEVICE_FILE = DEVICE_DIR / 'device_id.txt'
CONTROLLER_PLATFORM_FILE = DEVICE_DIR / 'controller-platform.txt'
REMEMBERED_KEY_FILE = DEVICE_DIR / 'remembered-key.dat'
ALPHA_INSTALL_FILE = DEVICE_DIR / 'alpha-boost-install.txt'
ALPHA_MOD_FILE = DEVICE_DIR / 'alpha-boost-source.txt'


def load_controller_platform():
    try:
        platform = CONTROLLER_PLATFORM_FILE.read_text(encoding='utf-8').strip()
    except FileNotFoundError:
        return DEFAULT_CONTROLLER_PLATFORM, None
    except OSError as error:
        return DEFAULT_CONTROLLER_PLATFORM, str(error)
    if platform not in CONTROLLER_PLATFORMS:
        return DEFAULT_CONTROLLER_PLATFORM, f'Profil de manette invalide : {platform!r}'
    return platform, None


def save_controller_platform(platform):
    if platform not in CONTROLLER_PLATFORMS:
        raise ValueError(f'Profil de manette inconnu : {platform!r}')
    DEVICE_DIR.mkdir(parents=True, exist_ok=True)
    CONTROLLER_PLATFORM_FILE.write_text(platform, encoding='utf-8')


def get_device_id():
    DEVICE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        existing = DEVICE_FILE.read_text(encoding='utf-8').strip()
        return str(uuid.UUID(existing))
    except FileNotFoundError:
        pass
    except ValueError:
        raise OSError('Identifiant d installation invalide')

    device_id = str(uuid.uuid4())
    try:
        with DEVICE_FILE.open('x', encoding='utf-8') as f:
            f.write(device_id)
        return device_id
    except FileExistsError:
        return str(uuid.UUID(DEVICE_FILE.read_text(encoding='utf-8').strip()))


def validate_key(key):
    if not API_URL:
        return False, 'Serveur de licence non configuré. Contactez le support.', None
    try:
        response = requests.post(API_URL + '/v1/validate', json={'key': key, 'device_id': get_device_id()}, timeout=8)
        response.raise_for_status()
        data = response.json()
        if not data.get('valid'):
            return False, data.get('message', 'Licence invalide'), None
        # expires_at vaut None pour une licence a vie.
        raw = data.get('expires_at')
        expiry = datetime.fromisoformat(raw.replace('Z', '+00:00')) if raw else None
        return True, 'Licence active', expiry
    except OSError:
        return False, 'Impossible de sauvegarder l identifiant de ce PC.', None
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return False, 'Serveur indisponible. Verifiez Internet.', None


def expiry_text(expiry):
    return 'a vie' if expiry is None else "jusqu'au " + expiry.astimezone().strftime('%d/%m/%Y')


# Macros: controlees exclusivement par les interrupteurs de l'interface.
class MacroEngine:
    def __init__(self, controller_platform=DEFAULT_CONTROLLER_PLATFORM):
        self.enabled = {name: False for name in MACROS}
        self.stop_event = threading.Event()
        self.horse_cancel_event = threading.Event()
        self.thread = None
        self.lock = threading.Lock()
        self.controller_name = None
        self.controller_platform = controller_platform
        self.horse_active = False
        self.horse_steps = HORSE_ENTRY
        self.horse_step_index = 0
        self.horse_next_step = 0.0
        self.horse_held = set()

    def get_controller_name(self):
        with self.lock:
            return self.controller_name

    def set_controller_name(self, name):
        with self.lock:
            self.controller_name = name

    def get_controller_platform(self):
        with self.lock:
            return self.controller_platform

    def set_controller_platform(self, platform):
        if platform not in CONTROLLER_PLATFORMS:
            raise ValueError(f'Profil de manette inconnu : {platform!r}')
        with self.lock:
            self.controller_platform = platform

    def set_enabled(self, name, value):
        with self.lock:
            if name in self.enabled:
                self.enabled[name] = bool(value)
                if name == 'HorseDash' and not value:
                    self.horse_cancel_event.set()

    def is_enabled(self, name):
        with self.lock:
            return self.enabled.get(name, False)

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        self.horse_cancel_event.set()
        with self.lock:
            for name in self.enabled:
                self.enabled[name] = False

    def action(self, name, steps):
        if not self.is_enabled(name) or self.stop_event.is_set():
            return
        pressed = set()
        pressed_mouse = set()
        try:
            for kind, arg in steps:
                if not self.is_enabled(name) or self.stop_event.is_set():
                    break
                if kind == 'press':
                    keyboard.press(arg)
                    pressed.add(arg)
                elif kind == 'release':
                    keyboard.release(arg)
                    pressed.discard(arg)
                elif kind == 'mouse_press':
                    button = arg or 'right'
                    mouse.press(button)
                    pressed_mouse.add(button)
                elif kind == 'mouse_release':
                    button = arg or 'right'
                    mouse.release(button)
                    pressed_mouse.discard(button)
                elif kind == 'wait':
                    self.stop_event.wait(arg)
        finally:
            for key in pressed:
                keyboard.release(key)
            for button in pressed_mouse:
                mouse.release(button)

    def stall(self):
        self.action('Stall', STALL_STEPS)

    def dash_left(self):
        self.action('Infinite Dash', [('press','q'),('press','w'),('mouse_press',None),('mouse_release',None),('wait',.01),('mouse_press',None),('mouse_release',None),('release','q'),('release','w')])

    def dash_right(self):
        self.action('Infinite Dash', [('press','e'),('press','w'),('mouse_press',None),('mouse_release',None),('wait',.01),('mouse_press',None),('mouse_release',None),('release','e'),('release','w')])

    def toggle_horse_dash(self):
        if not self.is_enabled('HorseDash'):
            return
        if self.horse_active:
            self.cancel_horse_dash()
            return
        self.horse_cancel_event.clear()
        self.horse_active = True
        self.horse_steps = HORSE_ENTRY
        self.horse_step_index = 0
        self.horse_next_step = time.perf_counter()
        print('Horse Dash actif')

    def cancel_horse_dash(self):
        was_active = self.horse_active
        self.horse_active = False
        self.horse_steps = HORSE_ENTRY
        self.horse_step_index = 0
        self.horse_next_step = 0.0
        for key in sorted(self.horse_held, key=lambda held_key: held_key != 'jump'):
            try:
                if key == 'jump':
                    mouse.release('right')
                else:
                    keyboard.release(key)
            except Exception as error:
                print(f'Impossible de relâcher {key} : {error}')
        self.horse_held.clear()
        if was_active:
            print('Horse Dash arrêté')

    def advance_horse_dash(self, now):
        if not self.horse_active:
            return
        if not self.is_enabled('HorseDash') or self.horse_cancel_event.is_set():
            self.horse_cancel_event.clear()
            self.cancel_horse_dash()
            return
        if now < self.horse_next_step:
            return
        try:
            while self.horse_active and now >= self.horse_next_step:
                if self.horse_step_index >= len(self.horse_steps):
                    if self.horse_steps is HORSE_ENTRY:
                        self.horse_steps = HORSE_PAIR
                        self.horse_step_index = 0
                    else:
                        self.horse_step_index = 0

                kind, value = self.horse_steps[self.horse_step_index]
                self.horse_step_index += 1
                if kind == 'down':
                    if value == 'jump':
                        mouse.press('right')
                    else:
                        keyboard.press(value)
                    self.horse_held.add(value)
                elif kind == 'up':
                    if value == 'jump':
                        mouse.release('right')
                    else:
                        keyboard.release(value)
                    self.horse_held.discard(value)
                elif kind == 'wait':
                    self.horse_next_step = now + value
                    return
        except Exception as error:
            print(f'Erreur Horse Dash : {error}')
            self.cancel_horse_dash()

    def run(self):
        pygame.init()
        pygame.joystick.init()
        joystick = None
        last_left = 0.0
        last_right = 0.0
        active_platform = self.get_controller_platform()
        held = {'stall': False, 'horse_dash': False, 'dash_left': False, 'dash_right': False}
        try:
            while not self.stop_event.is_set():
                platform = self.get_controller_platform()
                if platform != active_platform:
                    active_platform = platform
                    held = {name: False for name in held}
                    last_left = 0.0
                    last_right = 0.0
                    self.cancel_horse_dash()
                if pygame.joystick.get_count() == 0:
                    joystick = None
                    self.set_controller_name(None)
                    held = {name: False for name in held}
                    self.cancel_horse_dash()
                    self.stop_event.wait(.5)
                    pygame.event.pump()
                    continue
                if joystick is None:
                    joystick = pygame.joystick.Joystick(0)
                    joystick.init()
                    self.set_controller_name(joystick.get_name())
                for event in pygame.event.get():
                    if event.type == pygame.JOYDEVICEREMOVED:
                        joystick = None
                        self.set_controller_name(None)
                        held = {name: False for name in held}
                        self.cancel_horse_dash()
                    else:
                        updates = CONTROLLER_PLATFORMS[active_platform].read_event(event)
                        for control, pressed in updates.items():
                            was_pressed = held[control]
                            held[control] = pressed
                            if pressed and not was_pressed:
                                if control == 'stall':
                                    self.stall()
                                elif control == 'horse_dash':
                                    self.toggle_horse_dash()
                                elif control == 'dash_left':
                                    last_left = 0.0
                                    self.dash_left()
                                    last_left = time.monotonic()
                                elif control == 'dash_right':
                                    last_right = 0.0
                                    self.dash_right()
                                    last_right = time.monotonic()
                now = time.monotonic()
                self.advance_horse_dash(time.perf_counter())
                if held['dash_left'] and self.is_enabled('Infinite Dash') and now - last_left >= .01:
                    last_left = now
                    self.dash_left()
                elif held['dash_right'] and self.is_enabled('Infinite Dash') and now - last_right >= .01:
                    last_right = now
                    self.dash_right()
                self.stop_event.wait(.001)
        finally:
            self.cancel_horse_dash()
            pygame.quit()


if __name__ == '__main__':
    ctk.set_appearance_mode('dark')
    app = ctk.CTk()
    app.title('ONYX CLIENT  |  V1')
    app.geometry('460x590')
    app.minsize(420, 540)
    app.configure(fg_color=BG)
    asset_dir = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
    logo_path = asset_dir / 'onyx-logo.png'
    icon_path = asset_dir / 'onyx-logo.ico'
    app.iconbitmap(default=str(icon_path))
    with Image.open(logo_path) as source:
        logo_source = source.copy()
    activation_logo = ctk.CTkImage(light_image=logo_source, dark_image=logo_source, size=(148, 148))
    sidebar_logo = ctk.CTkImage(light_image=logo_source, dark_image=logo_source, size=(48, 48))
    dashboard_logo = ctk.CTkImage(light_image=logo_source, dark_image=logo_source, size=(166, 166))
    switches = {name: ctk.BooleanVar(value=False) for name in MACROS}
    session = {'key': None, 'expires': None, 'last_validation': 0.0, 'check_pending': False}
    validation_results = queue.Queue()
    selected_platform, platform_load_error = load_controller_platform()
    platform_state = {'platform': selected_platform, 'load_error': platform_load_error}
    engine = MacroEngine(platform_state['platform'])
    internal_shell = None
    page_container = None
    page_view = None
    page_nav_buttons = {}
    page_routes = {}
    ui_state = {'macro_status': {}, 'macro_cards': {}, 'active_count': None}
    def update_macro(name):
        enabled = switches[name].get() and bool(session['key'])
        engine.set_enabled(name, enabled)
        status = ui_state['macro_status'].get(name)
        status_color = GREEN if enabled else MUTED
        if status is not None:
            status.configure(
                text='ACTIVE' if enabled else 'EN VEILLE',
                text_color=status_color,
                fg_color='#123126' if enabled else '#211B28',
            )
        macro_card = ui_state['macro_cards'].get(name)
        if macro_card is not None:
            macro_card.configure(border_color=ACCENT if enabled else '#30233A')
        active_count = ui_state['active_count']
        if active_count is not None:
            count = sum(1 for switch in switches.values() if switch.get())
            active_count.configure(text=f'{count:02d} / {len(MACROS):02d}')

    def stop_client():
        engine.stop()
        app.destroy()

    app.protocol('WM_DELETE_WINDOW', stop_client)

    def accent():
        return ACCENT

    def clear():
        global internal_shell, page_container, page_view, page_nav_buttons
        for widget in app.winfo_children():
            widget.destroy()
        internal_shell = None
        page_container = None
        page_view = None
        page_nav_buttons = {}

    def set_window_mode(compact):
        screen_width = app.winfo_screenwidth()
        screen_height = app.winfo_screenheight()
        if compact:
            width, height = min(460, screen_width - 40), min(590, screen_height - 80)
            app.minsize(min(420, width), min(540, height))
        else:
            width, height = min(1240, screen_width - 60), min(780, screen_height - 100)
            app.minsize(min(980, width), min(640, height))
        app.resizable(not compact, not compact)
        app.minsize(width, height)
        app.update_idletasks()
        x = max(0, (app.winfo_screenwidth() - width) // 2)
        y = max(0, (app.winfo_screenheight() - height) // 2)
        app.geometry(f'{width}x{height}+{x}+{y}')

    def label(parent, text, size=15, bold=False, color=FG, **kwargs):
        return ctk.CTkLabel(parent, text=text, font=('Arial', size, 'bold' if bold else 'normal'), text_color=color, **kwargs)

    def button(parent, text, command, **kwargs):
        kwargs.setdefault('fg_color', accent())
        kwargs.setdefault('hover_color', accent())
        kwargs.setdefault('height', 44)
        kwargs.setdefault('corner_radius', 12)
        kwargs.setdefault('font', ('Arial', 13, 'bold'))
        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            **kwargs
        )

    def card(parent, **kwargs):
        kwargs.setdefault('fg_color', CARD)
        kwargs.setdefault('corner_radius', 18)
        kwargs.setdefault('border_width', 1)
        kwargs.setdefault('border_color', '#30233A')
        return ctk.CTkFrame(
            parent,
            **kwargs
        )

    def access_ok():
        if not session['key']:
            activation()
            return False
        expiry = session['expires']
        if expiry is not None and expiry <= datetime.now(expiry.tzinfo):
            engine.stop()
            session['key'] = None
            session['expires'] = None
            activation('Votre licence est expiree ou revoquee.')
            return False
        return True

    def request_license_check():
        if not session['key'] or session['check_pending']:
            return
        key = session['key']
        session['check_pending'] = True

        def check():
            validation_results.put((key, *validate_key(key)))

        threading.Thread(target=check, daemon=True).start()

    def poll_license_checks():
        try:
            key, ok, message, expiry = validation_results.get_nowait()
        except queue.Empty:
            pass
        else:
            session['check_pending'] = False
            if key == session['key']:
                session['last_validation'] = time.monotonic()
                if ok:
                    session['expires'] = expiry
                elif message != 'Serveur indisponible. Verifiez Internet.':
                    engine.stop()
                    session['key'] = None
                    session['expires'] = None
                    activation('Votre licence est expiree ou revoquee.')

        if session['key']:
            expiry = session['expires']
            if expiry is not None and expiry <= datetime.now(expiry.tzinfo):
                engine.stop()
                session['key'] = None
                session['expires'] = None
                activation('Votre licence est expiree ou revoquee.')
            elif time.monotonic() - session['last_validation'] >= 300:
                request_license_check()
        app.after(1000, poll_license_checks)

    def layout(active):
        global internal_shell, page_container, page_view, page_nav_buttons
        if not access_ok():
            return None
        if internal_shell is None:
            set_window_mode(False)
            clear()
            internal_shell = ctk.CTkFrame(app, fg_color=BG, corner_radius=0)
            internal_shell.pack(fill='both', expand=True)

            sidebar = ctk.CTkFrame(internal_shell, width=220, fg_color=SIDE, corner_radius=0)
            sidebar.pack(side='left', fill='y')
            sidebar.pack_propagate(False)

            brand = ctk.CTkFrame(sidebar, fg_color='transparent')
            brand.pack(fill='x', padx=19, pady=(23, 24))
            ctk.CTkLabel(brand, text='', image=sidebar_logo).pack(side='left')
            brand_text = ctk.CTkFrame(brand, fg_color='transparent')
            brand_text.pack(side='left', padx=10)
            label(brand_text, 'ONYX', 17, True).pack(anchor='w')
            label(brand_text, 'PERFORMANCE', 9, True, MUTED).pack(anchor='w', pady=(2, 0))

            ctk.CTkFrame(sidebar, height=1, fg_color='#282132').pack(fill='x', padx=18, pady=(0, 20))
            label(sidebar, 'ESPACE DE TRAVAIL', 9, True, MUTED).pack(anchor='w', padx=21, pady=(0, 9))
            navigation = ctk.CTkFrame(sidebar, fg_color='transparent')
            navigation.pack(fill='x', padx=11)
            page_nav_buttons = {}
            pages = ['Accueil', 'Mes macros', 'Alpha Boost', 'Manette', 'Commandes', 'Guide', 'Réglages']
            for index, page in enumerate(pages, start=1):
                nav_button = ctk.CTkButton(
                    navigation,
                    text=f'{index:02d}   {page}',
                    command=lambda selected=page: page_routes[selected](),
                    anchor='w',
                    height=42,
                    corner_radius=10,
                    fg_color='transparent',
                    hover_color='#251B30',
                    text_color=MUTED,
                    font=('Arial', 12, 'bold'),
                )
                nav_button.pack(fill='x', pady=3)
                page_nav_buttons[page] = nav_button

            ctk.CTkFrame(sidebar, height=1, fg_color='#282132').pack(
                side='bottom', fill='x', padx=18, pady=(0, 16)
            )
            label(sidebar, 'ONYX CLIENT', 9, True, MUTED).pack(side='bottom', anchor='w', padx=21, pady=(0, 4))
            label(sidebar, 'Windows  ·  Edition V1', 10, color=FG).pack(
                side='bottom', anchor='w', padx=21, pady=(0, 18)
            )

            main_area = ctk.CTkFrame(internal_shell, fg_color=BG, corner_radius=0)
            main_area.pack(side='left', fill='both', expand=True)
            topbar = ctk.CTkFrame(main_area, height=70, fg_color=SIDE, corner_radius=0)
            topbar.pack(fill='x')
            topbar.pack_propagate(False)
            label(topbar, 'ONYX  /  PERFORMANCE CLIENT', 11, True, MUTED).pack(
                side='left', padx=27
            )

            status = ctk.CTkFrame(topbar, fg_color=CARD, corner_radius=12)
            status.pack(side='right', padx=22, pady=13)
            label(status, '●  LICENCE ACTIVE', 10, True, GREEN).pack(side='left', padx=(12, 8), pady=9)
            label(status, expiry_text(session['expires']), 10, color=MUTED).pack(side='left', padx=(0, 12))

            page_container = ctk.CTkScrollableFrame(
                main_area,
                fg_color=BG,
                corner_radius=0,
                scrollbar_button_color=SIDE,
            )
            page_container.pack(fill='both', expand=True)

        for page, nav_button in page_nav_buttons.items():
            selected = page == active
            nav_button.configure(
                fg_color='#2B1B38' if selected else 'transparent',
                text_color=FG if selected else MUTED,
                hover_color='#352142',
            )
        ui_state['macro_status'].clear()
        ui_state['macro_cards'].clear()
        ui_state['active_count'] = None
        if page_view is not None:
            page_view.destroy()
        page_view = ctk.CTkFrame(page_container, fg_color='transparent', corner_radius=0)
        page_view.pack(fill='x', expand=False)
        return page_view

    def heading(parent, title, subtitle):
        label(parent, 'ONYX WORKSPACE', 9, True, accent()).pack(
            anchor='w', padx=34, pady=(28, 8)
        )
        label(parent, title, 30, True).pack(anchor='w', padx=34, pady=(0, 5))
        label(parent, subtitle, 13, color=MUTED).pack(anchor='w', padx=34, pady=(0, 23))

    def activation(error=''):
        set_window_mode(True)
        clear()
        frame = card(app, width=416, height=526)
        frame.pack(expand=True, padx=18, pady=18)
        frame.pack_propagate(False)
        ctk.CTkLabel(frame, text='', image=activation_logo).pack(pady=(13, 3))
        label(frame, 'Déverrouillez votre espace', 21, True).pack(pady=(0, 4))
        label(frame, 'Entrez votre clé ONYX pour continuer.', 11, color=MUTED).pack(pady=(0, 17))
        label(frame, 'CLÉ DE LICENCE', 9, True, MUTED).pack(anchor='w', padx=28, pady=(0, 7))
        entry = ctk.CTkEntry(
            frame,
            height=44,
            justify='center',
            placeholder_text='ONYX-XXXX-XXXX-XXXX-XXXX',
            corner_radius=11,
            border_color=accent(),
            font=('Arial', 13),
        )
        entry.pack(fill='x', padx=28)
        remember_key = tk.BooleanVar(value=remembered_key is not None)
        ctk.CTkCheckBox(
            frame,
            text='Se souvenir de ma clé d’accès',
            variable=remember_key,
            font=('Arial', 11),
            text_color=FG,
            fg_color=accent(),
            hover_color='#9333EA',
            border_color='#493258',
            checkmark_color=FG,
            corner_radius=5,
        ).pack(anchor='w', padx=28, pady=(10, 0))
        status = label(frame, error, 11, color='#FF6B8A', wraplength=360, justify='left')
        status.pack(anchor='w', padx=28, pady=(8, 2))
        if remembered_key is not None:
            entry.insert(0, remembered_key)

        def submit():
            key = entry.get().strip().upper()
            if not remember_key.get():
                try:
                    forget_remembered_key(REMEMBERED_KEY_FILE)
                except OSError as storage_error:
                    status.configure(
                        text=f'Impossible d’effacer la clé mémorisée : {storage_error}',
                        text_color='#FF6B8A',
                    )
                    return
            ok, msg, expiry = validate_key(key)
            if ok:
                try:
                    if remember_key.get():
                        save_remembered_key(REMEMBERED_KEY_FILE, key)
                except (OSError, ValueError) as storage_error:
                    messagebox.showwarning(
                        'ONYX — clé non mémorisée',
                        f'La licence est valide, mais la préférence de clé n’a pas pu être enregistrée : {storage_error}',
                        parent=app,
                    )
                session['key'] = key
                session['expires'] = expiry
                session['last_validation'] = time.monotonic()
                for name in MACROS:
                    switches[name].set(False)
                    update_macro(name)
                engine.start()
                dashboard()
            else:
                status.configure(text=msg)

        button(frame, 'ACTIVER ONYX  →', submit).pack(fill='x', padx=28, pady=(9, 10))
        label(frame, 'ACTIVATION SÉCURISÉE  ·  WINDOWS 10 / 11', 9, True, MUTED).pack(pady=(0, 12))
        entry.bind('<Return>', lambda event: submit())

    def dashboard():
        content = layout('Accueil')
        if content is None:
            return
        heading(content, 'Votre espace de jeu.', 'Tout est prêt. Configurez votre expérience ONYX.')

        hero = ctk.CTkFrame(content, fg_color=('#1A1124', '#1A1124'), corner_radius=22, border_width=1,
                            border_color='#38234C')
        hero.pack(fill='x', padx=38, pady=(0, 20))
        hero.grid_columnconfigure(0, weight=1)
        copy = ctk.CTkFrame(hero, fg_color='transparent')
        copy.grid(row=0, column=0, sticky='nsew', padx=30, pady=30)
        label(copy, 'PERFORMANCE SYSTEM  /  V1', 10, True, accent()).pack(anchor='w', pady=(0, 12))
        label(copy, 'Votre jeu.\nVos règles.', 32, True, justify='left').pack(anchor='w', pady=(0, 8))
        label(copy, 'Personnalisez votre configuration et gardez vos commandes essentielles à portée de main.',
              13, color=MUTED, wraplength=490, justify='left').pack(anchor='w', pady=(0, 20))
        button(copy, 'CONFIGURER MES MACROS  →', macros_page, width=270).pack(anchor='w')
        button(copy, 'ALPHA BOOST LOCAL  →', alpha_boost_page, width=270).pack(anchor='w', pady=(10, 0))
        art = ctk.CTkFrame(hero, width=178, height=178, corner_radius=22, fg_color='#08060D')
        art.grid(row=0, column=1, padx=(0, 28), pady=22)
        art.grid_propagate(False)
        ctk.CTkLabel(art, text='', image=dashboard_logo).place(relx=.5, rely=.5, anchor='center')

        stats = ctk.CTkFrame(content, fg_color='transparent')
        stats.pack(fill='x', padx=30, pady=(0, 20))
        stats.grid_columnconfigure((0, 1, 2), weight=1)
        active_count = sum(1 for var in switches.values() if var.get())
        for column, (eyebrow, value, detail) in enumerate([
            ('CONFIGURATION', f'{active_count:02d} / {len(MACROS):02d}', 'macros sélectionnées'),
            ('LICENCE ONYX', 'ACTIVE', expiry_text(session['expires'])),
            ('CLIENT WINDOWS', 'V1', 'édition performance'),
        ]):
            tile = card(stats)
            tile.grid(row=0, column=column, padx=8, sticky='nsew')
            label(tile, eyebrow, 9, True, MUTED).pack(anchor='w', padx=17, pady=(17, 7))
            value_label = label(tile, value, 20, True, GREEN if column == 1 else FG)
            value_label.pack(anchor='w', padx=17, pady=(0, 2))
            if column == 0:
                ui_state['active_count'] = value_label
            label(tile, detail, 10, color=MUTED).pack(anchor='w', padx=17, pady=(0, 16))

        quick = card(content)
        quick.pack(fill='x', padx=38, pady=(0, 30))
        label(quick, 'UN CONSEIL POUR COMMENCER', 10, True, accent()).pack(anchor='w', padx=20, pady=(17, 6))
        label(quick, 'Choisissez le profil Xbox ou PS5 correspondant à votre manette, puis activez vos macros.',
              13, color=MUTED, wraplength=700, justify='left').pack(anchor='w', padx=20, pady=(0, 17))

    def macros_page():
        content = layout('Mes macros')
        if content is None:
            return
        heading(
            content,
            'Vos macros, votre style.',
            f'{engine.get_controller_platform()} — HorseDash en haut, Stall en bas, Wavedash à gauche/droite.',
        )
        grid = ctk.CTkFrame(content, fg_color='transparent')
        grid.pack(fill='x', padx=26)
        grid.grid_columnconfigure((0, 1), weight=1)
        ui_state['macro_status'].clear()
        ui_state['macro_cards'].clear()
        descriptions = {
            'Infinite Dash': 'Infinite Wavedash : enchaîne les wave dashes. Le D-pad gauche lance la séquence gauche (Q) et le D-pad droite la séquence droite (E).',
            'Stall': 'Technique aérienne permettant de réaliser un saut supplémentaire tout en limitant la rotation de la voiture. Elle est notamment utilisée pour conserver le contrôle du ballon et effectuer des enchaînements de flip resets.',
            'HorseDash': 'Enchaîne automatiquement le Horse Dash. Appuie sur la flèche du haut pour démarrer, puis à nouveau pour arrêter et relâcher les touches.',
        }
        for i, name in enumerate(MACROS):
            enabled = switches[name].get() and bool(session['key'])
            item = card(
                grid,
                corner_radius=18,
                border_width=1,
                border_color=ACCENT if enabled else '#30233A',
            )
            item.grid(row=i // 2, column=i % 2, padx=8, pady=8, sticky='nsew')
            item.grid_columnconfigure(0, weight=1)
            ui_state['macro_cards'][name] = item
            top = ctk.CTkFrame(item, fg_color='transparent')
            top.grid(row=0, column=0, sticky='ew', padx=19, pady=(17, 13))
            label(top, f'{i + 1:02d}   /   ONYX MOVE', 9, True, accent()).pack(side='left')
            status = ctk.CTkLabel(
                top,
                text='ACTIVE' if switches[name].get() and session['key'] else 'EN VEILLE',
                font=('Arial', 9, 'bold'),
                text_color=GREEN if enabled else MUTED,
                fg_color='#123126' if enabled else '#211B28',
                corner_radius=8,
            )
            status.pack(side='right', padx=1, pady=1)
            ui_state['macro_status'][name] = status

            label(item, name, 19, True).grid(row=1, column=0, sticky='w', padx=19, pady=(0, 6))
            label(item, descriptions[name], 12, color=MUTED, wraplength=390, justify='left').grid(
                row=2, column=0, sticky='w', padx=19, pady=(0, 17)
            )
            divider = ctk.CTkFrame(item, height=1, fg_color='#30283A', corner_radius=0)
            divider.grid(row=3, column=0, sticky='ew', padx=19, pady=(0, 13))
            controls = ctk.CTkFrame(item, fg_color='transparent')
            controls.grid(row=4, column=0, sticky='ew', padx=19, pady=(0, 15))
            label(controls, 'ACTIVATION INSTANTANÉE', 9, True, MUTED).pack(side='left')
            ctk.CTkSwitch(
                controls,
                text='',
                variable=switches[name],
                command=lambda n=name: update_macro(n),
                progress_color=accent(),
                button_hover_color='#C084FC',
                width=42,
                switch_width=42,
                switch_height=22,
            ).pack(side='right')

    def guide_page():
        content = layout('Guide')
        if content is None:
            return
        heading(content, 'Le guide Onyx.', 'Les essentiels pour démarrer et personnaliser votre expérience.')
        sections = [
            ('01  /  Activation', 'Saisissez une clé de licence valide pour ouvrir votre espace.'),
            ('02  /  Mes macros', 'Activez ou désactivez les options; le changement est instantané.'),
            ('03  /  Manette', 'Choisissez le profil Xbox ou PS5 correspondant à votre manette, puis branchez-la.'),
            ('04  /  Thème', 'L’interface Onyx associe un violet néon à un fond noir profond.'),
        ]
        for title, description in sections:
            item = card(content)
            item.pack(fill='x', padx=34, pady=6)
            label(item, title, 14, True, accent()).pack(anchor='w', padx=20, pady=(15, 5))
            label(item, description, 12, color=MUTED, wraplength=650, justify='left').pack(
                anchor='w', padx=20, pady=(0, 15)
            )

    def controller_page():
        content = layout('Manette')
        if content is None:
            return
        heading(content, 'Votre manette.', 'Détection en direct des manettes connectées.')

        platform_card = card(content, corner_radius=22)
        platform_card.pack(fill='x', padx=38, pady=(0, 16))
        label(platform_card, 'PROFIL DE MANETTE', 10, True, MUTED).pack(
            anchor='w', padx=22, pady=(18, 8)
        )
        platform_selector = ctk.CTkSegmentedButton(
            platform_card,
            values=['Xbox', 'PS5'],
            selected_color=accent(),
            selected_hover_color='#9333EA',
            unselected_color=CARD,
            unselected_hover_color='#352142',
            text_color=FG,
        )
        platform_selector.pack(anchor='w', padx=22, pady=(0, 8))
        platform_description = label(
            platform_card,
            '',
            11,
            color=MUTED,
            wraplength=680,
            justify='left',
        )
        platform_description.pack(anchor='w', padx=22, pady=(0, 8))
        platform_error = label(
            platform_card,
            '',
            11,
            color='#F0A84A',
            wraplength=680,
            justify='left',
        )
        platform_error.pack(anchor='w', padx=22, pady=(0, 15))

        def update_platform_description():
            if platform_state['platform'] == 'Xbox':
                platform_description.configure(
                    text='Xbox sélectionné — haut démarre/arrête HorseDash, bas déclenche Stall, gauche/droite lance l’Infinite Wavedash.'
                )
            else:
                platform_description.configure(
                    text='PS5 / PSN sélectionné — haut démarre/arrête HorseDash, bas déclenche Stall, gauche/droite lance l’Infinite Wavedash.'
                )

        def select_controller_platform(platform):
            try:
                save_controller_platform(platform)
            except OSError as error:
                platform_error.configure(text=f'Impossible d’enregistrer ce profil : {error}')
                platform_selector.set(platform_state['platform'])
                return
            platform_state['platform'] = platform
            platform_state['load_error'] = None
            engine.set_controller_platform(platform)
            platform_error.configure(text='')
            update_platform_description()

        platform_selector.configure(command=select_controller_platform)
        platform_selector.set(platform_state['platform'])
        update_platform_description()
        if platform_state['load_error']:
            platform_error.configure(
                text=f'Le profil enregistré n’a pas pu être lu : {platform_state["load_error"]}'
            )

        device_card = card(content, corner_radius=22)
        device_card.pack(fill='x', padx=38, pady=(0, 16))
        label(device_card, 'ÉTAT DU PÉRIPHÉRIQUE', 10, True, MUTED).pack(
            anchor='w', padx=22, pady=(20, 12)
        )
        indicator = ctk.CTkFrame(device_card, width=12, height=12, corner_radius=6, fg_color=MUTED)
        indicator.pack(anchor='w', padx=23, pady=(0, 10))
        device_status = label(device_card, 'Recherche en cours…', 20, True)
        device_status.pack(anchor='w', padx=22, pady=(0, 5))
        device_name = label(device_card, '', 12, color=MUTED)
        device_name.pack(anchor='w', padx=22, pady=(0, 20))

        label(content, 'BRANCHEZ OU DÉBRANCHEZ', 10, True, accent()).pack(
            anchor='w', padx=40, pady=(4, 8)
        )
        label(
            content,
            'Cette page surveille uniquement les manettes. Le statut se met à jour automatiquement.',
            12,
            color=MUTED,
            wraplength=720,
            justify='left',
        ).pack(anchor='w', padx=40, pady=(0, 20))

        def refresh_controller_status():
            if not device_status.winfo_exists():
                return
            name = engine.get_controller_name()
            if name:
                indicator.configure(fg_color=GREEN)
                device_status.configure(
                    text=f'Manette connectée — profil {engine.get_controller_platform()}',
                    text_color=GREEN,
                )
                device_name.configure(text=name)
            else:
                indicator.configure(fg_color='#F0A84A')
                device_status.configure(text='Aucune manette détectée', text_color=FG)
                device_name.configure(text='Branchez une manette USB ou Bluetooth.')
            app.after(750, refresh_controller_status)

        refresh_controller_status()

    def controls_page():
        content = layout('Commandes')
        if content is None:
            return
        platform = engine.get_controller_platform()
        heading(
            content,
            'Commandes manette.',
            f'Profil {platform} — gauche déclenche le Wavedash gauche (Q), droite le Wavedash droite (E).',
        )
        mappings = [
            ('HorseDash', 'Appuyer sur D-pad haut pour démarrer ou arrêter la séquence'),
            ('Stall', 'D-pad bas'),
            ('Infinite Dash — gauche', 'Maintenir le D-pad gauche'),
            ('Infinite Dash — droite', 'Maintenir le D-pad droite'),
        ]
        for title, description in mappings:
            item = card(content)
            item.pack(fill='x', padx=38, pady=6)
            label(item, title, 14, True, accent()).pack(anchor='w', padx=20, pady=(15, 5))
            label(item, description, 12, color=MUTED).pack(anchor='w', padx=20, pady=(0, 15))

    def alpha_boost_page():
        content = layout('Alpha Boost')
        if content is None:
            return
        heading(
            content,
            'Alpha Boost local.',
            'Installe ou restaure le boost Bubble sur une installation Rocket League.',
        )

        notice = card(content)
        notice.pack(fill='x', padx=38, pady=(0, 15))
        label(
            notice,
            'MODIFICATION LOCALE — réservée aux modes hors ligne compatibles avec les mods. '
            f'Sélectionne le fichier de remplacement {BOOST_FILENAME} avant l’activation. '
            'Aucun contournement de l’anti-triche n’est effectué. Cette ressource partagée peut '
            'aussi affecter d’autres voitures utilisant le boost Bubble. L’effet visuel n’a pas '
            'été vérifié en jeu.',
            12,
            color=MUTED,
            wraplength=760,
            justify='left',
        ).pack(anchor='w', padx=20, pady=17)

        installation_card = card(content)
        installation_card.pack(fill='x', padx=38, pady=(0, 15))
        label(installation_card, 'INSTALLATION ROCKET LEAGUE', 10, True, MUTED).pack(
            anchor='w', padx=20, pady=(18, 8)
        )
        try:
            installations = detect_installations()
            discovery_error = ''
        except OSError as error:
            installations = []
            discovery_error = f'La détection des installations a échoué : {error}'

        saved_path = None
        try:
            saved_value = ALPHA_INSTALL_FILE.read_text(encoding='utf-8').strip()
            if saved_value:
                saved_path = resolve_cooked_dir(saved_value)
        except FileNotFoundError:
            pass
        except (OSError, AlphaBoostError) as error:
            discovery_error = f'Le chemin mémorisé n’a pas pu être utilisé : {error}'

        known_paths = {
            os.path.normcase(str(item.cooked_dir.resolve()))
            for item in installations
        }
        if saved_path is not None and os.path.normcase(str(saved_path)) not in known_paths:
            installations.append(GameInstallation('Installation enregistrée', saved_path))

        selected_mod_file = {'value': None}
        stored_mod_file = DEVICE_DIR / 'alpha-boost-source' / BOOST_FILENAME
        try:
            if stored_mod_file.is_file():
                selected_mod_file['value'] = stored_mod_file.resolve()
            else:
                # Upgrade users who previously saved only the Downloads path.
                saved_mod_file = ALPHA_MOD_FILE.read_text(encoding='utf-8').strip()
                selected_mod_file['value'] = store_modified_file(saved_mod_file, stored_mod_file)
        except FileNotFoundError:
            pass
        except (OSError, AlphaBoostError) as error:
            discovery_error = f'Fichier Alpha Boost mémorisé indisponible : {error}'

        manager = {
            'value': AlphaBoostManager(
                selected_mod_file['value'],
                DEVICE_DIR / 'alpha-boost',
            ) if selected_mod_file['value'] else None
        }
        selected_installation = {'value': None}
        options = {}
        selected_path_label = label(
            installation_card,
            'Aucune installation sélectionnée.',
            11,
            color=MUTED,
            wraplength=760,
            justify='left',
        )
        selected_path_label.pack(anchor='w', padx=20, pady=(10, 8))
        selector = ctk.CTkOptionMenu(
            installation_card,
            values=['Aucune installation détectée'],
            command=lambda selected: choose_installation(selected),
            width=430,
            fg_color=CARD,
            button_color=accent(),
            button_hover_color='#9333EA',
        )
        selector.pack(anchor='w', padx=20, pady=(0, 12))
        state_label = label(installation_card, 'État : indéterminé', 15, True)
        state_label.pack(anchor='w', padx=20, pady=(0, 14))
        mod_file_label = label(
            installation_card,
            f'Fichier Alpha Boost enregistré sur ce PC : {selected_mod_file["value"] or "aucun sélectionné"}',
            11,
            color=MUTED,
            wraplength=760,
            justify='left',
        )
        mod_file_label.pack(anchor='w', padx=20, pady=(0, 10))
        feedback = label(
            installation_card,
            discovery_error or (
                'Aucune installation détectée. Utilise le bouton pour choisir son dossier.'
                if not installations else ''
            ),
            11,
            color='#F0A84A' if discovery_error or not installations else MUTED,
            wraplength=760,
            justify='left',
        )
        feedback.pack(anchor='w', padx=20, pady=(0, 8))

        def persist_installation(path):
            DEVICE_DIR.mkdir(parents=True, exist_ok=True)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode='w',
                    encoding='utf-8',
                    dir=DEVICE_DIR,
                    prefix='.alpha-install-',
                    suffix='.tmp',
                    delete=False,
                ) as output:
                    temporary = Path(output.name)
                    output.write(str(path))
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(temporary, ALPHA_INSTALL_FILE)
                temporary = None
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)

        def refresh_installation_state():
            installation = selected_installation['value']
            if installation is None or manager['value'] is None:
                state_label.configure(text='État : indéterminé', text_color='#F0A84A')
                return
            try:
                state = manager['value'].status(installation.cooked_dir)
            except (AlphaBoostError, OSError) as error:
                state = 'indéterminé'
                feedback.configure(text=str(error), text_color='#F0A84A')
            state_label.configure(
                text=f'État : {state}',
                text_color=GREEN if state == 'activé' else FG if state == 'désactivé' else '#F0A84A',
            )

        def choose_installation(selected):
            installation = options.get(selected)
            if installation is None:
                return
            selected_installation['value'] = installation
            selected_path_label.configure(text=str(installation.cooked_dir))
            try:
                persist_installation(installation.cooked_dir)
                feedback.configure(text='', text_color=MUTED)
            except OSError as error:
                feedback.configure(
                    text=f'Le chemin est choisi, mais n’a pas pu être mémorisé : {error}',
                    text_color='#F0A84A',
                )
            refresh_installation_state()

        def register_installation(installation, select=False):
            cooked_dir = installation.cooked_dir.resolve()
            key = os.path.normcase(str(cooked_dir))
            for existing_label, existing in options.items():
                if os.path.normcase(str(existing.cooked_dir.resolve())) == key:
                    if select:
                        selector.set(existing_label)
                        choose_installation(existing_label)
                    return
            display = f'{installation.source} — {cooked_dir}'
            options[display] = GameInstallation(installation.source, cooked_dir)
            selector.configure(values=list(options))
            selector.configure(state='normal')
            if select:
                selector.set(display)
                choose_installation(display)

        selector.configure(state='disabled')
        for item in installations:
            select = saved_path is not None and os.path.normcase(
                str(item.cooked_dir.resolve())
            ) == os.path.normcase(str(saved_path))
            register_installation(item, select=select)
        if saved_path is None and len(installations) == 1:
            first_label = next(iter(options))
            selector.set(first_label)
            choose_installation(first_label)
        elif len(installations) > 1 and saved_path is None:
            selector.set('Choisis une installation')
            selected_path_label.configure(text='Plusieurs installations détectées : choisis celle à modifier.')
        elif not installations:
            selector.set('Aucune installation détectée')

        def choose_mod_file():
            selected = filedialog.askopenfilename(
                parent=app,
                title='Choisir le fichier Alpha Boost',
                filetypes=[('Fichier UPK Alpha Boost', BOOST_FILENAME)],
            )
            if not selected:
                return
            try:
                candidate = store_modified_file(selected, stored_mod_file)
                selected_mod_file['value'] = candidate
                manager['value'] = AlphaBoostManager(candidate, DEVICE_DIR / 'alpha-boost')
                mod_file_label.configure(
                    text=f'Fichier Alpha Boost enregistré sur ce PC : {candidate}'
                )
                feedback.configure(text='', text_color=MUTED)
                refresh_installation_state()
            except OSError as error:
                feedback.configure(
                    text=f'Le fichier Alpha Boost n’a pas pu être enregistré sur ce PC : {error}',
                    text_color='#FF6B8A',
                )
            except AlphaBoostError as error:
                feedback.configure(text=str(error), text_color='#FF6B8A')

        def choose_game_folder():
            selected = filedialog.askdirectory(
                parent=app,
                title='Choisir le dossier Rocket League',
            )
            if not selected:
                return
            try:
                cooked_dir = resolve_cooked_dir(selected)
            except (AlphaBoostError, OSError) as error:
                feedback.configure(text=str(error), text_color='#FF6B8A')
                return
            register_installation(GameInstallation('Dossier choisi', cooked_dir), select=True)

        button(
            installation_card,
            'Choisir le dossier Rocket League',
            choose_game_folder,
            width=300,
        ).pack(anchor='w', padx=20, pady=(0, 17))
        button(
            installation_card,
            'Choisir le fichier Alpha Boost',
            choose_mod_file,
            width=300,
            fg_color='#352142',
            hover_color='#493258',
        ).pack(anchor='w', padx=20, pady=(0, 17))

        actions = ctk.CTkFrame(content, fg_color='transparent')
        actions.pack(fill='x', padx=38, pady=(0, 25))

        def activate_alpha_boost():
            installation = selected_installation['value']
            if installation is None:
                feedback.configure(
                    text='Choisis une installation Rocket League avant de continuer.',
                    text_color='#FF6B8A',
                )
                return
            if manager['value'] is None:
                feedback.configure(
                    text=f'Choisis le fichier de remplacement {BOOST_FILENAME} avant de continuer.',
                    text_color='#FF6B8A',
                )
                return
            try:
                manager['value'].activate(installation.cooked_dir)
                feedback.configure(
                    text='Alpha Boost activé. Ferme le jeu avant toute autre modification.',
                    text_color=GREEN,
                )
            except PermissionError:
                feedback.configure(
                    text='Accès refusé. Ferme Rocket League et vérifie les permissions du dossier. '
                    'L’application ne demande pas les droits administrateur.',
                    text_color='#FF6B8A',
                )
            except (AlphaBoostError, OSError) as error:
                feedback.configure(text=str(error), text_color='#FF6B8A')
            refresh_installation_state()

        def restore_alpha_boost():
            installation = selected_installation['value']
            if installation is None:
                feedback.configure(
                    text='Choisis une installation Rocket League avant de continuer.',
                    text_color='#FF6B8A',
                )
                return
            if manager['value'] is None:
                feedback.configure(
                    text=f'Choisis le fichier de remplacement {BOOST_FILENAME} avant de continuer.',
                    text_color='#FF6B8A',
                )
                return
            try:
                manager['value'].restore(installation.cooked_dir)
                feedback.configure(text='Le fichier sauvegardé a été restauré.', text_color=GREEN)
            except PermissionError:
                feedback.configure(
                    text='Accès refusé. Ferme Rocket League et vérifie les permissions du dossier. '
                    'L’application ne demande pas les droits administrateur.',
                    text_color='#FF6B8A',
                )
            except (AlphaBoostError, OSError) as error:
                feedback.configure(text=str(error), text_color='#FF6B8A')
            refresh_installation_state()

        button(
            actions,
            'Activer Alpha Boost',
            activate_alpha_boost,
            width=230,
        ).pack(side='left', padx=(0, 12))
        button(
            actions,
            'Restaurer',
            restore_alpha_boost,
            width=150,
            fg_color='#352142',
            hover_color='#493258',
        ).pack(side='left')

    def settings_page():
        content = layout('Réglages')
        if content is None:
            return
        heading(content, 'Violet. Noir. ONYX.', 'Une identité visuelle pensée pour votre setup.')
        theme = card(content)
        theme.pack(fill='x', padx=38, pady=(0, 12))
        label(theme, 'THÈME ONYX', 10, True, MUTED).pack(anchor='w', padx=22, pady=(19, 12))
        theme_row = ctk.CTkFrame(theme, fg_color='transparent')
        theme_row.pack(anchor='w', padx=22, pady=(0, 20))
        ctk.CTkFrame(theme_row, width=20, height=20, corner_radius=10, fg_color=accent()).pack(side='left')
        label(theme_row, 'VIOLET NÉON', 12, True).pack(side='left', padx=(9, 24))
        ctk.CTkFrame(theme_row, width=20, height=20, corner_radius=10, fg_color='#09070D',
                     border_width=1, border_color='#493258').pack(side='left')
        label(theme_row, 'NOIR PROFOND', 12, True).pack(side='left', padx=(9, 0))
        info = card(content)
        info.pack(fill='x', padx=38, pady=(0, 24))
        label(info, 'À PROPOS', 11, True, MUTED).pack(anchor='w', padx=20, pady=(18, 8))
        label(info, 'Onyx Client  ·  Edition V1', 13, True).pack(anchor='w', padx=20, pady=3)
        label(info, 'Licence active — ' + expiry_text(session['expires']), 11, color=GREEN).pack(
            anchor='w', padx=20, pady=(3, 18)
        )

    page_routes.update({
        'Accueil': dashboard,
        'Mes macros': macros_page,
        'Alpha Boost': alpha_boost_page,
        'Manette': controller_page,
        'Commandes': controls_page,
        'Guide': guide_page,
        'Réglages': settings_page,
    })

    try:
        remembered_key = load_remembered_key(REMEMBERED_KEY_FILE)
        remembered_key_error = ''
    except OSError as error:
        remembered_key = None
        remembered_key_error = f'Clé mémorisée indisponible : {error}'
    activation(remembered_key_error)
    app.after(1000, poll_license_checks)
    app.mainloop()
