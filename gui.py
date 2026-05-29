"""
Focus Guard GUI — PySide6 modern design with animations.
"""
import os, sys, time, json, math
from datetime import date

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton,
    QLineEdit, QTextEdit, QCheckBox, QScrollArea, QMessageBox,
    QVBoxLayout, QHBoxLayout, QGridLayout, QSizePolicy, QStackedWidget,
    QProgressBar, QSpacerItem, QDialog, QSystemTrayIcon, QMenu,
)
from PySide6.QtCore import (
    Qt, QTimer, Signal, QObject, QRect, QRectF, QSize,
)
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QPixmap, QIcon,
    QLinearGradient, QPainterPath, QCursor, QPalette,
    QTextCharFormat, QTextCursor,
)

from session import FocusSession
from usb_auth import detect_focus_guard_usb, register_device, get_usb_drive_path
from usb_protect import (protect, verify_and_unprotect, is_protected,
                          lock_usb_files, unlock_usb_files, is_ntfs,
                          convert_to_ntfs)


# ── Asset helpers ──────────────────────────────────────────────────────────────
def _asset(rel):
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, rel)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), rel)

def _cfg_path():
    base = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) \
           else os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "config.json")

def _load_pixmap(path, w, h):
    try:
        px = QPixmap(path)
        if not px.isNull():
            return px.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    except Exception:
        pass
    return None


# ── Themes ─────────────────────────────────────────────────────────────────────
DARK = dict(
    bg="#0c1220", surface="#111d30", panel="#162540",
    card="#1e304f", border="#2d4065",
    accent="#3b82f6", teal="#14b8a6", green="#22c55e",
    red="#ef4444", amber="#f59e0b",
    text="#e8f0fe", text_mid="#8ba4be", text_dim="#3d5a7a",
    btn_fg="#ffffff", input_bg="#0f1e35",
)
LIGHT = dict(
    bg="#f0f4f8", surface="#ffffff", panel="#e8eef5",
    card="#dde5f0", border="#b8c5d3",
    accent="#2563eb", teal="#0d9488", green="#16a34a",
    red="#dc2626", amber="#d97706",
    text="#0f1e30", text_mid="#4a6080", text_dim="#8ba4be",
    btn_fg="#ffffff", input_bg="#eef2f8",
)

# ── Duration choices ───────────────────────────────────────────────────────────
DURATIONS = [
    (2,"2m"),(3,"3m"),(5,"5m"),(10,"10m"),(15,"15m"),(20,"20m"),(25,"25m"),
    (30,"30m"),(35,"35m"),(40,"40m"),(45,"45m"),(50,"50m"),(55,"55m"),
    (60,"1 hr"),(90,"1h30"),(120,"2 hr"),(150,"2h30"),(180,"3 hr"),
    (210,"3h30"),(240,"4 hr"),(270,"4h30"),
]

# ── Categories ─────────────────────────────────────────────────────────────────
CATS = {
    "Social Media":          {"icon":"📱","color":"#a855f7","sites":["facebook.com","www.facebook.com","instagram.com","www.instagram.com","twitter.com","www.twitter.com","x.com","www.x.com","tiktok.com","www.tiktok.com","snapchat.com","www.snapchat.com","pinterest.com","www.pinterest.com","reddit.com","www.reddit.com","tumblr.com","www.tumblr.com","linkedin.com","www.linkedin.com","threads.net","www.threads.net"]},
    "Video & Entertainment": {"icon":"🎬","color":"#f87171","sites":["youtube.com","www.youtube.com","netflix.com","www.netflix.com","twitch.tv","www.twitch.tv","hulu.com","www.hulu.com","disneyplus.com","www.disneyplus.com","primevideo.com","www.primevideo.com","vimeo.com","www.vimeo.com","dailymotion.com","www.dailymotion.com","crunchyroll.com","www.crunchyroll.com","max.com","www.max.com"]},
    "Gaming":                {"icon":"🎮","color":"#4ade80","sites":["store.steampowered.com","steamcommunity.com","epicgames.com","www.epicgames.com","roblox.com","www.roblox.com","miniclip.com","www.miniclip.com","kongregate.com","www.kongregate.com","ign.com","www.ign.com","gamespot.com","www.gamespot.com","poki.com","www.poki.com"]},
    "News & Media":          {"icon":"📰","color":"#fb923c","sites":["cnn.com","www.cnn.com","bbc.com","www.bbc.com","foxnews.com","www.foxnews.com","msnbc.com","www.msnbc.com","buzzfeed.com","www.buzzfeed.com","theguardian.com","www.theguardian.com","nytimes.com","www.nytimes.com","washingtonpost.com","www.washingtonpost.com","huffpost.com","www.huffpost.com"]},
    "Shopping":              {"icon":"🛍️","color":"#38bdf8","sites":["amazon.com","www.amazon.com","ebay.com","www.ebay.com","aliexpress.com","www.aliexpress.com","etsy.com","www.etsy.com","shein.com","www.shein.com","walmart.com","www.walmart.com","target.com","www.target.com","wish.com","www.wish.com"]},
    "Music & Podcasts":      {"icon":"🎵","color":"#34d399","sites":["spotify.com","open.spotify.com","soundcloud.com","www.soundcloud.com","pandora.com","www.pandora.com","music.apple.com","deezer.com","www.deezer.com","tidal.com","www.tidal.com"]},
    "Messaging & Chat":      {"icon":"💬","color":"#facc15","sites":["web.whatsapp.com","web.telegram.org","discord.com","www.discord.com","messenger.com","www.messenger.com","slack.com","app.slack.com","teams.microsoft.com","skype.com","www.skype.com"]},
    "Adult & NSFW":          {"icon":"🔞","color":"#f43f5e","sites":["pornhub.com","www.pornhub.com","xvideos.com","www.xvideos.com","xnxx.com","www.xnxx.com","onlyfans.com","www.onlyfans.com","redtube.com","www.redtube.com"]},
}


# ── Color blend helper ─────────────────────────────────────────────────────────
def blend(c1: str, c2: str, t: float) -> str:
    """Blend two hex colors. t=1.0 → c1, t=0.0 → c2."""
    def p(h):
        h = h.lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    r1,g1,b1 = p(c1); r2,g2,b2 = p(c2)
    return "#{:02x}{:02x}{:02x}".format(
        int(r1*t + r2*(1-t)),
        int(g1*t + g2*(1-t)),
        int(b1*t + b2*(1-t)),
    )


# ── Thread → UI signal bridge ──────────────────────────────────────────────────
class _Bridge(QObject):
    tick  = Signal(int)
    ended = Signal()


# ══════════════════════════════════════════════════════════════════════════════
# First-run Welcome / EULA Dialog
# ══════════════════════════════════════════════════════════════════════════════
class WelcomeDialog(QDialog):
    """Shown once on first launch. User must agree to continue."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome to Focus Guard")
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint)
        self.setModal(True)
        self.setFixedWidth(580)
        self.setMinimumHeight(620)
        self._agreed = False
        self._build()
        self._apply_style()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header band ──────────────────────────────────────────────────────
        header = QFrame()
        header.setFixedHeight(130)
        header.setObjectName("wdHeader")
        hl = QVBoxLayout(header)
        hl.setAlignment(Qt.AlignCenter)
        hl.setSpacing(6)

        shield = QLabel("🛡")
        shield.setAlignment(Qt.AlignCenter)
        shield.setFont(QFont("Segoe UI Emoji", 36))
        shield.setObjectName("wdShield")

        title = QLabel("NACOMES Focus Guard")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setObjectName("wdTitle")

        hl.addWidget(shield)
        hl.addWidget(title)
        root.addWidget(header)

        # ── Scroll area for body content ──────────────────────────────────────
        scroll = QScrollArea()
        scroll.setObjectName("wdScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)

        body_w = QWidget()
        body_w.setObjectName("wdBody")
        bl = QVBoxLayout(body_w)
        bl.setContentsMargins(32, 24, 32, 24)
        bl.setSpacing(16)

        # About section
        about_hd = QLabel("About This Software")
        about_hd.setFont(QFont("Segoe UI", 11, QFont.Bold))
        about_hd.setObjectName("wdSecHead")

        about_txt = QLabel(
            "Focus Guard is a productivity enforcement system designed to help "
            "students, professionals, and individuals maintain deep concentration "
            "by blocking distracting websites during a timed focus session.\n\n"
            "Once a session is started, no one — not even the person who started it — "
            "can stop it before the timer expires. The session persists across "
            "system reboots, ensuring your commitment is honoured in full."
        )
        about_txt.setWordWrap(True)
        about_txt.setFont(QFont("Segoe UI", 10))
        about_txt.setObjectName("wdBodyText")

        # How it works
        how_hd = QLabel("How It Works")
        how_hd.setFont(QFont("Segoe UI", 11, QFont.Bold))
        how_hd.setObjectName("wdSecHead")

        how_txt = QLabel(
            "1.  Select the website categories you want to block.\n"
            "2.  Choose how long you want to focus (2 minutes to 4.5 hours).\n"
            "3.  Press  Start Session  — all selected sites are instantly blocked.\n"
            "4.  The countdown runs on real wall-clock time; shutting down your "
            "computer does not pause the timer.\n"
            "5.  When the timer reaches zero the sites are automatically unblocked."
        )
        how_txt.setWordWrap(True)
        how_txt.setFont(QFont("Segoe UI", 10))
        how_txt.setObjectName("wdBodyText")

        # Agreement
        agree_hd = QLabel("Terms of Use")
        agree_hd.setFont(QFont("Segoe UI", 11, QFont.Bold))
        agree_hd.setObjectName("wdSecHead")

        agree_txt = QLabel(
            "By clicking  \"I Agree & Continue\"  you acknowledge that:\n\n"
            "•  You understand that focus sessions cannot be cancelled once started.\n"
            "•  You accept full responsibility for the duration you choose.\n"
            "•  This software modifies your system's hosts file and firewall rules "
            "to block sites during a session — these changes are reversed "
            "automatically when the session ends.\n"
            "•  The developers are not liable for any inconvenience caused by "
            "an active session."
        )
        agree_txt.setWordWrap(True)
        agree_txt.setFont(QFont("Segoe UI", 10))
        agree_txt.setObjectName("wdBodyText")

        # Developer credits
        dev_frame = QFrame()
        dev_frame.setObjectName("wdDevFrame")
        dl = QVBoxLayout(dev_frame)
        dl.setContentsMargins(16, 14, 16, 14)
        dl.setSpacing(4)

        dev_label = QLabel("Developed by")
        dev_label.setAlignment(Qt.AlignCenter)
        dev_label.setFont(QFont("Segoe UI", 9))
        dev_label.setObjectName("wdDevSub")

        dev_name = QLabel("NACOMES Final Year Students")
        dev_name.setAlignment(Qt.AlignCenter)
        dev_name.setFont(QFont("Segoe UI", 12, QFont.Bold))
        dev_name.setObjectName("wdDevName")

        dev_school = QLabel("The Polytechnic, Ibadan  ·  Class of 2026")
        dev_school.setAlignment(Qt.AlignCenter)
        dev_school.setFont(QFont("Segoe UI", 10))
        dev_school.setObjectName("wdDevSchool")

        dl.addWidget(dev_label)
        dl.addWidget(dev_name)
        dl.addWidget(dev_school)

        bl.addWidget(about_hd)
        bl.addWidget(about_txt)
        bl.addSpacing(4)
        bl.addWidget(how_hd)
        bl.addWidget(how_txt)
        bl.addSpacing(4)
        bl.addWidget(agree_hd)
        bl.addWidget(agree_txt)
        bl.addSpacing(8)
        bl.addWidget(dev_frame)
        bl.addStretch()

        scroll.setWidget(body_w)
        root.addWidget(scroll, 1)

        # ── Button row ────────────────────────────────────────────────────────
        btn_frame = QFrame()
        btn_frame.setObjectName("wdBtnFrame")
        btn_frame.setFixedHeight(72)
        bfl = QHBoxLayout(btn_frame)
        bfl.setContentsMargins(32, 12, 32, 12)
        bfl.setSpacing(16)

        self._exit_btn = QPushButton("Exit")
        self._exit_btn.setFixedSize(120, 44)
        self._exit_btn.setObjectName("wdExitBtn")
        self._exit_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._exit_btn.clicked.connect(self._on_exit)

        self._agree_btn = QPushButton("I Agree & Continue  →")
        self._agree_btn.setFixedSize(220, 44)
        self._agree_btn.setObjectName("wdAgreeBtn")
        self._agree_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._agree_btn.clicked.connect(self._on_agree)

        bfl.addWidget(self._exit_btn)
        bfl.addStretch()
        bfl.addWidget(self._agree_btn)

        root.addWidget(btn_frame)

    def _apply_style(self):
        T = DARK
        self.setStyleSheet(f"""
            WelcomeDialog {{
                background: {T['bg']};
            }}
            QFrame#wdHeader {{
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 {T['panel']}, stop:1 {T['surface']});
                border-bottom: 1px solid {T['border']};
            }}
            QLabel#wdShield {{
                background: transparent;
                color: {T['accent']};
            }}
            QLabel#wdTitle {{
                background: transparent;
                color: {T['text']};
                letter-spacing: 1px;
            }}
            QWidget#wdBody {{
                background: {T['bg']};
            }}
            QScrollArea#wdScroll {{
                background: {T['bg']};
                border: none;
            }}
            QLabel#wdSecHead {{
                color: {T['accent']};
                border-left: 3px solid {T['accent']};
                padding-left: 8px;
                background: transparent;
            }}
            QLabel#wdBodyText {{
                color: {T['text']};
                background: transparent;
                line-height: 1.5;
            }}
            QFrame#wdDevFrame {{
                background: {T['card']};
                border: 1px solid {T['border']};
                border-radius: 10px;
            }}
            QLabel#wdDevSub {{
                color: {T['text_mid']};
                background: transparent;
            }}
            QLabel#wdDevName {{
                color: {T['text']};
                background: transparent;
            }}
            QLabel#wdDevSchool {{
                color: {T['teal']};
                background: transparent;
            }}
            QFrame#wdBtnFrame {{
                background: {T['surface']};
                border-top: 1px solid {T['border']};
            }}
            QPushButton#wdExitBtn {{
                background: transparent;
                color: {T['text_mid']};
                border: 1px solid {T['border']};
                border-radius: 8px;
                font-size: 13px;
                font-family: "Segoe UI";
            }}
            QPushButton#wdExitBtn:hover {{
                background: {T['card']};
                color: {T['text']};
            }}
            QPushButton#wdAgreeBtn {{
                background: {T['accent']};
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: bold;
                font-family: "Segoe UI";
            }}
            QPushButton#wdAgreeBtn:hover {{
                background: {blend(T['accent'], '#ffffff', 0.85)};
            }}
            QScrollBar:vertical {{
                background: {T['surface']};
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {T['border']};
                border-radius: 4px;
                min-height: 30px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

    def _on_agree(self):
        self._agreed = True
        self.accept()

    def _on_exit(self):
        self._agreed = False
        self.reject()

    def agreed(self) -> bool:
        return self._agreed


# ══════════════════════════════════════════════════════════════════════════════
# Animated Glow Canvas (lock screen)
# ══════════════════════════════════════════════════════════════════════════════
class GlowCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(220, 220)
        self._pulse = 0.0
        self._logo  = None
        self._T     = dict(DARK)

    def set_theme(self, T):
        self._T = T
        self.update()

    def set_pulse(self, val: float):
        self._pulse = val
        self.update()

    def set_logo(self, px: QPixmap):
        self._logo = px
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        T  = self._T
        cx, cy = 110, 110
        a  = max(0.0, min(1.0, self._pulse))
        # Animated glow rings
        for r, strength in [(105, 0.10), (92, 0.20), (79, 0.35), (66, 0.55)]:
            col_hex = blend(T["accent"], T["surface"], strength * a + (1 - a) * 0.05)
            pen = QPen(QColor(col_hex))
            pen.setWidth(2)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(cx - r, cy - r, 2*r, 2*r)
        # Filled inner circle
        ri = 56
        p.setPen(QPen(QColor(T["accent"]), 2))
        p.setBrush(QBrush(QColor(T["panel"])))
        p.drawEllipse(cx - ri, cy - ri, 2*ri, 2*ri)
        # Logo or fallback shield
        if self._logo:
            lx = cx - self._logo.width()  // 2
            ly = cy - self._logo.height() // 2
            p.drawPixmap(lx, ly, self._logo)
        else:
            p.setPen(QPen(QColor(T["accent"])))
            f = QFont("Segoe UI Emoji", 32)
            p.setFont(f)
            p.drawText(QRect(cx-40, cy-40, 80, 80), Qt.AlignCenter, "🛡")
        p.end()


# ══════════════════════════════════════════════════════════════════════════════
# Arc Timer Canvas (session screen)
# ══════════════════════════════════════════════════════════════════════════════
class ArcCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(260, 260)
        self._remaining = 1
        self._total     = 1
        self._T         = dict(DARK)

    def set_theme(self, T):
        self._T = T
        self.update()

    def update_arc(self, remaining, total):
        self._remaining = remaining
        self._total     = total
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        T       = self._T
        cx, cy  = 130, 130
        r       = 108
        # Track ring
        track = QPen(QColor(T["panel"]))
        track.setWidth(16)
        track.setCapStyle(Qt.RoundCap)
        p.setPen(track)
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(cx-r, cy-r, 2*r, 2*r)
        # Progress arc
        rem, tot = self._remaining, self._total
        frac = rem / tot if tot > 0 else 0.0
        color = T["accent"] if frac > 0.30 else (T["amber"] if frac > 0.10 else T["red"])
        if tot > 0 and rem > 0:
            span = int(-360 * 16 * frac)
            # Outer glow
            gpen = QPen(QColor(blend(color, T["bg"], 0.28)))
            gpen.setWidth(10)
            gpen.setCapStyle(Qt.RoundCap)
            p.setPen(gpen)
            p.drawArc(cx-r-4, cy-r-4, 2*(r+4), 2*(r+4), 90*16, span)
            # Main arc
            mpen = QPen(QColor(color))
            mpen.setWidth(16)
            mpen.setCapStyle(Qt.RoundCap)
            p.setPen(mpen)
            p.drawArc(cx-r, cy-r, 2*r, 2*r, 90*16, span)
        # Inner filled circle
        ri = r - 22
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(T["bg"])))
        p.drawEllipse(cx-ri, cy-ri, 2*ri, 2*ri)
        # Percentage text inside arc
        pct = int((1 - frac) * 100) if tot > 0 else 0
        p.setPen(QPen(QColor(color)))
        f = QFont("Segoe UI", 22)
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRect(cx-ri, cy-ri, 2*ri, 2*ri - 10), Qt.AlignCenter, f"{pct}%")
        p.setPen(QPen(QColor(T["text_mid"])))
        p.setFont(QFont("Segoe UI", 9))
        p.drawText(QRect(cx-ri, cy+16, 2*ri, 24), Qt.AlignCenter, "complete")
        p.end()


# ══════════════════════════════════════════════════════════════════════════════
# Category Card Widget
# ══════════════════════════════════════════════════════════════════════════════
class CatCard(QFrame):
    toggled = Signal(str, bool)

    def __init__(self, name, data, T, parent=None):
        super().__init__(parent)
        self._name = name
        self._data = data
        self._T    = T
        self.setFrameShape(QFrame.NoFrame)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self._build_ui()
        self._apply_styles(T)

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Colored accent bar on the left
        self._bar = QFrame()
        self._bar.setFixedWidth(5)
        layout.addWidget(self._bar)

        self._content = QWidget()
        cl = QHBoxLayout(self._content)
        cl.setContentsMargins(14, 13, 14, 13)
        cl.setSpacing(10)

        self._cb = QCheckBox(f"{self._data['icon']}  {self._name}")
        f = QFont("Segoe UI", 10)
        f.setBold(True)
        self._cb.setFont(f)
        self._cb.stateChanged.connect(self._on_check)
        cl.addWidget(self._cb, 1)

        uniq = len([s for s in self._data["sites"] if not s.startswith("www.")])
        self._cnt_lbl = QLabel(str(uniq))
        self._cnt_lbl.setFont(QFont("Segoe UI", 9))
        self._cnt_lbl.setAlignment(Qt.AlignCenter)
        self._cnt_lbl.setFixedSize(38, 22)
        cl.addWidget(self._cnt_lbl)

        layout.addWidget(self._content, 1)

    def _apply_styles(self, T):
        self._T = T
        checked = self._cb.isChecked()
        c = self._data['color']
        bg = blend(c, T['surface'], 0.10) if checked else T['surface']
        self.setStyleSheet(f"background-color: {bg}; border-radius: 8px;")
        bar_w = 5 if not checked else 7
        self._bar.setFixedWidth(bar_w)
        self._bar.setStyleSheet(
            f"background-color: {c}; border-radius: 3px;")
        self._content.setStyleSheet("background: transparent;")
        self._cb.setStyleSheet(f"""
            QCheckBox {{
                color: {T['text']};
                background: transparent;
                spacing: 10px;
            }}
            QCheckBox::indicator {{
                width: 17px; height: 17px;
                border: 2px solid {T['border']};
                border-radius: 4px;
                background: {T['card']};
            }}
            QCheckBox::indicator:checked {{
                background: {c};
                border-color: {c};
            }}
            QCheckBox::indicator:hover {{
                border-color: {c};
            }}
        """)
        cnt_bg = blend(c, T['card'], 0.20) if checked else T['card']
        cnt_fg = c if checked else T['text_mid']
        self._cnt_lbl.setStyleSheet(
            f"color: {cnt_fg}; background: {cnt_bg};"
            f" border-radius: 11px; font-weight: bold;")

    def update_theme(self, T):
        self._apply_styles(T)

    def is_checked(self):
        return self._cb.isChecked()

    def set_checked(self, val):
        self._cb.blockSignals(True)
        self._cb.setChecked(val)
        self._cb.blockSignals(False)

    def _on_check(self, state):
        self._apply_styles(self._T)
        self.toggled.emit(self._name, bool(state))

    def enterEvent(self, event):
        if not self._cb.isChecked():
            c = blend(self._T["surface"], self._data['color'], 0.95)
            self.setStyleSheet(f"background-color: {c}; border-radius: 8px;")
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._apply_styles(self._T)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self._cb.setChecked(not self._cb.isChecked())
        super().mousePressEvent(event)


# ══════════════════════════════════════════════════════════════════════════════
# Main Application Window
# ══════════════════════════════════════════════════════════════════════════════
class FocusGuardApp(QMainWindow):

    def __init__(self, resume_info=None):
        super().__init__()
        self._dark       = True
        self._T          = dict(DARK)
        self._state      = "locked"
        self._usb_ok     = False
        self._ask_reg    = False
        self._cat_cards  = {}
        self._custom     = []
        self._dur_mins   = 25
        self._ses_total  = 0
        self._pulse_val  = 0.0
        self._pulse_dir  = 1
        self._type_i     = 0
        self._session    = None
        self._resume     = resume_info
        self._logo_px    = {}
        self._blink_on   = True
        self._usb_handles = []
        self._usb_path    = None
        self._usb_locked  = False
        self._fade_step  = 8
        self._fade_in    = False
        self._fade_tgt   = "locked"
        self._fade_timer = None
        self._bridge     = _Bridge()
        self._bridge.tick.connect(self._on_tick)
        self._bridge.ended.connect(self._on_end)

        self.setWindowTitle("NACOMES Focus Guard — Productivity Enforcement System")
        self.setMinimumSize(1020, 660)
        self.resize(1180, 740)

        self._load_logos()
        self._build_ui()
        self._apply_theme()

        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._animate)
        self._anim_timer.start(60)

        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._blink_status)
        self._blink_timer.start(500)

        self._usb_timer = QTimer(self)
        self._usb_timer.timeout.connect(self._poll_usb)
        self._usb_timer.start(2000)

        self._setup_tray()

        if resume_info:
            self._resume_session(resume_info)
        else:
            self._switch("locked")

    # ── Logo loading ───────────────────────────────────────────────────────────

    def _load_logos(self):
        path = _asset(os.path.join("image", "logo.png"))
        for sz in [44, 80, 120, 160]:
            px = _load_pixmap(path, sz, sz)
            if px:
                self._logo_px[sz] = px

    def _px(self, sz):
        return self._logo_px.get(sz)

    # ── UI Construction ────────────────────────────────────────────────────────

    # ── Font helpers ───────────────────────────────────────────────────────────
    @staticmethod
    def _f(size, bold=False, family="Segoe UI"):
        f = QFont(family, size)
        if bold:
            f.setBold(True)
        return f

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        self._root_layout = QVBoxLayout(root)
        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(0)

        self._build_header()

        self._stack = QStackedWidget()
        self._root_layout.addWidget(self._stack)

        self._build_lock()
        self._build_dashboard()
        self._build_session()

    # ── HEADER ─────────────────────────────────────────────────────────────────

    def _build_header(self):
        self._header = QFrame()
        self._header.setFixedHeight(66)
        hl = QHBoxLayout(self._header)
        hl.setContentsMargins(22, 0, 22, 0)

        # Brand (left)
        lft = QWidget()
        ll = QHBoxLayout(lft)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(14)
        px = self._px(44)
        if px:
            logo_lbl = QLabel()
            logo_lbl.setPixmap(px)
            ll.addWidget(logo_lbl)
        brand = QWidget()
        bl = QVBoxLayout(brand)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(1)
        self._brand_title = QLabel("NACOMES  FOCUS GUARD")
        f = QFont("Segoe UI", 13)
        f.setBold(True)
        self._brand_title.setFont(f)
        self._brand_sub = QLabel("USB-Authenticated Productivity Enforcement System")
        self._brand_sub.setFont(QFont("Segoe UI", 8))
        bl.addWidget(self._brand_title)
        bl.addWidget(self._brand_sub)
        ll.addWidget(brand)
        hl.addWidget(lft)
        hl.addStretch()

        # Controls (right)
        rgt = QWidget()
        rl = QHBoxLayout(rgt)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(10)

        self._usb_dot = QLabel("●")
        self._usb_dot.setFont(QFont("Segoe UI", 11))
        self._usb_lbl = QLabel("No USB Detected")
        self._usb_lbl.setFont(QFont("Segoe UI", 9))
        rl.addWidget(self._usb_dot)
        rl.addWidget(self._usb_lbl)

        d1 = QFrame()
        d1.setFrameShape(QFrame.VLine)
        d1.setFixedHeight(22)
        rl.addWidget(d1)
        self._hdiv1 = d1

        self._theme_btn = QPushButton("☀️")
        self._theme_btn.setFont(QFont("Segoe UI", 12))
        self._theme_btn.setFixedSize(40, 32)
        self._theme_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._theme_btn.clicked.connect(self._toggle_theme)
        rl.addWidget(self._theme_btn)

        d2 = QFrame()
        d2.setFrameShape(QFrame.VLine)
        d2.setFixedHeight(22)
        rl.addWidget(d2)
        self._hdiv2 = d2

        self._ver_lbl = QLabel("v2.0")
        self._ver_lbl.setFont(QFont("Segoe UI", 8))
        rl.addWidget(self._ver_lbl)

        d3 = QFrame()
        d3.setFrameShape(QFrame.VLine)
        d3.setFixedHeight(22)
        rl.addWidget(d3)
        self._hdiv3 = d3

        self._prot_btn = QPushButton("🔐")
        self._prot_btn.setFont(QFont("Segoe UI", 12))
        self._prot_btn.setFixedSize(40, 32)
        self._prot_btn.setToolTip("USB File Protection")
        self._prot_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._prot_btn.clicked.connect(self._usb_protection_dialog)
        self._prot_btn.setVisible(False)
        rl.addWidget(self._prot_btn)

        hl.addWidget(rgt)
        self._root_layout.addWidget(self._header)

    # ── LOCK SCREEN ────────────────────────────────────────────────────────────

    def _build_lock(self):
        self._lock_w = QWidget()
        outer = QVBoxLayout(self._lock_w)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Center card
        center_area = QWidget()
        cal = QVBoxLayout(center_area)
        cal.setAlignment(Qt.AlignCenter)

        self._lock_card = QFrame()
        self._lock_card.setFixedWidth(580)
        card_l = QVBoxLayout(self._lock_card)
        card_l.setContentsMargins(60, 46, 60, 46)
        card_l.setSpacing(0)
        card_l.setAlignment(Qt.AlignHCenter)

        self._glow = GlowCanvas()
        if 80 in self._logo_px:
            self._glow.set_logo(self._logo_px[80])
        card_l.addWidget(self._glow, 0, Qt.AlignHCenter)
        card_l.addSpacing(22)

        self._lock_title = QLabel("NACOMES  FOCUS GUARD")
        f = QFont("Segoe UI", 20)
        f.setBold(True)
        self._lock_title.setFont(f)
        self._lock_title.setAlignment(Qt.AlignCenter)
        card_l.addWidget(self._lock_title)

        self._lock_sub = QLabel("USB-Authenticated Productivity System")
        self._lock_sub.setFont(QFont("Segoe UI", 10))
        self._lock_sub.setAlignment(Qt.AlignCenter)
        card_l.addWidget(self._lock_sub)
        card_l.addSpacing(26)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        self._lock_sep = sep
        card_l.addWidget(sep)
        card_l.addSpacing(26)

        self._type_lbl = QLabel("")
        self._type_lbl.setFont(QFont("Segoe UI", 12))
        self._type_lbl.setAlignment(Qt.AlignCenter)
        self._type_lbl.setMinimumHeight(28)
        card_l.addWidget(self._type_lbl)
        card_l.addSpacing(18)

        self._lock_desc = QLabel(
            "Focus Guard blocks distracting websites at the OS level.\n"
            "A physical USB key is required — no password can bypass it.")
        self._lock_desc.setFont(QFont("Segoe UI", 9))
        self._lock_desc.setAlignment(Qt.AlignCenter)
        self._lock_desc.setWordWrap(True)
        card_l.addWidget(self._lock_desc)

        cal.addWidget(self._lock_card)
        outer.addWidget(center_area, 1)

        # Feature pills row
        pills_area = QWidget()
        pills_area.setFixedHeight(60)
        pl = QHBoxLayout(pills_area)
        pl.setAlignment(Qt.AlignCenter)
        pl.setSpacing(20)
        self._pill_frames = []
        for icon, text in [("🔒","OS-Level Block"),("⏱️","Persist Across Reboots"),
                            ("📊","Session Analytics"),("🔑","USB Auth")]:
            pill = QFrame()
            pll = QHBoxLayout(pill)
            pll.setContentsMargins(18, 10, 18, 10)
            lw = QLabel(f"{icon}  {text}")
            lw.setFont(QFont("Segoe UI", 9))
            pll.addWidget(lw)
            self._pill_frames.append((pill, lw))
            pl.addWidget(pill)
        outer.addWidget(pills_area)

        self._stack.addWidget(self._lock_w)

    # ── DASHBOARD ──────────────────────────────────────────────────────────────

    def _build_dashboard(self):
        self._dash_w = QWidget()
        layout = QHBoxLayout(self._dash_w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ══════════════════════════════════════════════════════════════════════
        # Sidebar (left panel)
        # ══════════════════════════════════════════════════════════════════════
        self._sidebar = QFrame()
        self._sidebar.setFixedWidth(380)
        sbl = QVBoxLayout(self._sidebar)
        sbl.setContentsMargins(0, 0, 0, 0)
        sbl.setSpacing(0)

        # Sidebar header row
        shdr = QWidget()
        shl = QHBoxLayout(shdr)
        shl.setContentsMargins(20, 20, 20, 10)
        self._cats_hdr_lbl = QLabel("BLOCK CATEGORIES")
        self._cats_hdr_lbl.setFont(self._f(9, bold=True))
        self._sel_badge = QLabel("none selected")
        self._sel_badge.setFont(self._f(9))
        shl.addWidget(self._cats_hdr_lbl)
        shl.addStretch()
        shl.addWidget(self._sel_badge)
        sbl.addWidget(shdr)

        # Scrollable category cards
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._cats_container = QWidget()
        self._cats_layout = QVBoxLayout(self._cats_container)
        self._cats_layout.setContentsMargins(8, 4, 8, 4)
        self._cats_layout.setSpacing(5)
        self._cats_layout.addStretch()
        self._scroll.setWidget(self._cats_container)
        sbl.addWidget(self._scroll, 1)

        self._cat_cards = {}
        for name, data in CATS.items():
            card = CatCard(name, data, self._T)
            card.toggled.connect(self._cat_changed_slot)
            self._cat_cards[name] = card
            self._cats_layout.insertWidget(self._cats_layout.count() - 1, card)

        # Custom sites section
        self._sdiv = QFrame()
        self._sdiv.setFrameShape(QFrame.HLine)
        self._sdiv.setFixedHeight(1)
        sbl.addWidget(self._sdiv)

        custom_hdr_row = QWidget()
        chl = QHBoxLayout(custom_hdr_row)
        chl.setContentsMargins(20, 12, 20, 6)
        self._custom_hdr = QLabel("CUSTOM SITES")
        self._custom_hdr.setFont(self._f(9, bold=True))
        chl.addWidget(self._custom_hdr)
        chl.addStretch()
        sbl.addWidget(custom_hdr_row)

        entry_row = QWidget()
        erl = QHBoxLayout(entry_row)
        erl.setContentsMargins(16, 0, 16, 6)
        erl.setSpacing(10)
        self._ce = QLineEdit()
        self._ce.setPlaceholderText("e.g. example.com")
        self._ce.setFont(self._f(10))
        self._ce.setFixedHeight(40)
        self._ce.returnPressed.connect(self._add_custom)
        erl.addWidget(self._ce)
        self._add_btn = QPushButton("+ Add")
        self._add_btn.setFont(self._f(9, bold=True))
        self._add_btn.setFixedSize(72, 40)
        self._add_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._add_btn.clicked.connect(self._add_custom)
        erl.addWidget(self._add_btn)
        sbl.addWidget(entry_row)

        self._clbl = QLabel("No custom sites added.")
        self._clbl.setFont(self._f(9))
        self._clbl.setContentsMargins(20, 0, 0, 14)
        sbl.addWidget(self._clbl)

        layout.addWidget(self._sidebar)

        self._dash_vdiv = QFrame()
        self._dash_vdiv.setFrameShape(QFrame.VLine)
        self._dash_vdiv.setFixedWidth(1)
        layout.addWidget(self._dash_vdiv)

        # ══════════════════════════════════════════════════════════════════════
        # Main content (right panel)
        # ══════════════════════════════════════════════════════════════════════
        self._main_w = QWidget()
        ml = QVBoxLayout(self._main_w)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(0)

        # ── Summary bar ──────────────────────────────────────────────────────
        self._sum_bar = QFrame()
        self._sum_bar.setFixedHeight(56)
        sbl2 = QHBoxLayout(self._sum_bar)
        sbl2.setContentsMargins(24, 0, 24, 0)
        self._sum_lbl = QLabel("Select categories on the left to get started")
        self._sum_lbl.setFont(self._f(10))
        self._cnt_lbl = QLabel("0 sites")
        self._cnt_lbl.setFont(self._f(15, bold=True))
        sbl2.addWidget(self._sum_lbl, 1)
        sbl2.addWidget(self._cnt_lbl)
        ml.addWidget(self._sum_bar)

        inner = QWidget()
        self._main_inner = inner
        il = QVBoxLayout(inner)
        il.setContentsMargins(24, 20, 24, 20)
        il.setSpacing(0)

        # ── Duration section ──────────────────────────────────────────────────
        self._dur_hdr = self._section_label("FOCUS DURATION")
        il.addWidget(self._dur_hdr)
        il.addSpacing(12)

        self._grid_w = QWidget()
        grid = QGridLayout(self._grid_w)
        grid.setSpacing(6)
        grid.setContentsMargins(0, 0, 0, 0)
        self._dur_btns = {}
        COLS = 7
        for i, (m, lbl) in enumerate(DURATIONS):
            btn = QPushButton(lbl)
            btn.setFont(self._f(10))
            btn.setFixedSize(78, 38)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.clicked.connect(lambda checked=False, v=m: self._set_dur(v))
            grid.addWidget(btn, i // COLS, i % COLS)
            self._dur_btns[m] = btn
        il.addWidget(self._grid_w)
        il.addSpacing(20)

        # ── Blocked sites preview ─────────────────────────────────────────────
        self._prev_hdr = self._section_label("WEBSITES THAT WILL BE BLOCKED")
        il.addWidget(self._prev_hdr)
        il.addSpacing(10)

        self._prev = QTextEdit()
        self._prev.setFont(self._f(10, family="Consolas"))
        self._prev.setReadOnly(True)
        self._prev.setFrameShape(QFrame.NoFrame)
        self._prev.setMinimumHeight(100)
        il.addWidget(self._prev, 1)
        il.addSpacing(14)

        # ── Stats bar ──────────────────────────────────────────────────────────
        self._stats_bar = QFrame()
        self._stats_bar.setFixedHeight(44)
        stl = QHBoxLayout(self._stats_bar)
        stl.setContentsMargins(18, 0, 18, 0)
        stl.setSpacing(0)
        self._s_today = QLabel("Sessions today: 0")
        self._s_today.setFont(self._f(10))
        self._s_total_lbl = QLabel("Total focus time: 0m")
        self._s_total_lbl.setFont(self._f(10))
        self._stats_div = QFrame()
        self._stats_div.setFrameShape(QFrame.VLine)
        self._stats_div.setFixedHeight(18)
        self._stats_div.setContentsMargins(14, 0, 14, 0)
        stl.addWidget(self._s_today)
        stl.addWidget(self._stats_div)
        stl.addWidget(self._s_total_lbl)
        stl.addStretch()
        il.addWidget(self._stats_bar)
        il.addSpacing(12)

        # ── Start button ───────────────────────────────────────────────────────
        self._start_btn = QPushButton("▶   START FOCUS SESSION")
        self._start_btn.setFont(self._f(14, bold=True))
        self._start_btn.setFixedHeight(62)
        self._start_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._start_btn.clicked.connect(self._start)
        il.addWidget(self._start_btn)

        ml.addWidget(inner, 1)
        layout.addWidget(self._main_w, 1)

        self._stack.addWidget(self._dash_w)
        self._set_dur(25)

    def _section_label(self, text):
        """Styled section header label with accent left border."""
        w = QLabel(text)
        w.setFont(self._f(9, bold=True))
        w.setContentsMargins(10, 0, 0, 0)
        return w

    # ── SESSION SCREEN ─────────────────────────────────────────────────────────

    def _build_session(self):
        self._sess_w = QWidget()
        layout = QHBoxLayout(self._sess_w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Info strip (left)
        self._strip = QFrame()
        self._strip.setFixedWidth(310)
        sl = QVBoxLayout(self._strip)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(0)
        sl.setAlignment(Qt.AlignTop)

        px = self._px(80)
        if px:
            ll = QLabel()
            ll.setPixmap(px)
            ll.setAlignment(Qt.AlignHCenter)
            ll.setContentsMargins(0, 28, 0, 0)
            sl.addWidget(ll)

        self._sg_lbl = QLabel("FOCUS GUARD")
        f = QFont("Segoe UI", 11)
        f.setBold(True)
        self._sg_lbl.setFont(f)
        self._sg_lbl.setAlignment(Qt.AlignCenter)
        self._sg_lbl.setContentsMargins(0, 8, 0, 0)
        sl.addWidget(self._sg_lbl)

        d1 = QFrame()
        d1.setFrameShape(QFrame.HLine)
        d1.setContentsMargins(18, 16, 18, 16)
        self._s_d1 = d1
        sl.addWidget(d1)

        self._nb_lbl = QLabel("NOW BLOCKING")
        f2 = QFont("Segoe UI", 8)
        f2.setBold(True)
        self._nb_lbl.setFont(f2)
        self._nb_lbl.setContentsMargins(20, 0, 0, 0)
        sl.addWidget(self._nb_lbl)

        self._blk_lbl = QLabel("0")
        f3 = QFont("Segoe UI", 44)
        f3.setBold(True)
        self._blk_lbl.setFont(f3)
        self._blk_lbl.setAlignment(Qt.AlignCenter)
        sl.addWidget(self._blk_lbl)

        self._web_lbl = QLabel("websites")
        self._web_lbl.setFont(QFont("Segoe UI", 10))
        self._web_lbl.setAlignment(Qt.AlignCenter)
        sl.addWidget(self._web_lbl)

        d2 = QFrame()
        d2.setFrameShape(QFrame.HLine)
        d2.setContentsMargins(18, 16, 18, 16)
        self._s_d2 = d2
        sl.addWidget(d2)

        self._ac_lbl = QLabel("ACTIVE CATEGORIES")
        f4 = QFont("Segoe UI", 8)
        f4.setBold(True)
        self._ac_lbl.setFont(f4)
        self._ac_lbl.setContentsMargins(20, 0, 0, 6)
        sl.addWidget(self._ac_lbl)

        self._scats_w = QWidget()
        self._scats_layout = QVBoxLayout(self._scats_w)
        self._scats_layout.setContentsMargins(14, 0, 14, 0)
        self._scats_layout.setSpacing(4)
        sl.addWidget(self._scats_w)

        d3 = QFrame()
        d3.setFrameShape(QFrame.HLine)
        d3.setContentsMargins(18, 16, 18, 16)
        self._s_d3 = d3
        sl.addWidget(d3)

        self._susb = QLabel("🔒  Blocking active\nUSB can be removed")
        self._susb.setFont(QFont("Segoe UI", 9))
        self._susb.setContentsMargins(20, 0, 0, 0)
        sl.addWidget(self._susb)
        sl.addStretch()

        layout.addWidget(self._strip)

        vdiv = QFrame()
        vdiv.setFrameShape(QFrame.VLine)
        vdiv.setFixedWidth(1)
        self._sess_vdiv = vdiv
        layout.addWidget(vdiv)

        # Center timer area — scrollable so it never clips on small windows
        center_scroll = QScrollArea()
        center_scroll.setFrameShape(QFrame.NoFrame)
        center_scroll.setWidgetResizable(True)
        center_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        center_scroll.setStyleSheet("background: transparent; border: none;")
        self._center_scroll = center_scroll

        self._center_w = QWidget()
        self._center_w.setStyleSheet("background: transparent;")
        cl = QVBoxLayout(self._center_w)
        cl.setContentsMargins(48, 20, 48, 20)
        cl.setSpacing(0)

        cl.addStretch(1)

        # Status dot + label
        status_row = QWidget()
        status_row.setStyleSheet("background: transparent;")
        srl = QHBoxLayout(status_row)
        srl.setContentsMargins(0, 0, 0, 0)
        srl.setAlignment(Qt.AlignCenter)
        srl.setSpacing(8)
        self._status_dot = QLabel("●")
        self._status_dot.setFont(QFont("Segoe UI", 10))
        self._status_lbl = QLabel("FOCUS MODE ACTIVE")
        f5 = QFont("Segoe UI", 10)
        f5.setBold(True)
        f5.setLetterSpacing(QFont.AbsoluteSpacing, 1.5)
        self._status_lbl.setFont(f5)
        srl.addWidget(self._status_dot)
        srl.addWidget(self._status_lbl)
        cl.addWidget(status_row)
        cl.addSpacing(20)

        self._arc = ArcCanvas()
        cl.addWidget(self._arc, 0, Qt.AlignHCenter)
        cl.addSpacing(16)

        self._timer_lbl = QLabel("--:--")
        f6 = QFont("Segoe UI", 46)
        f6.setBold(True)
        self._timer_lbl.setFont(f6)
        self._timer_lbl.setAlignment(Qt.AlignCenter)
        self._timer_lbl.setMinimumWidth(280)
        cl.addWidget(self._timer_lbl)

        self._rem_lbl = QLabel("remaining")
        self._rem_lbl.setFont(QFont("Segoe UI", 10))
        self._rem_lbl.setAlignment(Qt.AlignCenter)
        cl.addWidget(self._rem_lbl)
        cl.addSpacing(26)

        # Progress bar row — expands with window width
        pb_row = QWidget()
        pb_row.setStyleSheet("background: transparent;")
        pbl = QHBoxLayout(pb_row)
        pbl.setContentsMargins(0, 0, 0, 0)
        pbl.setSpacing(12)
        self._pb = QProgressBar()
        self._pb.setFixedHeight(10)
        self._pb.setTextVisible(False)
        self._pb.setRange(0, 100)
        self._pb.setValue(0)
        self._pb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._pct_lbl = QLabel("0%")
        self._pct_lbl.setFont(QFont("Segoe UI", 9))
        self._pct_lbl.setFixedWidth(36)
        self._pct_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        pbl.addWidget(self._pb, 1)
        pbl.addWidget(self._pct_lbl)
        cl.addWidget(pb_row)
        cl.addSpacing(28)

        # Lock banner — expands with window width, no fixed size
        self._lock_banner = QFrame()
        self._lock_banner.setFixedHeight(88)
        self._lock_banner.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lb_l = QVBoxLayout(self._lock_banner)
        lb_l.setContentsMargins(28, 14, 28, 14)
        lb_l.setSpacing(6)
        lb_title = QLabel("🔒  SESSION LOCKED — Cannot Be Stopped")
        f_lb = QFont("Segoe UI", 11)
        f_lb.setBold(True)
        lb_title.setFont(f_lb)
        lb_title.setAlignment(Qt.AlignCenter)
        self._lb_title = lb_title
        lb_sub = QLabel(
            "Timer expiry is the only exit. "
            "Shutting down the computer does not cancel the session.")
        lb_sub.setFont(QFont("Segoe UI", 8))
        lb_sub.setAlignment(Qt.AlignCenter)
        lb_sub.setWordWrap(True)
        self._lb_sub = lb_sub
        lb_l.addWidget(lb_title)
        lb_l.addWidget(lb_sub)
        cl.addWidget(self._lock_banner)

        cl.addStretch(1)

        center_scroll.setWidget(self._center_w)
        layout.addWidget(center_scroll, 1)
        self._stack.addWidget(self._sess_w)

    # ── THEME ──────────────────────────────────────────────────────────────────

    def _toggle_theme(self):
        self._dark = not self._dark
        self._T    = dict(DARK if self._dark else LIGHT)
        self._apply_theme()

    def _apply_theme(self):
        T = self._T

        # Root + header
        self.centralWidget().setStyleSheet(f"background-color: {T['bg']};")
        self._header.setStyleSheet(
            f"background-color: {T['surface']}; border-bottom: 1px solid {T['border']};")
        self._brand_title.setStyleSheet(f"color: {T['text']}; background: transparent;")
        self._brand_sub.setStyleSheet(f"color: {T['text_mid']}; background: transparent;")
        self._usb_dot.setStyleSheet(f"color: {T['red']}; background: transparent;")
        self._usb_lbl.setStyleSheet(f"color: {T['text_mid']}; background: transparent;")
        self._hdiv1.setStyleSheet(f"color: {T['border']};")
        self._hdiv2.setStyleSheet(f"color: {T['border']};")
        self._theme_btn.setText("☀️" if not self._dark else "🌙")
        self._theme_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {T['panel']}; border: none;
                border-radius: 6px; color: {T['text_mid']};
            }}
            QPushButton:hover {{ background-color: {T['card']}; }}
        """)
        self._ver_lbl.setStyleSheet(f"color: {T['text_dim']}; background: transparent;")
        self._hdiv3.setStyleSheet(f"color: {T['border']};")
        self._prot_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {T['panel']}; border: none;
                border-radius: 6px; color: {T['text_mid']};
            }}
            QPushButton:hover {{ background-color: {T['card']}; }}
        """)

        # Lock screen
        self._lock_w.setStyleSheet(f"background-color: {T['bg']};")
        self._lock_card.setStyleSheet(
            f"background-color: {T['surface']}; border-radius: 12px;")
        self._lock_title.setStyleSheet(f"color: {T['text']}; background: transparent;")
        self._lock_sub.setStyleSheet(f"color: {T['text_mid']}; background: transparent;")
        self._lock_sep.setStyleSheet(f"color: {T['border']};")
        self._type_lbl.setStyleSheet(f"color: {T['amber']}; background: transparent;")
        self._lock_desc.setStyleSheet(f"color: {T['text_mid']}; background: transparent;")
        for pill, lw in self._pill_frames:
            pill.setStyleSheet(f"background-color: {T['panel']}; border-radius: 8px;")
            lw.setStyleSheet(f"color: {T['text_mid']}; background: transparent;")
        self._glow.set_theme(T)

        # Dashboard
        self._dash_w.setStyleSheet(f"background-color: {T['bg']};")
        self._sidebar.setStyleSheet(f"background-color: {T['surface']};")
        self._scroll.setStyleSheet(f"background-color: {T['surface']}; border: none;")
        self._cats_container.setStyleSheet(f"background-color: {T['surface']};")
        self._cats_hdr_lbl.setStyleSheet(
            f"color: {T['text']}; background: transparent;"
            f" border-left: 3px solid {T['accent']}; padding-left: 8px;")
        self._sel_badge.setStyleSheet(
            f"color: {T['accent']}; background: {T['card']};"
            f" border-radius: 10px; padding: 3px 10px; font-weight: bold;")
        self._sdiv.setStyleSheet(f"color: {T['border']};")
        self._custom_hdr.setStyleSheet(
            f"color: {T['text']}; background: transparent;"
            f" border-left: 3px solid {T['teal']}; padding-left: 8px;")
        self._ce.setStyleSheet(f"""
            QLineEdit {{
                background-color: {T['input_bg']}; color: {T['text']};
                border: 1.5px solid {T['border']}; border-radius: 8px;
                padding: 4px 12px; font-size: 10pt;
            }}
            QLineEdit:focus {{ border: 1.5px solid {T['accent']}; }}
            QLineEdit::placeholder {{ color: {T['text_dim']}; }}
        """)
        self._add_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {T['accent']}; color: {T['btn_fg']};
                border: none; border-radius: 8px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {T['teal']}; }}
        """)
        self._clbl.setStyleSheet(f"color: {T['text_mid']}; background: transparent;")
        self._dash_vdiv.setStyleSheet(f"color: {T['border']};")
        self._main_w.setStyleSheet(f"background-color: {T['bg']};")
        self._sum_bar.setStyleSheet(
            f"background-color: {T['panel']};"
            f" border-bottom: 1px solid {T['border']};")
        self._sum_lbl.setStyleSheet(f"color: {T['text_mid']}; background: transparent;")
        self._cnt_lbl.setStyleSheet(f"color: {T['accent']}; background: transparent;")
        self._main_inner.setStyleSheet(f"background-color: {T['bg']};")
        self._dur_hdr.setStyleSheet(
            f"color: {T['text']}; background: transparent;"
            f" border-left: 3px solid {T['accent']}; padding-left: 8px;")
        self._grid_w.setStyleSheet(f"background: transparent;")
        self._prev_hdr.setStyleSheet(
            f"color: {T['text']}; background: transparent;"
            f" border-left: 3px solid {T['accent']}; padding-left: 8px;")
        self._prev.setStyleSheet(f"""
            QTextEdit {{
                background-color: {T['card']}; color: {T['text']};
                border: 1px solid {T['border']}; border-radius: 8px; padding: 10px;
            }}
            QScrollBar:vertical {{
                background: {T['card']}; width: 6px;
            }}
            QScrollBar::handle:vertical {{
                background: {T['border']}; border-radius: 3px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)
        self._stats_bar.setStyleSheet(
            f"background-color: {T['surface']}; border-radius: 8px;"
            f" border: 1px solid {T['border']};")
        self._s_today.setStyleSheet(f"color: {T['text']}; background: transparent;")
        self._stats_div.setStyleSheet(f"color: {T['border']};")
        self._s_total_lbl.setStyleSheet(f"color: {T['text']}; background: transparent;")
        self._start_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {T['accent']}; color: {T['btn_fg']};
                border: none; border-radius: 10px; letter-spacing: 1px;
            }}
            QPushButton:hover {{ background-color: {T['teal']}; }}
            QPushButton:pressed {{ background-color: {T['green']}; }}
        """)
        self._set_dur(self._dur_mins)
        for card in self._cat_cards.values():
            card.update_theme(T)

        # Session screen
        self._sess_w.setStyleSheet(f"background-color: {T['bg']};")
        self._strip.setStyleSheet(f"background-color: {T['surface']};")
        self._sg_lbl.setStyleSheet(f"color: {T['text']}; background: transparent;")
        for d in (self._s_d1, self._s_d2, self._s_d3):
            d.setStyleSheet(f"color: {T['border']};")
        self._nb_lbl.setStyleSheet(f"color: {T['text_dim']}; background: transparent;")
        self._blk_lbl.setStyleSheet(f"color: {T['teal']}; background: transparent;")
        self._web_lbl.setStyleSheet(f"color: {T['text_mid']}; background: transparent;")
        self._ac_lbl.setStyleSheet(f"color: {T['text_dim']}; background: transparent;")
        self._susb.setStyleSheet(f"color: {T['text_mid']}; background: transparent;")
        self._sess_vdiv.setStyleSheet(f"color: {T['border']};")
        self._center_scroll.setStyleSheet(f"background: {T['bg']}; border: none;")
        self._center_w.setStyleSheet(f"background-color: {T['bg']};")
        self._status_dot.setStyleSheet(f"color: {T['green']}; background: transparent;")
        self._status_lbl.setStyleSheet(f"color: {T['green']}; background: transparent;")
        self._timer_lbl.setStyleSheet(f"color: {T['text']}; background: transparent;")
        self._rem_lbl.setStyleSheet(f"color: {T['text_mid']}; background: transparent;")
        self._pb.setStyleSheet(f"""
            QProgressBar {{
                background-color: {T['panel']}; border: none; border-radius: 5px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {T['accent']}, stop:1 {T['teal']});
                border-radius: 5px;
            }}
        """)
        self._pct_lbl.setStyleSheet(f"color: {T['text_mid']}; background: transparent;")
        self._lock_banner.setStyleSheet(
            f"background-color: {T['panel']}; border: 2px solid {T['amber']};"
            f" border-radius: 12px;")
        self._lb_title.setStyleSheet(f"color: {T['amber']}; background: transparent;")
        self._lb_sub.setStyleSheet(f"color: {T['text_mid']}; background: transparent;")
        self._arc.set_theme(T)
        # Scroll bar for center scroll area
        self._center_scroll.verticalScrollBar().setStyleSheet(f"""
            QScrollBar:vertical {{
                background: {T['bg']}; width: 6px; border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background: {T['border']}; border-radius: 3px; min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

        # Scroll bar in sidebar
        self._scroll.verticalScrollBar().setStyleSheet(f"""
            QScrollBar:vertical {{
                background: {T['surface']}; width: 6px; border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background: {T['border']}; border-radius: 3px; min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

    # ── ANIMATIONS ─────────────────────────────────────────────────────────────

    _HINT = "⏳   Insert your USB key to unlock"

    def _animate(self):
        self._pulse_val += 0.035 * self._pulse_dir
        if self._pulse_val >= 1.0:
            self._pulse_dir = -1
        elif self._pulse_val <= 0.0:
            self._pulse_dir = 1

        T = self._T

        if self._state == "locked":
            self._glow.set_pulse(self._pulse_val)
            full = self._HINT
            self._type_i = (self._type_i + 1) % (len(full) + 20)
            shown  = full[:min(self._type_i, len(full))]
            cursor = "▌" if (self._type_i // 6) % 2 == 0 else " "
            text   = shown + (cursor if self._type_i < len(full) + 8 else "")
            self._type_lbl.setText(text)

        elif self._state == "dashboard":
            # Start button breathing glow
            bright = blend(T['teal'], T['accent'], self._pulse_val)
            self._start_btn.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                        stop:0 {T['accent']}, stop:1 {bright});
                    color: {T['btn_fg']}; border: none;
                    border-radius: 10px; letter-spacing: 1px;
                }}
                QPushButton:hover {{
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                        stop:0 {T['teal']}, stop:1 {T['green']});
                }}
                QPushButton:pressed {{ background-color: {T['green']}; }}
            """)

        elif self._state == "session":
            # Lock banner amber border pulse
            pulsed = blend(T['amber'], T['panel'], 0.5 + 0.5 * self._pulse_val)
            self._lock_banner.setStyleSheet(
                f"background-color: {T['panel']}; border: 2px solid {pulsed};"
                f" border-radius: 12px;")
            # Status dot color oscillation
            dot_c = blend(T['green'], T['teal'], self._pulse_val)
            self._status_dot.setStyleSheet(
                f"color: {dot_c}; background: transparent;")

    def _blink_status(self):
        pass  # Status dot animation handled by _animate()

    def _fade_switch(self, state):
        if self._fade_timer and self._fade_timer.isActive():
            return
        self._fade_tgt  = state
        self._fade_step = 8
        self._fade_in   = False
        self._fade_timer = QTimer(self)
        self._fade_timer.timeout.connect(self._do_fade)
        self._fade_timer.start(18)

    def _do_fade(self):
        if not self._fade_in:
            self._fade_step -= 1
            self.setWindowOpacity(max(0.0, self._fade_step / 8))
            if self._fade_step <= 0:
                self._switch(self._fade_tgt)
                self._fade_in = True
        else:
            self._fade_step += 1
            self.setWindowOpacity(min(1.0, self._fade_step / 8))
            if self._fade_step >= 8:
                self.setWindowOpacity(1.0)
                self._fade_timer.stop()
                self._fade_timer = None

    def _roll_to(self, label, target, current=0, step=None):
        if step is None:
            step = max(1, target // 20)
        if current < target:
            current = min(current + step, target)
            label.setText(str(current))
            QTimer.singleShot(30, lambda: self._roll_to(label, target, current, step))
        else:
            label.setText(str(target))

    # ── STATE SWITCHING ────────────────────────────────────────────────────────

    def _switch(self, state):
        self._state = state
        if state == "locked":
            self._stack.setCurrentWidget(self._lock_w)
        elif state == "dashboard":
            self._stack.setCurrentWidget(self._dash_w)
            self._update_stats()
            self._refresh_preview()
        elif state == "session":
            self._stack.setCurrentWidget(self._sess_w)

    # ── USB POLLING ────────────────────────────────────────────────────────────

    def _poll_usb(self):
        dev, is_new  = detect_focus_guard_usb()
        self._usb_ok = dev is not None and not is_new
        T = self._T

        # Get the actual drive path (e.g. "E:\") — separate from the device hash
        usb_drive = get_usb_drive_path() if dev else None

        # Layer 2 file-handle lock: hold open on auth, release on removal
        if self._usb_ok and usb_drive and not self._usb_locked:
            self._usb_path   = usb_drive
            self._usb_locked = True
            new_handles = lock_usb_files(usb_drive)
            self._usb_handles.extend(new_handles)
            self._prot_btn.setVisible(True)
            # Auto-apply protection if not already active
            if not is_protected(usb_drive):
                QTimer.singleShot(700, lambda d=usb_drive: self._auto_protect_usb(d))
        elif not self._usb_ok and usb_drive is None and self._usb_locked:
            unlock_usb_files(self._usb_handles)
            self._usb_locked = False
            self._usb_path   = None
            self._prot_btn.setVisible(False)

        if self._usb_ok:
            self._usb_dot.setStyleSheet(f"color: {T['green']}; background: transparent;")
            self._usb_lbl.setStyleSheet(f"color: {T['green']}; background: transparent;")
            self._usb_lbl.setText("USB Authenticated  ✔")
        elif dev and is_new:
            self._usb_dot.setStyleSheet(f"color: {T['amber']}; background: transparent;")
            self._usb_lbl.setStyleSheet(f"color: {T['amber']}; background: transparent;")
            self._usb_lbl.setText("New USB — tap to register")
        else:
            self._usb_dot.setStyleSheet(f"color: {T['red']}; background: transparent;")
            self._usb_lbl.setStyleSheet(f"color: {T['text_mid']}; background: transparent;")
            self._usb_lbl.setText("No USB Detected")

        if self._state == "locked":
            if self._usb_ok:
                self._fade_switch("dashboard")
            elif dev and is_new and not self._ask_reg:
                self._ask_reg = True
                QTimer.singleShot(200, self._do_register)

        elif self._state == "dashboard":
            if not self._usb_ok and dev is None:
                self._fade_switch("locked")
            elif dev and is_new and not self._ask_reg:
                self._ask_reg = True
                QTimer.singleShot(200, self._do_register)

        elif self._state == "session":
            # Session cannot be stopped regardless of USB state
            self._susb.setText("🔒  Session locked\nTimer expiry is the only exit")
            self._susb.setStyleSheet(f"color: {T['amber']}; background: transparent;")

    def _do_register(self):
        reply = QMessageBox.question(
            self, "Register USB Key",
            "A new USB key has been detected.\n\n"
            "Register it as your Focus Guard authentication key?\n\n"
            "Only registered keys can unlock Focus Guard.",
            QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            dev, new = detect_focus_guard_usb()
            if dev and new:
                register_device(dev)
                usb_drive = get_usb_drive_path()
                if usb_drive:
                    protect(usb_drive)
                QMessageBox.information(self, "USB Registered & Protected  🔐",
                    "USB key registered successfully!\n\n"
                    "✅  File protection has been applied.\n"
                    "    No file on this USB can be deleted.")
        self._ask_reg = False

    def _usb_protection_dialog(self):
        """Show USB protection status and allow enabling / removing protection."""
        if not self._usb_path:
            QMessageBox.warning(self, "No USB",
                "No authenticated USB drive is currently connected.")
            return

        if is_protected(self._usb_path):
            from PySide6.QtWidgets import QInputDialog
            key, ok = QInputDialog.getText(
                self, "Remove USB Protection  🔐",
                "File protection is ACTIVE on this USB drive.\n\n"
                "Enter your protection key to remove it:\n"
                "(Format: XXXX-XXXX)",
                QLineEdit.Normal, "")
            if not ok or not key.strip():
                return
            if verify_and_unprotect(self._usb_path, key.strip()):
                QMessageBox.information(self, "Protection Removed",
                    "File protection has been removed from the USB drive.\n\n"
                    "USB files can now be modified or deleted normally.")
            else:
                QMessageBox.critical(self, "Wrong Key  ✖",
                    "The protection key you entered is incorrect.\n\n"
                    "File protection remains active.\n\n"
                    "Check the key you wrote down and try again.")
        else:
            reply = QMessageBox.question(
                self, "Apply USB Protection  🔐",
                "File protection is NOT currently active on this USB.\n\n"
                "Apply protection to prevent USB files from being\n"
                "deleted or the drive from being formatted?\n\n"
                "A new protection key will be generated — write it down!",
                QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                protect(self._usb_path)
                QMessageBox.information(self, "Protection Applied  🔐",
                    "USB drive is now write-protected.\n\n"
                    "✅  No file can be deleted or modified.")

    def _auto_protect_usb(self, dev: str):
        """Called once when an authenticated USB has no protection yet."""
        protect(dev)
        QMessageBox.information(self, "USB Drive Protected  🔐",
            "Your USB drive is now write-protected.\n\n"
            "✅  No file can be deleted, modified, or added\n"
            "    — even when Focus Guard is not running.\n\n"
            "Works on FAT32 and NTFS alike.")

    # ── DASHBOARD LOGIC ────────────────────────────────────────────────────────

    def _cat_changed_slot(self, name: str, state: bool):
        self._refresh_preview()

    def _refresh_preview(self):
        T    = self._T
        sel  = [n for n, c in self._cat_cards.items() if c.is_checked()]
        all_sites = self._selected_sites()
        uniq = [s for s in all_sites if not s.startswith("www.")]

        badge = f"{len(sel)} selected" if sel else "none selected"
        self._sel_badge.setText(badge)
        self._sel_badge.setStyleSheet(
            f"color: {T['green'] if sel else T['text_mid']};"
            f" background: {T['panel']}; border-radius: 4px; padding: 2px 8px;")

        if sel:
            icons = "  ".join(CATS[n]["icon"] for n in sel[:6])
            names = ", ".join(sel[:3]) + (f"  +{len(sel)-3}" if len(sel) > 3 else "")
            self._sum_lbl.setText(f"   {icons}    {names}")
            self._sum_lbl.setStyleSheet(f"color: {T['text']}; background: transparent;")
        else:
            self._sum_lbl.setText("   Select categories to begin")
            self._sum_lbl.setStyleSheet(f"color: {T['text_mid']}; background: transparent;")

        self._cnt_lbl.setText(f"{len(uniq)} sites")
        self._cnt_lbl.setStyleSheet(
            f"color: {T['accent'] if uniq else T['text_dim']}; background: transparent;")

        # Rebuild sites preview
        self._prev.clear()
        cur = self._prev.textCursor()
        hdr_fmt = QTextCharFormat()
        hdr_fmt.setForeground(QColor(T["teal"]))
        f_bold = QFont("Consolas", 9)
        f_bold.setBold(True)
        hdr_fmt.setFont(f_bold)
        body_fmt = QTextCharFormat()
        body_fmt.setForeground(QColor(T["text_mid"]))
        body_fmt.setFont(QFont("Consolas", 9))

        if uniq:
            for cat in sel:
                cs = [s for s in CATS[cat]["sites"] if not s.startswith("www.")]
                cur.setCharFormat(hdr_fmt)
                cur.insertText(f"── {CATS[cat]['icon']}  {cat}  ({len(cs)} sites)\n")
                cur.setCharFormat(body_fmt)
                for s in cs:
                    cur.insertText(f"    {s}\n")
                cur.insertText("\n")
            cu = [s for s in self._custom if not s.startswith("www.")]
            if cu:
                cur.setCharFormat(hdr_fmt)
                cur.insertText("── ✏️  Custom Sites\n")
                cur.setCharFormat(body_fmt)
                for s in cu:
                    cur.insertText(f"    {s}\n")
        else:
            cur.setCharFormat(body_fmt)
            cur.insertText(
                "\n    No websites selected yet.\n\n"
                "    Check one or more categories on the left panel.")

    def _selected_sites(self):
        sites = []
        for name, card in self._cat_cards.items():
            if card.is_checked():
                sites.extend(CATS[name]["sites"])
        sites.extend(self._custom)
        return list(set(sites))

    def _add_custom(self):
        raw = self._ce.text().strip().lower()
        if not raw:
            return
        clean = raw.lstrip("https://").lstrip("http://").strip("/")
        base  = clean[4:] if clean.startswith("www.") else clean
        if "." not in base:
            QMessageBox.warning(self, "Invalid Domain",
                "Enter a valid domain (e.g. example.com)")
            return
        for s in [base, f"www.{base}"]:
            if s not in self._custom:
                self._custom.append(s)
        self._ce.clear()
        n = len([s for s in self._custom if not s.startswith("www.")])
        self._clbl.setText(f"✔  {n} custom site(s) added")
        self._clbl.setStyleSheet(f"color: {self._T['green']}; background: transparent;")
        self._refresh_preview()

    def _set_dur(self, mins):
        self._dur_mins = mins
        T = self._T
        for m, btn in self._dur_btns.items():
            if m == mins:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {T['accent']}; color: #ffffff;
                        border: none; border-radius: 8px; font-weight: bold;
                        font-size: 10pt;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {T['card']}; color: {T['text']};
                        border: 1px solid {T['border']}; border-radius: 8px;
                        font-size: 10pt;
                    }}
                    QPushButton:hover {{
                        background-color: {T['panel']}; color: {T['text']};
                        border: 1px solid {T['accent']};
                    }}
                """)

    def _update_stats(self):
        try:
            with open(_cfg_path()) as f:
                cfg = json.load(f)
            today = date.today().strftime("%Y-%m-%d")
            log   = cfg.get("session_log", [])
            n = sum(1 for s in log if s.get("date") == today)
            t = sum(s.get("duration_minutes", 0) for s in log)
            h, m = divmod(t, 60)
            self._s_today.setText(f"Sessions today: {n}")
            self._s_total_lbl.setText(
                f"Total focus time: {h}h {m}m" if h else f"Total focus time: {t}m")
        except Exception:
            pass

    # ── SESSION START / STOP ───────────────────────────────────────────────────

    def _start(self):
        dev, new = detect_focus_guard_usb()
        if not dev or new:
            QMessageBox.warning(self, "USB Required",
                "Insert your registered USB key to start a session.")
            return
        sites = self._selected_sites()
        if not sites:
            QMessageBox.warning(self, "No Sites Selected",
                "Select at least one category before starting.")
            return

        dur_label = dict(DURATIONS).get(self._dur_mins, f"{self._dur_mins}m")
        reply = QMessageBox.warning(self, "⚠️  No Going Back — Read Before Continuing",
            f"You are about to start a  {dur_label}  focus session.\n\n"
            "🔒  ONCE STARTED, THIS SESSION CANNOT BE\n"
            "     STOPPED BY ANYONE — NOT EVEN WITH THE USB KEY.\n\n"
            "⏱  The timer runs on real wall-clock time.\n"
            "     Shutting down the computer does NOT pause the timer.\n"
            "     When you power on again the remaining time continues.\n\n"
            "     The ONLY way to end the session is to wait\n"
            "     for the countdown to reach zero.\n\n"
            "Do you want to proceed?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No)
        if reply != QMessageBox.Yes:
            return

        T    = self._T
        self._ses_total = self._dur_mins * 60
        uniq = [s for s in sites if not s.startswith("www.")]
        sel  = [n for n, c in self._cat_cards.items() if c.is_checked()]

        # Clear and populate info strip categories
        for i in reversed(range(self._scats_layout.count())):
            w = self._scats_layout.itemAt(i).widget()
            if w:
                w.deleteLater()
        for cat in sel:
            row = QWidget()
            row.setStyleSheet("background: transparent;")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(8)
            bar = QFrame()
            bar.setFixedSize(4, 20)
            bar.setStyleSheet(
                f"background-color: {CATS[cat]['color']}; border-radius: 2px;")
            lbl = QLabel(f"{CATS[cat]['icon']}  {cat}")
            lbl.setFont(QFont("Segoe UI", 9))
            lbl.setStyleSheet(f"color: {T['text']}; background: transparent;")
            rl.addWidget(bar)
            rl.addWidget(lbl)
            rl.addStretch()
            self._scats_layout.addWidget(row)

        self._blk_lbl.setText("0")
        self._roll_to(self._blk_lbl, len(uniq))
        self._arc.update_arc(self._ses_total, self._ses_total)

        self._session = FocusSession(
            duration_minutes=self._dur_mins,
            sites=sites,
            on_tick=lambda r: self._bridge.tick.emit(r),
            on_end=lambda: self._bridge.ended.emit(),
        )
        self._session.start()
        self._fade_switch("session")

        dur_label = dict(DURATIONS).get(self._dur_mins, f"{self._dur_mins}m")
        QMessageBox.information(self, "Session Started",
            f"🔒  {len(uniq)} websites are now blocked.\n\n"
            f"⏱  Duration: {dur_label}\n\n"
            "You can safely remove the USB key.\n"
            "The session continues even after a system restart.\n\n"
            "Re-insert USB anytime to stop the session early.")

    def _on_tick(self, remaining: int):
        total = self._ses_total
        pct   = int(100 * (1 - remaining / total)) if total else 0
        h, rest = divmod(remaining, 3600)
        m, s    = divmod(rest, 60)
        if h:
            self._timer_lbl.setText(f"{h}:{m:02d}:{s:02d}")
        else:
            self._timer_lbl.setText(f"{m:02d}:{s:02d}")
        self._arc.update_arc(remaining, total)
        self._pb.setValue(pct)
        self._pct_lbl.setText(f"{pct}%")
        self._update_tray(remaining)

    def _on_end(self):
        QTimer.singleShot(0, self._complete)

    def _complete(self):
        self._session = None
        self._update_tray()
        next_s = "dashboard" if self._usb_ok else "locked"
        self._fade_switch(next_s)
        self._tray.showMessage(
            "Focus Guard — Session Complete 🎉",
            "Your focus session is over. All websites have been unblocked.",
            QSystemTrayIcon.Information, 6000,
        )
        QMessageBox.information(self, "Session Complete  🎉",
            "Excellent work! Your focus session is complete.\n\n"
            "All websites have been unblocked.\n\n"
            "Insert your USB key to start another session.")

    def _resume_session(self, info):
        remaining = max(0, int(info["end_unix"] - time.time()))
        dur_secs  = info.get("duration_secs", remaining)
        sites     = info.get("sites", [])
        uniq      = [s for s in sites if not s.startswith("www.")]
        T         = self._T

        self._ses_total = dur_secs
        self._blk_lbl.setText(str(len(uniq)))

        for i in reversed(range(self._scats_layout.count())):
            w = self._scats_layout.itemAt(i).widget()
            if w:
                w.deleteLater()
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        rl  = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel("  🔄  Session resuming from reboot")
        lbl.setFont(QFont("Segoe UI", 9))
        lbl.setStyleSheet(f"color: {T['text']}; background: transparent;")
        rl.addWidget(lbl)
        self._scats_layout.addWidget(row)

        self._arc.update_arc(remaining, dur_secs)

        self._session = FocusSession(
            sites=sites,
            on_tick=lambda r: self._bridge.tick.emit(r),
            on_end=lambda: self._bridge.ended.emit(),
            resume_end_unix=info["end_unix"],
            resume_duration_secs=dur_secs,
        )
        self._session.start(resume=True)
        self._switch("session")
        self._update_tray(remaining)

        # Notify user that the session resumed after reboot
        m, s = divmod(remaining, 60)
        h, m = divmod(m, 60)
        time_str = f"{h}h {m:02d}m" if h else f"{m}m {s:02d}s"
        QTimer.singleShot(1500, lambda: self._tray.showMessage(
            "🔒 Focus Guard — Session Still Running",
            f"Your focus session resumed after reboot.\n{time_str} remaining.",
            QSystemTrayIcon.Warning, 8000,
        ))

    # ── SYSTEM TRAY ────────────────────────────────────────────────────────────

    def _setup_tray(self):
        icon = self._tray_icon_normal()
        self._tray = QSystemTrayIcon(icon, self)
        self._tray.setToolTip("Focus Guard — No active session")
        self._tray.activated.connect(self._tray_activated)
        self._tray_menu = QMenu()
        self._tray_status_action = self._tray_menu.addAction("No active session")
        self._tray_status_action.setEnabled(False)
        self._tray_menu.addSeparator()
        show_action = self._tray_menu.addAction("Show Window")
        show_action.triggered.connect(self._tray_show_window)
        self._tray_exit_action = self._tray_menu.addAction("Exit")
        self._tray_exit_action.triggered.connect(QApplication.quit)
        self._tray.setContextMenu(self._tray_menu)
        self._tray.show()

    def _tray_icon_normal(self) -> QIcon:
        px = self._logo_px.get(44)
        if px:
            return QIcon(px)
        # Fallback: draw a blue shield icon
        img = QPixmap(44, 44)
        img.fill(Qt.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QBrush(QColor(DARK["accent"])))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(4, 4, 36, 36, 8, 8)
        p.setPen(QPen(QColor("#ffffff"), 2))
        p.setFont(QFont("Segoe UI Emoji", 18))
        p.drawText(img.rect(), Qt.AlignCenter, "🛡")
        p.end()
        return QIcon(img)

    def _tray_icon_active(self) -> QIcon:
        """Red padlock icon shown during an active session."""
        img = QPixmap(44, 44)
        img.fill(Qt.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QBrush(QColor(DARK["red"])))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(4, 4, 36, 36, 8, 8)
        p.setPen(QPen(QColor("#ffffff"), 2))
        p.setFont(QFont("Segoe UI Emoji", 18))
        p.drawText(img.rect(), Qt.AlignCenter, "🔒")
        p.end()
        return QIcon(img)

    def _tray_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self._tray_show_window()

    def _tray_show_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _update_tray(self, remaining: int = -1):
        """Refresh tray icon, tooltip and context-menu based on session state."""
        if self._session and self._session.active:
            self._tray.setIcon(self._tray_icon_active())
            if remaining >= 0:
                m, s = divmod(remaining, 60)
                h, m = divmod(m, 60)
                if h:
                    time_str = f"{h}h {m:02d}m {s:02d}s remaining"
                else:
                    time_str = f"{m:02d}m {s:02d}s remaining"
                self._tray.setToolTip(f"🔒 Focus Guard — Session active\n{time_str}")
                self._tray_status_action.setText(f"🔒  Session active — {time_str}")
            self._tray_exit_action.setVisible(False)
        else:
            self._tray.setIcon(self._tray_icon_normal())
            self._tray.setToolTip("Focus Guard — No active session")
            self._tray_status_action.setText("No active session")
            self._tray_exit_action.setVisible(True)

    # ── CLOSE ──────────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        if self._session and self._session.active:
            QMessageBox.warning(self, "🔒  Session Active — Cannot Close",
                "A focus session is currently running.\n\n"
                "This window cannot be closed until the timer expires.\n\n"
                "The session will end automatically when the countdown\n"
                "reaches zero.")
            event.ignore()
            return
        unlock_usb_files(self._usb_handles)
        event.accept()
