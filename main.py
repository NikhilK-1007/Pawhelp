"""PawHelp - Kivy prototype.

Run:  python main.py
"""
import json
import os
import threading
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime

try:
    import mysql.connector
    from mysql.connector import Error as MySQLError
except ImportError:
    mysql = None
    MySQLError = Exception

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.filechooser import FileChooserIconView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.utils import get_color_from_hex, platform

# PawHelp palette copied from the Lovable design system.
CREAM = "#F7F1E6"
DARK_GREEN = "#315B49"
GREEN = "#547B61"
PALE_GREEN = "#E3EDE3"
ORANGE = "#E58A43"
WHITE = "#FFFEFA"
TEXT = "#35483D"
MUTED = "#78847B"
WARNING_BG = "#F7EBCB"
WARNING_TEXT = "#72552A"
BORDER = "#D9D2C3"
PREVIEW_BG = "#EDE7DA"

PHONE_DISPLAY = "+91 74119 96630"
PHONE_DIAL = "+917411996630"

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif")

POPULAR_AREAS = [
    ("Rajajinagar", 12.9982, 77.5530),
    ("Indiranagar", 12.9784, 77.6408),
    ("Koramangala", 12.9352, 77.6245),
    ("Whitefield", 12.9698, 77.7500),
    ("Jayanagar", 12.9308, 77.5838),
    ("Malleshwaram", 13.0031, 77.5643),
    ("HSR Layout", 12.9121, 77.6446),
    ("Hebbal", 13.0358, 77.5970),
    ("MG Road", 12.9756, 77.6066),
    ("Electronic City", 12.8452, 77.6602),
]


def rgba(hex_color):
    return get_color_from_hex(hex_color)


def darker(color, factor=0.88):
    r, g, b, a = color
    return (r * factor, g * factor, b * factor, a)


# ---------------------------------------------------------------- database
def load_db_config():
    """Load MySQL connection config from db_config.json or use defaults."""
    default_config = {
        "host": "localhost",
        "port": 3306,
        "user": "root",
        "password": "",
        "database": "pawhelp_db"
    }
    cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "db_config.json")
    if os.path.isfile(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as fh:
                loaded = json.load(fh)
                if isinstance(loaded, dict):
                    default_config.update(loaded)
        except Exception as ex:
            print("Could not read db_config.json:", ex)
    return default_config


def get_db_connection(include_database=True):
    """Return an active connection to MySQL or raise an error."""
    if mysql is None:
        raise RuntimeError("mysql-connector-python is not installed.")
    cfg = load_db_config()
    conn_params = {
        "host": cfg.get("host", "localhost"),
        "port": int(cfg.get("port", 3306)),
        "user": cfg.get("user", "root"),
        "password": cfg.get("password", ""),
        "connect_timeout": 3
    }
    if include_database and cfg.get("database"):
        conn_params["database"] = cfg.get("database")
    return mysql.connector.connect(**conn_params)


def init_db():
    """Ensure pawhelp_db database and reports table exist in MySQL."""
    if mysql is None:
        return False, "mysql-connector-python not installed"
    try:
        cfg = load_db_config()
        db_name = cfg.get("database", "pawhelp_db")
        # 1. Connect without database to create database if not exists
        conn = get_db_connection(include_database=False)
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        cursor.close()
        conn.close()

        # 2. Connect with database to create table if not exists
        conn = get_db_connection(include_database=True)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS `reports` (
                `id` INT AUTO_INCREMENT PRIMARY KEY,
                `animal_type` VARCHAR(50) NOT NULL,
                `problem` VARCHAR(50) NOT NULL,
                `description` TEXT NOT NULL,
                `location` VARCHAR(255) NOT NULL,
                `latitude` DOUBLE NULL,
                `longitude` DOUBLE NULL,
                `maps_url` VARCHAR(500) NULL,
                `photo_path` VARCHAR(500) NULL,
                `created_at` VARCHAR(50) NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        conn.commit()
        cursor.close()
        conn.close()
        return True, "Connected to MySQL successfully"
    except Exception as exc:
        return False, str(exc)


def save_report_to_db(report):
    """Insert a report into MySQL, or raise Exception."""
    init_ok, msg = init_db()
    if not init_ok:
        raise RuntimeError(f"Database error: {msg}")

    conn = get_db_connection(include_database=True)
    cursor = conn.cursor()
    query = """
        INSERT INTO `reports`
        (`animal_type`, `problem`, `description`, `location`, `latitude`, `longitude`, `maps_url`, `photo_path`, `created_at`)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
    """
    values = (
        report.get("animal_type", ""),
        report.get("problem", ""),
        report.get("description", ""),
        report.get("location", ""),
        report.get("latitude"),
        report.get("longitude"),
        report.get("maps_url", ""),
        report.get("photo_path", ""),
        report.get("created_at", datetime.now().isoformat(timespec="seconds"))
    )
    cursor.execute(query, values)
    conn.commit()
    report_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return report_id


def get_reports_from_db():
    """Fetch all reports from MySQL sorted newest first, or return None if offline."""
    init_ok, _ = init_db()
    if not init_ok:
        return None
    try:
        conn = get_db_connection(include_database=True)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM `reports` ORDER BY `id` DESC;")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows
    except Exception as exc:
        print("Error fetching from MySQL:", exc)
        return None


def sync_local_json_to_db():
    """Sync any unmigrated reports from local JSON store to MySQL."""
    try:
        app = App.get_running_app()
        if not app:
            return
        store = os.path.join(app.user_data_dir, "reports.json")
        if not os.path.isfile(store):
            return
        with open(store, "r", encoding="utf-8") as fh:
            local_reports = json.load(fh)
        if not local_reports:
            return

        db_reports = get_reports_from_db()
        if db_reports is None:
            return

        db_keys = {(str(r.get("description", "")).strip(), str(r.get("created_at", "")).strip()[:19]) for r in db_reports}
        for item in local_reports:
            key = (str(item.get("description", "")).strip(), str(item.get("created_at", "")).strip()[:19])
            if key not in db_keys:
                try:
                    save_report_to_db(item)
                except Exception:
                    pass
    except Exception as ex:
        print("Sync notice:", ex)


# ---------------------------------------------------------------- widgets
class RoundedPanel(BoxLayout):
    """BoxLayout with a rounded coloured background.

    auto_height=True makes the panel exactly as tall as its content.
    """

    def __init__(self, bg_color=WHITE, radius=dp(22), auto_height=False, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            self._bg = Color(*rgba(bg_color))
            self._rect = RoundedRectangle(pos=self.pos, size=self.size,
                                          radius=[radius])
        self.bind(pos=self._update_rect, size=self._update_rect)
        if auto_height:
            self.size_hint_y = None
            self.bind(minimum_height=self.setter("height"))

    def _update_rect(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size

    def set_bg(self, hex_color):
        self._bg.rgba = rgba(hex_color)


class PawButton(Button):
    """Rounded, flat button that supports markup and left/centre alignment."""

    def __init__(self, bg=GREEN, fg=WHITE, radius=dp(18), halign="left",
                 font_size=16, pad=dp(32), **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)
        self.color = rgba(fg)
        self.markup = True
        self.font_size = sp(font_size)
        self.halign = halign
        self.valign = "middle"
        self._pad = pad
        self._normal = rgba(bg)
        self._pressed = darker(self._normal)
        with self.canvas.before:
            self._fill = Color(*self._normal)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size,
                                          radius=[radius])
        self.bind(pos=self._update_rect, size=self._update_rect,
                  state=self._update_state)
        self._update_rect()

    def _update_rect(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size
        # text_size is what makes halign/valign actually work on a Label.
        self.text_size = (max(self.width - self._pad, 0),
                          max(self.height - dp(16), 0))

    def _update_state(self, *_):
        self._fill.rgba = self._pressed if self.state == "down" else self._normal

    def set_colors(self, bg, fg):
        self._normal = rgba(bg)
        self._pressed = darker(self._normal)
        self.color = rgba(fg)
        self._update_state()


class ContactCard(ButtonBehavior, RoundedPanel):
    """A tappable rounded card."""

    def on_state(self, *_):
        self.set_bg(PALE_GREEN if self.state == "down" else WHITE)


class PawIcon(Widget):
    """A paw print drawn with shapes (no emoji font needed)."""

    def __init__(self, color=WHITE, **kwargs):
        super().__init__(**kwargs)
        with self.canvas:
            Color(*rgba(color))
            self._pad = Ellipse()
            self._toes = [Ellipse() for _ in range(4)]
        self.bind(pos=self._redraw, size=self._redraw)

    def _redraw(self, *_):
        s = min(self.size)
        cx = self.x + self.width / 2
        cy = self.y + self.height / 2
        self._pad.size = (s * 0.52, s * 0.40)
        self._pad.pos = (cx - s * 0.26, cy - s * 0.34)
        toe_w, toe_h = s * 0.20, s * 0.26
        offsets = [(-0.40, 0.02), (-0.17, 0.22), (0.17, 0.22), (0.40, 0.02)]
        for toe, (dx, dy) in zip(self._toes, offsets):
            toe.size = (toe_w, toe_h)
            toe.pos = (cx + dx * s - toe_w / 2, cy + dy * s - toe_h / 2)


class FieldBox(BoxLayout):
    """Bordered rounded container for text inputs; border turns green on focus."""

    def __init__(self, radius=dp(14), **kwargs):
        super().__init__(**kwargs)
        self.padding = dp(1.5)
        with self.canvas.before:
            self._border = Color(*rgba(BORDER))
            self._outer = RoundedRectangle(radius=[radius])
            Color(*rgba(WHITE))
            self._inner = RoundedRectangle(radius=[max(radius - dp(1.5), 0)])
        self.bind(pos=self._update, size=self._update)

    def _update(self, *_):
        self._outer.pos = self.pos
        self._outer.size = self.size
        self._inner.pos = (self.x + dp(1.5), self.y + dp(1.5))
        self._inner.size = (max(self.width - dp(3), 0), max(self.height - dp(3), 0))

    def set_focus(self, focused):
        self._border.rgba = rgba(GREEN if focused else BORDER)


def make_input(hint, height, multiline=False):
    """Return (FieldBox, TextInput) styled for the report form."""
    box = FieldBox(size_hint_y=None, height=height)
    field = TextInput(
        hint_text=hint, multiline=multiline,
        padding=[dp(14), dp(14), dp(14), dp(12)], font_size=sp(15),
        background_normal="", background_active="",
        background_color=(0, 0, 0, 0), foreground_color=rgba(TEXT),
        hint_text_color=rgba(MUTED), cursor_color=rgba(DARK_GREEN),
        selection_color=rgba(PALE_GREEN)[:3] + [0.6],
    )
    field.bind(focus=lambda inst, value: box.set_focus(value))
    box.add_widget(field)
    return box, field


class ChipGroup(GridLayout):
    """Single-choice group of tappable chips."""

    def __init__(self, values, cols, **kwargs):
        super().__init__(cols=cols, spacing=dp(8), size_hint_y=None,
                         row_force_default=True, row_default_height=dp(44),
                         **kwargs)
        self.bind(minimum_height=self.setter("height"))
        self.selected = None
        self._chips = {}
        for value in values:
            chip = PawButton(text="[b]" + value + "[/b]", bg=PALE_GREEN,
                             fg=DARK_GREEN, radius=dp(14), halign="center",
                             font_size=14, pad=dp(8))
            chip.bind(on_release=lambda _w, v=value: self.select(v))
            self._chips[value] = chip
            self.add_widget(chip)

    def select(self, value):
        self.selected = value
        for name, chip in self._chips.items():
            if name == value:
                chip.set_colors(DARK_GREEN, WHITE)
            else:
                chip.set_colors(PALE_GREEN, DARK_GREEN)

    def reset(self):
        self.selected = None
        for chip in self._chips.values():
            chip.set_colors(PALE_GREEN, DARK_GREEN)


def make_label(text, size=14, color=TEXT, bold=False, halign="left"):
    """Wrapping label whose height follows its text."""
    label = Label(text=text, font_size=sp(size), color=rgba(color), bold=bold,
                  halign=halign, valign="middle", size_hint_y=None, markup=True)
    label.bind(width=lambda inst, w: setattr(inst, "text_size", (w, None)))
    label.bind(texture_size=lambda inst, ts: setattr(inst, "height", ts[1] + dp(4)))
    return label


def column(**kwargs):
    """Vertical BoxLayout that is exactly as tall as its children."""
    box = BoxLayout(orientation="vertical", size_hint_y=None, **kwargs)
    box.bind(minimum_height=box.setter("height"))
    return box


def add_spacer(layout, height=dp(10)):
    layout.add_widget(Widget(size_hint_y=None, height=height))


def scrolling_page(screen, padding, spacing):
    """Give a screen a vertically scrolling page and return the page layout."""
    scroll = ScrollView(do_scroll_x=False, bar_width=dp(3))
    page = BoxLayout(orientation="vertical", padding=padding, spacing=spacing,
                     size_hint_y=None)
    page.bind(minimum_height=page.setter("height"))
    scroll.add_widget(page)
    screen.add_widget(scroll)
    return page


def section_card(number, title, subtitle=None):
    """White card with a numbered header. Returns the card to add widgets to."""
    card = RoundedPanel(bg_color=WHITE, radius=dp(22), orientation="vertical",
                        padding=[dp(16), dp(16), dp(16), dp(18)], spacing=dp(12),
                        auto_height=True)
    header = BoxLayout(orientation="horizontal", size_hint_y=None,
                       height=dp(30), spacing=dp(10))
    badge = RoundedPanel(bg_color=DARK_GREEN, radius=dp(15),
                         size_hint=(None, None), size=(dp(30), dp(30)))
    badge.add_widget(Label(text=str(number), bold=True, font_size=sp(14),
                           color=rgba(WHITE)))
    header.add_widget(badge)
    header.add_widget(Label(text=title, bold=True, font_size=sp(17),
                            color=rgba(DARK_GREEN), halign="left", valign="middle",
                            text_size=(dp(250), None)))
    card.add_widget(header)
    if subtitle:
        card.add_widget(make_label(subtitle, 12, MUTED))
    return card


# ---------------------------------------------------------------- screens
class HomeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        page = scrolling_page(self, [dp(20), dp(24), dp(20), dp(24)], dp(13))

        # Brand header
        header = BoxLayout(orientation="horizontal", size_hint_y=None,
                           height=dp(62), spacing=dp(12))
        logo = RoundedPanel(bg_color=DARK_GREEN, radius=dp(17), padding=dp(11),
                            size_hint=(None, None), size=(dp(52), dp(52)),
                            pos_hint={"center_y": 0.5})
        logo.add_widget(PawIcon(WHITE))
        header.add_widget(logo)

        brand = BoxLayout(orientation="vertical")
        brand.add_widget(make_label("PawHelp", 29, DARK_GREEN, True))
        brand.add_widget(make_label("Every stray deserves a helping hand.", 13,
                                    MUTED, True))
        header.add_widget(brand)
        page.add_widget(header)

        add_spacer(page, dp(8))

        # Welcome card
        welcome = RoundedPanel(bg_color=WHITE, orientation="vertical",
                               padding=[dp(19), dp(16), dp(19), dp(16)],
                               spacing=dp(7), auto_height=True)
        welcome.add_widget(make_label("Welcome, friend!", 21, DARK_GREEN, True))
        welcome.add_widget(make_label(
            "Saw an animal that's hurt, lost or in danger? "
            "You're in the right place. A few taps can get it the help it needs.",
            14, MUTED))
        page.add_widget(welcome)

        add_spacer(page, dp(3))

        # Main report action
        report = PawButton(
            text="[b][size=21sp]Report an Animal[/size][/b]   [size=24sp]›[/size]\n"
                 "[size=13sp]Injured, lost or in danger[/size]",
            bg=ORANGE, radius=dp(26), size_hint_y=None, height=dp(110))
        report.bind(on_release=lambda *_: self.manager.go("report"))
        page.add_widget(report)

        # Two secondary actions
        actions = GridLayout(cols=2, spacing=dp(12), size_hint_y=None,
                             height=dp(120))
        contacts = PawButton(text="[b]Find Rescue\nContacts[/b]",
                             bg=DARK_GREEN, radius=dp(22), halign="center")
        contacts.bind(on_release=lambda *_: self.manager.go("contacts"))
        reports = PawButton(text="[b]My Reports[/b]", bg=DARK_GREEN,
                            radius=dp(22), halign="center")
        reports.bind(on_release=lambda *_: self.manager.go("my_reports"))
        actions.add_widget(contacts)
        actions.add_widget(reports)
        page.add_widget(actions)

        # Safety note
        safety = RoundedPanel(bg_color=WARNING_BG, orientation="horizontal",
                              padding=[dp(14), dp(14), dp(14), dp(14)],
                              spacing=dp(12), auto_height=True)
        badge = RoundedPanel(bg_color=WARNING_TEXT, radius=dp(15),
                             size_hint=(None, None), size=(dp(30), dp(30)),
                             pos_hint={"top": 1})
        badge.add_widget(Label(text="!", bold=True, font_size=sp(18),
                               color=rgba(WHITE)))
        safety.add_widget(badge)
        safety_text = column(spacing=dp(4))
        safety_text.add_widget(make_label("Safety first", 16, WARNING_TEXT, True))
        safety_text.add_widget(make_label(
            "Keep a safe distance. Scared or injured animals may bite or scratch - "
            "don't touch them, and wait for trained rescuers.", 13, WARNING_TEXT))
        safety.add_widget(safety_text)
        page.add_widget(safety)

        add_spacer(page, dp(4))
        page.add_widget(make_label("Small acts of kindness can save lives.", 12,
                                   MUTED, False, "center"))

    def show_placeholder(self, title, message):
        self.manager.get_screen("placeholder").set_message(title, message)
        self.manager.go("placeholder")


class ReportScreen(Screen):
    """Form for entering a new animal-welfare report, with photo upload.

    Submit validates the form and saves the report (including the selected
    photo path) to reports.json in the app's data folder.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.photo_path = ""
        self.location_coords = None
        self._locating = False
        page = scrolling_page(self, [dp(18), dp(20), dp(18), dp(24)], dp(14))

        back = PawButton(text="[b]‹  Home[/b]", bg=PALE_GREEN, fg=DARK_GREEN,
                         size_hint_y=None, height=dp(43), radius=dp(14))
        back.bind(on_release=lambda *_: self.manager.go("home", "right"))
        page.add_widget(back)

        # Title block
        title = column(spacing=dp(2))
        title.add_widget(make_label("Report an Animal", 28, DARK_GREEN, True))
        title.add_widget(make_label(
            "Tell us what happened so rescuers can respond quickly.", 14, MUTED))
        page.add_widget(title)

        # Safety banner
        banner = RoundedPanel(bg_color=WARNING_BG, orientation="horizontal",
                              padding=[dp(14), dp(11), dp(14), dp(11)],
                              spacing=dp(10), auto_height=True)
        dot = RoundedPanel(bg_color=WARNING_TEXT, radius=dp(11),
                           size_hint=(None, None), size=(dp(22), dp(22)),
                           pos_hint={"top": 1})
        dot.add_widget(Label(text="!", bold=True, font_size=sp(13),
                             color=rgba(WHITE)))
        banner.add_widget(dot)
        banner.add_widget(make_label(
            "Keep a safe distance. Never approach an aggressive or badly "
            "injured animal.", 12, WARNING_TEXT))
        page.add_widget(banner)

        # 1. Animal details
        card1 = section_card(1, "Animal details")
        card1.add_widget(make_label("Animal type", 13, MUTED, True))
        self.animal = ChipGroup(["Dog", "Cat", "Bird", "Other"], cols=4)
        card1.add_widget(self.animal)
        card1.add_widget(make_label("What is the problem?", 13, MUTED, True))
        self.problem = ChipGroup(
            ["Injured", "Sick", "Trapped", "Abandoned", "Other"], cols=3)
        card1.add_widget(self.problem)
        page.add_widget(card1)

        # 2. Situation
        card2 = section_card(2, "Describe the situation")
        box, self.description = make_input(
            "Example: A dog has an injured front leg and is limping...",
            dp(120), multiline=True)
        card2.add_widget(box)
        page.add_widget(card2)

        # 3. Photo
        card3 = section_card(
            3, "Add a photo",
            "Optional, but a clear photo helps rescuers assess the animal.")
        self.preview_box = BoxLayout(size_hint_y=None, height=dp(190))
        card3.add_widget(self.preview_box)
        self.photo_name = make_label("", 12, MUTED, False, "center")
        card3.add_widget(self.photo_name)

        photo_row = BoxLayout(orientation="horizontal", size_hint_y=None,
                              height=dp(48), spacing=dp(10))
        self.upload_btn = PawButton(text="[b]Upload Photo[/b]", bg=GREEN,
                                    halign="center", radius=dp(16),
                                    size_hint_x=0.62)
        self.upload_btn.bind(on_release=lambda *_: self.open_photo_picker())
        self.remove_btn = PawButton(text="[b]Remove[/b]", bg=PALE_GREEN,
                                    fg=DARK_GREEN, halign="center",
                                    radius=dp(16), size_hint_x=0.38)
        self.remove_btn.bind(on_release=lambda *_: self.clear_photo())
        photo_row.add_widget(self.upload_btn)
        photo_row.add_widget(self.remove_btn)
        card3.add_widget(photo_row)
        page.add_widget(card3)
        self._show_placeholder()

        # 4. Location
        card4 = section_card(
            4, "Location",
            "Tell rescuers where the animal was seen.")
        card4.add_widget(make_label("Address or nearby landmark", 13, MUTED, True))
        box, self.location = make_input(
            "Enter address, landmark or tap below", dp(52))
        self.location.bind(text=self._on_location_text_change)
        card4.add_widget(box)

        # Location buttons row: [📍 Use Current Location] [Pick Area]
        loc_row = BoxLayout(orientation="horizontal", size_hint_y=None,
                            height=dp(46), spacing=dp(10))
        self.loc_btn = PawButton(
            text="[b]Use Current Location[/b]", bg=GREEN,
            halign="center", radius=dp(16), size_hint_x=0.62,
            font_size=14, pad=dp(6))
        self.loc_btn.bind(on_release=lambda *_: self.detect_current_location())

        self.pick_loc_btn = PawButton(
            text="[b]Pick Area[/b]", bg=PALE_GREEN, fg=DARK_GREEN,
            halign="center", radius=dp(16), size_hint_x=0.38,
            font_size=14, pad=dp(6))
        self.pick_loc_btn.bind(on_release=lambda *_: self.open_location_picker())
        loc_row.add_widget(self.loc_btn)
        loc_row.add_widget(self.pick_loc_btn)
        card4.add_widget(loc_row)

        # Location status and map preview / clear action row
        self.loc_status_box = RoundedPanel(
            bg_color=PREVIEW_BG, radius=dp(14), orientation="vertical",
            padding=[dp(12), dp(10), dp(12), dp(10)], spacing=dp(8),
            auto_height=True)
        self.loc_status_label = make_label(
            "Tip: Tap [b]Use Current Location[/b] to auto-detect via GPS/IP, or [b]Pick Area[/b] to choose landmarks.",
            12, MUTED)
        self.loc_status_box.add_widget(self.loc_status_label)

        self.loc_action_row = BoxLayout(
            orientation="horizontal", size_hint_y=None, height=dp(36),
            spacing=dp(8))
        self.map_btn = PawButton(
            text="[b]View on Map[/b]", bg=DARK_GREEN, fg=WHITE,
            halign="center", radius=dp(12), size_hint_x=0.6,
            font_size=12, pad=dp(4))
        self.map_btn.bind(on_release=lambda *_: self.open_map())
        self.clear_loc_btn = PawButton(
            text="[b]Clear[/b]", bg=PALE_GREEN, fg=DARK_GREEN,
            halign="center", radius=dp(12), size_hint_x=0.4,
            font_size=12, pad=dp(4))
        self.clear_loc_btn.bind(on_release=lambda *_: self.clear_location())
        self.loc_action_row.add_widget(self.map_btn)
        self.loc_action_row.add_widget(self.clear_loc_btn)
        self.loc_action_row.opacity = 0
        self.loc_action_row.disabled = True
        self.loc_status_box.add_widget(self.loc_action_row)

        card4.add_widget(self.loc_status_box)
        page.add_widget(card4)

        submit = PawButton(text="[b]Submit Report[/b]", bg=ORANGE,
                           halign="center", size_hint_y=None,
                           height=dp(58), radius=dp(20))
        submit.bind(on_release=self.submit_report)
        page.add_widget(submit)

        page.add_widget(make_label(
            "For urgent situations, contact a trained rescue organisation "
            "directly.", 12, MUTED, False, "center"))

    # ------------------------------------------------------------ photo
    def _show_placeholder(self):
        self.preview_box.clear_widgets()
        panel = RoundedPanel(bg_color=PREVIEW_BG, radius=dp(18),
                             orientation="vertical",
                             padding=[dp(16), dp(10), dp(16), dp(10)],
                             spacing=dp(6))
        panel.add_widget(Widget())
        icon_bg = RoundedPanel(bg_color=PALE_GREEN, radius=dp(26),
                               padding=dp(12), size_hint=(None, None),
                               size=(dp(52), dp(52)),
                               pos_hint={"center_x": 0.5})
        icon_bg.add_widget(PawIcon(GREEN))
        panel.add_widget(icon_bg)
        panel.add_widget(make_label("No photo selected", 14, DARK_GREEN, True,
                                    "center"))
        panel.add_widget(make_label("Tap Upload Photo to choose an image.", 12,
                                    MUTED, False, "center"))
        panel.add_widget(Widget())
        self.preview_box.add_widget(panel)
        self.photo_name.text = ""
        self.upload_btn.text = "[b]Upload Photo[/b]"
        self.remove_btn.disabled = True
        self.remove_btn.opacity = 0.45

    def _show_preview(self, path):
        self.preview_box.clear_widgets()
        panel = RoundedPanel(bg_color=PREVIEW_BG, radius=dp(18), padding=dp(6))
        panel.add_widget(Image(source=path, nocache=True))
        self.preview_box.add_widget(panel)
        self.photo_name.text = os.path.basename(path)
        self.upload_btn.text = "[b]Change Photo[/b]"
        self.remove_btn.disabled = False
        self.remove_btn.opacity = 1

    def open_photo_picker(self):
        """Open the image selection window."""
        if platform == "android":
            try:
                from plyer import filechooser
                filechooser.open_file(
                    on_selection=self._on_native_selection,
                    filters=[["Images", "*.png", "*.jpg", "*.jpeg"]])
                return
            except Exception as exc:  # fall back to the built-in picker
                print("Native picker unavailable:", exc)
        self._open_kivy_picker()

    def _on_native_selection(self, selection):
        if selection:
            path = selection[0]
            Clock.schedule_once(lambda _dt: self.set_photo(path))

    def _open_kivy_picker(self):
        start = os.path.expanduser("~")
        for folder in ("Pictures", "Downloads"):
            candidate = os.path.join(start, folder)
            if os.path.isdir(candidate):
                start = candidate
                break
        if platform == "android" and os.path.isdir("/storage/emulated/0"):
            start = "/storage/emulated/0"

        filters = ["*" + ext for ext in IMAGE_EXTENSIONS]
        filters += ["*" + ext.upper() for ext in IMAGE_EXTENSIONS]
        chooser = FileChooserIconView(path=start, filters=filters)

        content = BoxLayout(orientation="vertical", spacing=dp(10),
                            padding=dp(10))
        content.add_widget(chooser)
        buttons = BoxLayout(orientation="horizontal", size_hint_y=None,
                            height=dp(48), spacing=dp(10))
        cancel = PawButton(text="[b]Cancel[/b]", bg=PALE_GREEN, fg=DARK_GREEN,
                           halign="center", radius=dp(14))
        select = PawButton(text="[b]Select[/b]", bg=ORANGE, halign="center",
                           radius=dp(14))
        buttons.add_widget(cancel)
        buttons.add_widget(select)
        content.add_widget(buttons)

        popup = Popup(title="Select a photo", content=content,
                      size_hint=(0.95, 0.85))

        def choose(*_):
            if not chooser.selection:
                App.get_running_app().show_message(
                    "No photo selected", "Tap an image first, then press Select.")
                return
            popup.dismiss()
            self.set_photo(chooser.selection[0])

        select.bind(on_release=choose)
        cancel.bind(on_release=popup.dismiss)
        chooser.bind(on_submit=lambda _c, sel, _touch: choose() if sel else None)
        popup.open()

    def set_photo(self, path):
        if not path or not os.path.isfile(path) \
                or not path.lower().endswith(IMAGE_EXTENSIONS):
            App.get_running_app().show_message(
                "Unsupported file",
                "Please choose a PNG, JPG, JPEG, WEBP, BMP or GIF image.")
            return
        self.photo_path = path
        self._show_preview(path)

    def clear_photo(self):
        self.photo_path = ""
        self._show_placeholder()

    # ------------------------------------------------------------ location
    def _on_location_text_change(self, instance, text):
        has_text = bool(text.strip())
        if has_text:
            self.loc_action_row.opacity = 1
            self.loc_action_row.disabled = False
        elif not self.location_coords:
            self.loc_action_row.opacity = 0
            self.loc_action_row.disabled = True

    def detect_current_location(self):
        """Fetch current GPS / IP geolocation asynchronously."""
        if self._locating:
            return
        self._locating = True
        self.loc_btn.text = "[b]Locating...[/b]"
        self.loc_btn.disabled = True
        self.loc_btn.opacity = 0.65
        self.loc_status_label.text = "Detecting current location..."

        def worker():
            coords, display_name, err = self._fetch_current_location_data()
            Clock.schedule_once(
                lambda _dt: self._on_location_detected(coords, display_name, err))

        threading.Thread(target=worker, daemon=True).start()

    def _fetch_current_location_data(self):
        """Worker thread to fetch coordinates and reverse geocode."""
        lat, lon, city, region = None, None, "", ""
        # 1. Try ipapi.co
        try:
            req = urllib.request.Request(
                "https://ipapi.co/json/",
                headers={"User-Agent": "PawHelpApp/1.0"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode())
                lat = data.get("latitude")
                lon = data.get("longitude")
                city = data.get("city", "")
                region = data.get("region", "")
        except Exception:
            pass

        # Fallback to ip-api.com if needed
        if not lat or not lon:
            try:
                req = urllib.request.Request(
                    "http://ip-api.com/json/",
                    headers={"User-Agent": "PawHelpApp/1.0"})
                with urllib.request.urlopen(req, timeout=4) as resp:
                    data = json.loads(resp.read().decode())
                    if data.get("status") == "success":
                        lat = data.get("lat")
                        lon = data.get("lon")
                        city = data.get("city", "")
                        region = data.get("regionName", "")
            except Exception:
                pass

        if not lat or not lon:
            return None, None, "Could not determine location. Please verify your connection or set location manually."

        # 2. Reverse geocode via Nominatim for neighborhood/street
        display_name = f"{city}, {region}".strip(", ")
        try:
            rev_url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json"
            rev_req = urllib.request.Request(
                rev_url, headers={"User-Agent": "PawHelpAnimalRescue/1.0"})
            with urllib.request.urlopen(rev_req, timeout=4) as rev_resp:
                rev_data = json.loads(rev_resp.read().decode())
                addr = rev_data.get("address", {})
                parts = [
                    addr.get("road") or addr.get("suburb") or addr.get("neighbourhood"),
                    addr.get("city") or addr.get("town") or city,
                    addr.get("state") or region
                ]
                filtered = [p for p in parts if p]
                if filtered:
                    display_name = ", ".join(filtered)
                elif rev_data.get("display_name"):
                    display_name = ", ".join(rev_data.get("display_name").split(",")[:3]).strip()
        except Exception:
            pass

        return (float(lat), float(lon)), display_name, None

    def _on_location_detected(self, coords, display_name, err):
        self._locating = False
        self.loc_btn.disabled = False
        self.loc_btn.opacity = 1.0

        if err or not coords:
            self.loc_btn.text = "[b]Use Current Location[/b]"
            self.loc_status_label.text = "Could not auto-detect location. Please enter manually or pick an area."
            App.get_running_app().show_message(
                "Location unavailable",
                err or "Could not detect location. Please type your location or pick an area.")
            return

        self.set_selected_location(display_name, coords)

    def set_selected_location(self, name, coords=None):
        self.location.text = name
        self.location_coords = coords
        safe_name = name.replace("[", "(").replace("]", ")")
        if coords:
            lat, lon = coords
            self.loc_status_label.text = (
                f"[b]Coordinates:[/b] {lat:.4f}° N, {lon:.4f}° E\n"
                f"[color={MUTED}][size=12sp]{safe_name}[/size][/color]")
            self.loc_btn.text = "[b]✓ Location Set[/b]"
        else:
            self.loc_status_label.text = f"[b]Location:[/b] {safe_name}"
            self.loc_btn.text = "[b]Use Current Location[/b]"
        self.loc_action_row.opacity = 1
        self.loc_action_row.disabled = False

    def clear_location(self):
        self.location.text = ""
        self.location_coords = None
        self._locating = False
        self.loc_btn.text = "[b]Use Current Location[/b]"
        self.loc_btn.disabled = False
        self.loc_btn.opacity = 1.0
        self.loc_status_label.text = (
            "Tip: Tap [b]Use Current Location[/b] to auto-detect via GPS/IP, or [b]Pick Area[/b] to choose landmarks.")
        self.loc_action_row.opacity = 0
        self.loc_action_row.disabled = True

    def open_map(self):
        """Open current location in browser map."""
        if self.location_coords:
            lat, lon = self.location_coords
            url = f"https://www.google.com/maps?q={lat},{lon}"
        elif self.location.text.strip():
            query = urllib.parse.quote(self.location.text.strip())
            url = f"https://www.google.com/maps/search/?api=1&query={query}"
        else:
            App.get_running_app().show_message(
                "No location", "Please set or enter a location first.")
            return
        webbrowser.open(url)

    def open_location_picker(self):
        """Open the location picker modal popup."""
        content = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(12))

        content.add_widget(make_label(
            "Search a landmark/street or pick a quick area:", 13, MUTED))

        # Search bar
        search_box, search_input = make_input("e.g. Orion Mall, MG Road...", dp(44))
        search_btn = PawButton(
            text="[b]Search[/b]", bg=DARK_GREEN, halign="center",
            radius=dp(12), size_hint_x=None, width=dp(80),
            font_size=13, pad=dp(4))
        search_row = BoxLayout(orientation="horizontal", size_hint_y=None,
                               height=dp(44), spacing=dp(8))
        search_row.add_widget(search_box)
        search_row.add_widget(search_btn)
        content.add_widget(search_row)

        # Scrolling container for preset chips / search results
        scroll = ScrollView(do_scroll_x=False, bar_width=dp(3))
        results_container = BoxLayout(
            orientation="vertical", spacing=dp(8), size_hint_y=None)
        results_container.bind(minimum_height=results_container.setter("height"))
        scroll.add_widget(results_container)
        content.add_widget(scroll)

        # Selected preview label
        selected_box = RoundedPanel(
            bg_color=PREVIEW_BG, radius=dp(12), orientation="vertical",
            padding=[dp(10), dp(8), dp(10), dp(8)], auto_height=True)
        initial_label = self.location.text.strip().replace("[", "(").replace("]", ")")
        selected_label = make_label(
            "[b]Selected:[/b] " + (initial_label or "None"), 12, TEXT)
        selected_box.add_widget(selected_label)
        content.add_widget(selected_box)

        # Action buttons
        btn_row = BoxLayout(orientation="horizontal", size_hint_y=None,
                            height=dp(46), spacing=dp(10))
        cancel_btn = PawButton(
            text="[b]Cancel[/b]", bg=PALE_GREEN, fg=DARK_GREEN,
            halign="center", radius=dp(14), size_hint_x=0.38)
        apply_btn = PawButton(
            text="[b]Set Location[/b]", bg=ORANGE, halign="center",
            radius=dp(14), size_hint_x=0.62)
        btn_row.add_widget(cancel_btn)
        btn_row.add_widget(apply_btn)
        content.add_widget(btn_row)

        popup = Popup(
            title="Pick or Search Location", content=content,
            size_hint=(0.95, 0.88))

        state = {
            "name": self.location.text.strip(),
            "coords": self.location_coords
        }

        def choose_item(name, coords):
            state["name"] = name
            state["coords"] = coords
            safe_name = name.replace("[", "(").replace("]", ")")
            if coords:
                selected_label.text = f"[b]Selected:[/b] {safe_name} ({coords[0]:.4f}, {coords[1]:.4f})"
            else:
                selected_label.text = f"[b]Selected:[/b] {safe_name}"

        def populate_presets():
            results_container.clear_widgets()
            # Fast GPS option inside popup too
            current_loc_btn = PawButton(
                text="[b]📍 Use Current Location[/b]", bg=GREEN,
                halign="center", radius=dp(12), size_hint_y=None, height=dp(40),
                font_size=13, pad=dp(4))

            def on_use_current(*_):
                popup.dismiss()
                self.detect_current_location()

            current_loc_btn.bind(on_release=on_use_current)
            results_container.add_widget(current_loc_btn)

            results_container.add_widget(
                make_label("Popular areas & landmarks:", 13, DARK_GREEN, True))

            grid = GridLayout(cols=2, spacing=dp(8), size_hint_y=None,
                              row_force_default=True, row_default_height=dp(40))
            grid.bind(minimum_height=grid.setter("height"))
            for area_name, lat, lon in POPULAR_AREAS:
                chip = PawButton(
                    text="[b]" + area_name + "[/b]", bg=PALE_GREEN,
                    fg=DARK_GREEN, radius=dp(12), halign="center",
                    font_size=13, pad=dp(4))
                chip.bind(
                    on_release=lambda _w, a=area_name, c=(lat, lon): choose_item(a, c))
                grid.add_widget(chip)
            results_container.add_widget(grid)

        def perform_search(*_):
            query = search_input.text.strip()
            if not query:
                populate_presets()
                return
            results_container.clear_widgets()
            safe_q = query.replace("[", "(").replace("]", ")")
            results_container.add_widget(
                make_label(f"Searching for '{safe_q}'...", 13, MUTED))

            def search_worker():
                try:
                    q = urllib.parse.quote(query)
                    url = f"https://nominatim.openstreetmap.org/search?q={q}&format=json&limit=5"
                    req = urllib.request.Request(
                        url, headers={"User-Agent": "PawHelpAnimalRescue/1.0"})
                    with urllib.request.urlopen(req, timeout=5) as resp:
                        data = json.loads(resp.read().decode())
                except Exception:
                    data = None

                Clock.schedule_once(lambda _dt: render_search_results(query, data))

            threading.Thread(target=search_worker, daemon=True).start()

        def render_search_results(query, results):
            results_container.clear_widgets()
            safe_q = query.replace("[", "(").replace("]", ")")
            back_btn = PawButton(
                text="[b]‹ Back to Popular Areas[/b]", bg=PALE_GREEN,
                fg=DARK_GREEN, radius=dp(12), size_hint_y=None, height=dp(36),
                font_size=12, pad=dp(4), halign="center")
            back_btn.bind(on_release=lambda *_: populate_presets())
            results_container.add_widget(back_btn)

            if not results:
                results_container.add_widget(
                    make_label(f"No results found for '{safe_q}'.\nYou can still use '{safe_q}' by tapping Set Location.", 12, MUTED))
                choose_item(query, None)
                return

            results_container.add_widget(
                make_label(f"Results for '{safe_q}':", 13, DARK_GREEN, True))

            for item in results:
                raw_name = item.get("display_name", "")
                parts = [p.strip() for p in raw_name.split(",") if p.strip()]
                short_name = ", ".join(parts[:3]) if parts else raw_name
                safe_short = short_name.replace("[", "(").replace("]", ")")
                try:
                    c = (float(item.get("lat")), float(item.get("lon")))
                except (ValueError, TypeError):
                    c = None
                res_btn = PawButton(
                    text="[b]" + safe_short + "[/b]", bg=WHITE,
                    fg=DARK_GREEN, radius=dp(12), size_hint_y=None,
                    height=dp(48), font_size=13, pad=dp(6), halign="left")
                res_btn.bind(
                    on_release=lambda _w, s=short_name, coord=c: choose_item(s, coord))
                results_container.add_widget(res_btn)

        def apply_selection(*_):
            name = state["name"] or search_input.text.strip()
            if not name:
                App.get_running_app().show_message(
                    "No location selected",
                    "Please choose an area or type a location first.")
                return
            popup.dismiss()
            self.set_selected_location(name, state["coords"])

        populate_presets()
        search_btn.bind(on_release=perform_search)
        search_input.bind(on_text_validate=perform_search)
        apply_btn.bind(on_release=apply_selection)
        cancel_btn.bind(on_release=popup.dismiss)
        popup.open()

    # ------------------------------------------------------------ submit
    def submit_report(self, *_):
        app = App.get_running_app()
        animal = self.animal.selected
        problem = self.problem.selected
        description = self.description.text.strip()
        location = self.location.text.strip()

        if not animal:
            app.show_message("Missing information", "Please choose the animal type.")
            return
        if not problem:
            app.show_message("Missing information", "Please choose the problem.")
            return
        if not description:
            app.show_message("Missing information",
                             "Please describe the situation.")
            return
        if not location:
            app.show_message("Missing information",
                             "Please enter a location or landmark.")
            return

        report = {
            "animal_type": animal,
            "problem": problem,
            "description": description,
            "location": location,
            "latitude": self.location_coords[0] if self.location_coords else None,
            "longitude": self.location_coords[1] if self.location_coords else None,
            "maps_url": (
                f"https://www.google.com/maps?q={self.location_coords[0]},{self.location_coords[1]}"
                if self.location_coords
                else f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(location)}"
            ),
            "photo_path": self.photo_path,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        try:
            report_id, store = app.save_report(report)
        except OSError as exc:
            app.show_message("Could not save", f"The report was not saved: {exc}")
            return

        self.reset_form()
        app.show_message(
            "Report saved",
            f"Report #{report_id} was saved"
            + (" with its photo." if report["photo_path"] else ".")
            + f"\n\nStored in:\n{store}")
        self.manager.go("home", "right")

    def reset_form(self):
        self.animal.reset()
        self.problem.reset()
        self.description.text = ""
        self.clear_location()
        self.clear_photo()


class ContactsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        page = scrolling_page(self, [dp(20), dp(24), dp(20), dp(20)], dp(12))

        back = PawButton(text="[b]‹  Home[/b]", bg=PALE_GREEN, fg=DARK_GREEN,
                         size_hint_y=None, height=dp(43), radius=dp(14))
        back.bind(on_release=lambda *_: self.manager.go("home", "right"))
        page.add_widget(back)

        page.add_widget(make_label("Rescue Contacts", 28, DARK_GREEN, True))
        page.add_widget(make_label("Tap a contact to see details and call.", 14,
                                   MUTED))

        # Contact card
        card = ContactCard(bg_color=WHITE, radius=dp(22), orientation="horizontal",
                           padding=dp(16), spacing=dp(14), auto_height=True)
        icon_bg = RoundedPanel(bg_color=PALE_GREEN, radius=dp(22), padding=dp(10),
                               size_hint=(None, None), size=(dp(44), dp(44)),
                               pos_hint={"top": 1})
        icon_bg.add_widget(PawIcon(GREEN))
        card.add_widget(icon_bg)

        info = column(spacing=dp(3))
        info.add_widget(make_label("Little Hearts Animal Healing Rescue Centre",
                                   16, DARK_GREEN, True))
        info.add_widget(make_label("Wildlife rescue · Bangalore", 12, MUTED))
        info.add_widget(make_label("Open until 11 pm (as listed in project)", 11,
                                   ORANGE))
        card.add_widget(info)
        card.bind(on_release=lambda *_: self.manager.go("contact_detail"))
        page.add_widget(card)

        page.add_widget(make_label(
            "Contact information is reproduced from your uploaded project. "
            "Please confirm the number and availability before relying on it.",
            12, MUTED))


class ContactDetailScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        page = scrolling_page(self, [dp(20), dp(24), dp(20), dp(20)], dp(13))

        back = PawButton(text="[b]‹  All contacts[/b]", bg=PALE_GREEN,
                         fg=DARK_GREEN, size_hint_y=None, height=dp(43),
                         radius=dp(14))
        back.bind(on_release=lambda *_: self.manager.go("contacts", "right"))
        page.add_widget(back)

        page.add_widget(make_label("WILDLIFE RESCUE", 12, GREEN, True))
        page.add_widget(make_label("Little Hearts Animal Healing Rescue Centre",
                                   25, DARK_GREEN, True))
        page.add_widget(make_label(
            "Wildlife rescue service providing care and rehabilitation for injured "
            "or orphaned animals.", 14, MUTED))

        call = PawButton(text="[b]Call " + PHONE_DISPLAY + "[/b]", bg=ORANGE,
                         halign="center", size_hint_y=None, height=dp(60),
                         radius=dp(22))
        call.bind(on_release=lambda *_: App.get_running_app().call_number())
        page.add_widget(call)

        info = RoundedPanel(bg_color=WHITE, orientation="vertical",
                            padding=dp(17), spacing=dp(8), auto_height=True)
        info.add_widget(make_label("[b]Location[/b]   Bangalore", 15, TEXT))
        info.add_widget(make_label(
            "[b]Hours[/b]   Open until 11 pm (as listed in project)", 14, TEXT))
        page.add_widget(info)

        page.add_widget(make_label("Can help with", 18, DARK_GREEN, True))
        chips = GridLayout(cols=2, spacing=dp(8), size_hint_y=None,
                           row_force_default=True, row_default_height=dp(38))
        chips.bind(minimum_height=chips.setter("height"))
        for tag in ["Wildlife rescue", "Injured animals",
                    "Orphaned animals", "Rehabilitation"]:
            chip = RoundedPanel(bg_color=PALE_GREEN, radius=dp(14))
            chip.add_widget(Label(text=tag, font_size=sp(13), bold=True,
                                  color=rgba(GREEN)))
            chips.add_widget(chip)
        page.add_widget(chips)

        page.add_widget(make_label(
            "Please verify contact details and current service availability "
            "independently.", 12, MUTED))


class MyReportsScreen(Screen):
    """Screen that loads and displays reports from MySQL database."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.page = scrolling_page(self, [dp(18), dp(20), dp(18), dp(24)], dp(14))

        # Top Home button (Only 1 Home button, as requested)
        top_home = PawButton(text="[b]‹  Home[/b]", bg=PALE_GREEN, fg=DARK_GREEN,
                             size_hint_y=None, height=dp(43), radius=dp(14))
        top_home.bind(on_release=lambda *_: self.manager.go("home", "right"))
        self.page.add_widget(top_home)

        # Header block with Refresh button
        header_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(48), spacing=dp(10))
        title_box = column(spacing=dp(2))
        title_box.add_widget(make_label("My Rescue Reports", 26, DARK_GREEN, True))
        title_box.add_widget(make_label("Saved safely in your local MySQL database", 12, MUTED))
        header_row.add_widget(title_box)

        refresh_btn = PawButton(text="[b]↻ Refresh[/b]", bg=PALE_GREEN, fg=DARK_GREEN,
                                halign="center", radius=dp(12), size_hint=(None, None),
                                size=(dp(92), dp(38)), font_size=13, pad=dp(4),
                                pos_hint={"center_y": 0.5})
        refresh_btn.bind(on_release=lambda *_: self.load_reports())
        header_row.add_widget(refresh_btn)
        self.page.add_widget(header_row)

        # Database connection & status indicator
        self.status_box = RoundedPanel(
            bg_color=PREVIEW_BG, radius=dp(12), orientation="vertical",
            padding=[dp(12), dp(8), dp(12), dp(8)], auto_height=True)
        self.status_label = make_label("Checking MySQL connection...", 12, MUTED)
        self.status_box.add_widget(self.status_label)
        self.page.add_widget(self.status_box)

        # Reports container
        self.reports_container = column(spacing=dp(14))
        self.page.add_widget(self.reports_container)

    def on_pre_enter(self, *args):
        super().on_pre_enter(*args)
        self.load_reports()

    def load_reports(self):
        """Fetch reports from MySQL (with local cache fallback) and populate UI."""
        self.reports_container.clear_widgets()
        self.status_label.text = "Loading reports..."

        def worker():
            # Sync local reports if any exist
            sync_local_json_to_db()

            reports = get_reports_from_db()
            db_source = "mysql"
            db_err = None

            if reports is None:
                db_source = "local"
                # Fallback to local JSON
                app = App.get_running_app()
                store = os.path.join(app.user_data_dir, "reports.json") if app else ""
                if os.path.isfile(store):
                    try:
                        with open(store, "r", encoding="utf-8") as fh:
                            reports = json.load(fh)
                            reports = sorted(reports, key=lambda r: r.get("id", 0), reverse=True)
                    except Exception as e:
                        reports = []
                        db_err = str(e)
                else:
                    reports = []

            Clock.schedule_once(lambda _dt: self._render_reports(reports, db_source, db_err))

        threading.Thread(target=worker, daemon=True).start()

    def _render_reports(self, reports, source, err):
        self.reports_container.clear_widgets()

        if source == "mysql":
            count = len(reports) if reports else 0
            self.status_label.text = (
                f"[b][color={DARK_GREEN}]✓ Connected to MySQL Workbench 8.0[/color][/b] "
                f"· Table: [b]pawhelp_db.reports[/b] ({count} record{'s' if count != 1 else ''})"
            )
        else:
            cfg = load_db_config()
            self.status_label.text = (
                f"[b][color={WARNING_TEXT}]! MySQL Offline ({cfg.get('host')}:{cfg.get('port')})[/color][/b]\n"
                f"[size=11sp]Showing local backup. Please start MySQL Server / Workbench and tap Refresh.[/size]"
            )

        if not reports:
            empty = RoundedPanel(
                bg_color=WHITE, radius=dp(20), orientation="vertical",
                padding=[dp(20), dp(26), dp(20), dp(26)], spacing=dp(10), auto_height=True)
            empty.add_widget(make_label("No rescue reports found yet", 17, DARK_GREEN, True, "center"))
            empty.add_widget(make_label(
                "When you report an animal in need, it will be automatically saved into your MySQL database and listed here.",
                13, MUTED, halign="center"))
            self.reports_container.add_widget(empty)
            return

        for item in reports:
            card = self._build_card(item)
            self.reports_container.add_widget(card)

    def _build_card(self, report):
        card = RoundedPanel(
            bg_color=WHITE, radius=dp(20), orientation="vertical",
            padding=[dp(16), dp(14), dp(16), dp(16)], spacing=dp(10), auto_height=True)

        # Header: #ID and Timestamp
        top_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(28), spacing=dp(8))
        badge = RoundedPanel(
            bg_color=DARK_GREEN, radius=dp(12),
            size_hint=(None, None), size=(dp(46), dp(26)))
        badge.add_widget(Label(text=f"#{report.get('id', '?')}", bold=True, font_size=sp(12), color=rgba(WHITE)))
        top_row.add_widget(badge)

        created = str(report.get("created_at", "")).replace("T", " ")[:19]
        top_row.add_widget(make_label(created, 12, MUTED))
        card.add_widget(top_row)

        # Badges row: Animal + Problem
        tags_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(30), spacing=dp(8))
        raw_animal = str(report.get("animal_type", "Animal"))
        a_chip = RoundedPanel(bg_color=PALE_GREEN, radius=dp(10), size_hint=(None, None), size=(dp(84), dp(28)))
        a_chip.add_widget(Label(text=raw_animal, font_size=sp(12), bold=True, color=rgba(DARK_GREEN)))
        tags_row.add_widget(a_chip)

        raw_prob = str(report.get("problem", "Notice"))
        p_chip = RoundedPanel(bg_color=WARNING_BG, radius=dp(10), size_hint=(None, None), size=(dp(96), dp(28)))
        p_chip.add_widget(Label(text=raw_prob, font_size=sp(12), bold=True, color=rgba(WARNING_TEXT)))
        tags_row.add_widget(p_chip)
        tags_row.add_widget(Widget())
        card.add_widget(tags_row)

        # Description
        desc = report.get("description", "").strip()
        if desc:
            safe_desc = desc.replace("[", "(").replace("]", ")")
            card.add_widget(make_label(safe_desc, 14, TEXT))

        # Photo if attached and file exists
        photo_path = report.get("photo_path")
        if photo_path and os.path.isfile(photo_path):
            img_panel = RoundedPanel(
                bg_color=PREVIEW_BG, radius=dp(14), padding=dp(6),
                size_hint_y=None, height=dp(150))
            img_panel.add_widget(Image(source=photo_path, nocache=True))
            card.add_widget(img_panel)

        # Location details box
        loc_box = RoundedPanel(
            bg_color=PREVIEW_BG, radius=dp(12), orientation="vertical",
            padding=[dp(12), dp(8), dp(12), dp(8)], spacing=dp(6), auto_height=True)
        loc_str = str(report.get("location", "")).strip()
        safe_loc = loc_str.replace("[", "(").replace("]", ")")
        loc_box.add_widget(make_label(f"[b]Location:[/b] {safe_loc}", 13, DARK_GREEN))

        lat = report.get("latitude")
        lon = report.get("longitude")
        if lat is not None and lon is not None:
            try:
                loc_box.add_widget(make_label(f"GPS: {float(lat):.4f}° N, {float(lon):.4f}° E", 11, MUTED))
            except (ValueError, TypeError):
                pass

        maps_url = report.get("maps_url")
        target_url = maps_url or (f"https://www.google.com/maps?q={lat},{lon}" if lat and lon else f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(loc_str)}")
        if target_url:
            map_btn = PawButton(
                text="[b]View on Google Maps[/b]", bg=GREEN, fg=WHITE,
                halign="center", radius=dp(10), size_hint_y=None, height=dp(34),
                font_size=12, pad=dp(4))
            map_btn.bind(on_release=lambda *_, u=target_url: webbrowser.open(u))
            loc_box.add_widget(map_btn)

        card.add_widget(loc_box)
        return card


class PlaceholderScreen(Screen):
    """Placeholder screen with only a top Home button."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        page = BoxLayout(orientation="vertical",
                         padding=[dp(24), dp(30), dp(24), dp(24)], spacing=dp(14))
        top_home = PawButton(text="[b]‹  Home[/b]", bg=PALE_GREEN, fg=DARK_GREEN,
                             size_hint_y=None, height=dp(43), radius=dp(14))
        top_home.bind(on_release=lambda *_: self.manager.go("home", "right"))
        page.add_widget(top_home)
        self.title_label = make_label("Coming soon", 26, DARK_GREEN, True)
        self.message_label = make_label("", 15, MUTED)
        page.add_widget(self.title_label)
        page.add_widget(self.message_label)
        page.add_widget(Widget())
        self.add_widget(page)

    def set_message(self, title, message):
        self.title_label.text = title
        self.message_label.text = message


class PawManager(ScreenManager):
    # Which screen the Back button / Esc key returns to.
    PARENTS = {"contacts": "home", "contact_detail": "contacts",
               "placeholder": "home", "report": "home", "my_reports": "home"}

    def go(self, name, direction="left"):
        self.transition.direction = direction
        self.current = name

    def go_back(self):
        parent = self.PARENTS.get(self.current)
        if parent:
            self.go(parent, "right")
            return True
        return False


# ---------------------------------------------------------------- app
class PawHelpApp(App):
    title = "PawHelp"

    def build(self):
        Window.clearcolor = rgba(CREAM)
        # Phone-shaped window when previewing on a computer.
        if platform in ("win", "linux", "macosx"):
            Window.size = (390, 780)
        Window.bind(on_keyboard=self._on_keyboard)

        manager = PawManager(transition=SlideTransition(duration=0.18))
        manager.add_widget(HomeScreen(name="home"))
        manager.add_widget(ReportScreen(name="report"))
        manager.add_widget(ContactsScreen(name="contacts"))
        manager.add_widget(ContactDetailScreen(name="contact_detail"))
        manager.add_widget(MyReportsScreen(name="my_reports"))
        manager.add_widget(PlaceholderScreen(name="placeholder"))
        return manager

    def _on_keyboard(self, window, key, *args):
        # 27 = Esc / Android Back button. Returning True stops the app closing.
        if key == 27:
            return self.root.go_back()
        return False

    def save_report(self, report):
        """Save report to MySQL (and keep local backup).

        Returns (report_id, path_or_destination).
        """
        # Always maintain local JSON backup
        store = os.path.join(self.user_data_dir, "reports.json")
        reports = []
        if os.path.isfile(store):
            try:
                with open(store, "r", encoding="utf-8") as fh:
                    reports = json.load(fh)
            except (OSError, ValueError):
                reports = []
        local_id = len(reports) + 1
        report["id"] = local_id
        reports.append(report)
        os.makedirs(self.user_data_dir, exist_ok=True)
        try:
            with open(store, "w", encoding="utf-8") as fh:
                json.dump(reports, fh, indent=2, ensure_ascii=False)
        except OSError:
            pass

        # Save to MySQL
        try:
            db_id = save_report_to_db(report)
            return db_id, "MySQL Database: pawhelp_db (table 'reports')"
        except Exception as exc:
            print("MySQL save notice:", exc)
            return local_id, f"Local backup (MySQL offline: {exc})"

    def call_number(self):
        if platform == "android":
            try:
                from jnius import autoclass
                Intent = autoclass("android.content.Intent")
                Uri = autoclass("android.net.Uri")
                activity = autoclass("org.kivy.android.PythonActivity").mActivity
                activity.startActivity(
                    Intent(Intent.ACTION_DIAL, Uri.parse("tel:" + PHONE_DIAL)))
                return
            except Exception as exc:  # fall through to the popup
                print("Could not open dialer:", exc)
        self.show_message("Calling", f"Dial {PHONE_DISPLAY} on your phone.")

    def show_message(self, title, message):
        content = BoxLayout(orientation="vertical", padding=dp(15), spacing=dp(12))
        content.add_widget(make_label(message, 15, CREAM, halign="center"))
        content.add_widget(Widget())
        close = PawButton(text="[b]OK[/b]", bg=DARK_GREEN, halign="center",
                          size_hint_y=None, height=dp(45))
        content.add_widget(close)
        popup = Popup(title=title, content=content, size_hint=(0.85, 0.38))
        close.bind(on_release=popup.dismiss)
        popup.open()


if __name__ == "__main__":
    PawHelpApp().run()
