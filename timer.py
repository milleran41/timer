import sys
import os
import json
import math
import time
import numpy as np
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import (Qt, QTimer, QPropertyAnimation, QEasingCurve,
                          QRect, QRectF, QPointF, pyqtProperty, QUrl)
from PyQt6.QtGui import (QPainter, QColor, QPen, QFont, QFontMetricsF,
                         QPainterPath, QPolygonF, QMouseEvent, QDesktopServices)
import pygame


# ── Audio ──────────────────────────────────────────────────────────────────
try:
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
    AUDIO_OK = True
except Exception:
    AUDIO_OK = False


def make_beep(freq=880, duration=0.12, volume=0.3):
    """Creates a sound matching the real audio device parameters.
    On any problem returns None, so the app simply runs without sound."""
    if not AUDIO_OK:
        return None
    try:
        sample_rate, fmt, channels = pygame.mixer.get_init()
        if fmt != -16:
            return None
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        wave = np.sin(2 * np.pi * freq * t) * volume * 32767
        wave = (wave * np.linspace(1, 0, len(wave))).astype(np.int16)
        if channels > 1:
            wave = np.ascontiguousarray(np.column_stack([wave] * channels))
        return pygame.sndarray.make_sound(wave)
    except Exception:
        return None


TICK_SOUND = make_beep(880, 0.12, 0.25)
FINAL_BEEP1 = make_beep(660, 0.35, 0.4)
FINAL_BEEP2 = make_beep(880, 0.6, 0.45)


def _play(sound):
    if sound is not None:
        sound.play()


def play_tick():
    _play(TICK_SOUND)


def play_final():
    _play(FINAL_BEEP1)
    QTimer.singleShot(450, lambda: _play(FINAL_BEEP1))
    QTimer.singleShot(900, lambda: _play(FINAL_BEEP2))


# ── Colors ────────────────────────────────────────────────────────────────────
# Strict palette: black, white, yellow and the app's existing red.
# Every other value below is one of those four, optionally with transparency.
BLACK = QColor(0, 0, 0)
WHITE = QColor(255, 255, 255)
YELLOW = QColor('#ffd21e')
RED = QColor('#ff5252')

BG_NORMAL = QColor(0, 0, 0, 205)     # translucent black
BG_WARN = QColor(0, 0, 0, 218)
BG_FINISHED = QColor(0, 0, 0, 230)

SIZE_SMALL = 160    # normal mode
SIZE_WARNING = 300  # last 10 seconds


# ── Microsoft Store rating ────────────────────────────────────────────────────
# Product ID of the published Store listing (the "9N..." value from Partner
# Center). While it is empty the thumbs-up button only thanks the user, which
# is better than opening a broken Store link before the app is published.
STORE_PRODUCT_ID = '9MWTDPLL3C5M'

FEEDBACK_AFTER_FIRST = 3    # finished sessions before the very first ask
FEEDBACK_EVERY = 5          # finished sessions between later asks
FEEDBACK_MAX_PROMPTS = 3    # total asks per install, so nobody gets nagged


def store_review_url():
    """Store review link, or '' while the listing has no product id yet."""
    if not STORE_PRODUCT_ID:
        return ''
    return f'ms-windows-store://review/?ProductId={STORE_PRODUCT_ID}'


def open_store_review():
    """Opens the Microsoft Store rating dialog for this app."""
    url = store_review_url()
    if not url:
        return False
    return QDesktopServices.openUrl(QUrl(url))


def _settings_path():
    """Per-user settings file: %LOCALAPPDATA%\\TimerApp\\settings.json."""
    if os.name == 'nt':
        base = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
    else:
        base = os.environ.get('XDG_CONFIG_HOME') or os.path.join(
            os.path.expanduser('~'), '.config')
    return os.path.join(base, 'TimerApp', 'settings.json')


class FeedbackTracker:
    """Counts finished sessions and decides whether the rating card may show.

    State is a small JSON file (%LOCALAPPDATA%\\TimerApp\\settings.json) rather
    than the registry: an MSIX package virtualises the registry, while a plain
    file survives that and can be inspected or deleted by hand. The user is
    asked only after a few completed sessions, at most FEEDBACK_MAX_PROMPTS
    times, and never again after a thumbs-up, a thumbs-down or 'Don't ask again'.
    """

    def __init__(self, path=None):
        self.path = path or _settings_path()
        self.data = self._load()

    # ── file storage ──
    def _load(self):
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def _save(self):
        """Writes atomically; a read-only folder must not break the app."""
        try:
            folder = os.path.dirname(self.path)
            if folder:
                os.makedirs(folder, exist_ok=True)
            tmp = self.path + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2)
            os.replace(tmp, self.path)
        except OSError:
            pass

    def _int(self, key, default=0):
        try:
            return int(self.data.get(key, default) or default)
        except (TypeError, ValueError):
            return default

    # ── state ──
    @property
    def sessions(self):
        return self._int('sessions')

    @property
    def prompts(self):
        return self._int('prompts')

    @property
    def next_at(self):
        return self._int('next_at', FEEDBACK_AFTER_FIRST)

    @property
    def rated(self):
        return bool(self.data.get('rated', False))

    @property
    def dismissed(self):
        return bool(self.data.get('dismissed', False))

    def record_completion(self):
        self.data['sessions'] = self.sessions + 1
        self._save()

    def should_prompt(self):
        if self.rated or self.dismissed:
            return False
        if self.prompts >= FEEDBACK_MAX_PROMPTS:
            return False
        return self.sessions >= self.next_at

    def mark_shown(self):
        self.data['prompts'] = self.prompts + 1
        self._save()

    def mark_later(self):
        """'Not now' / X: stay quiet for a few more finished sessions."""
        self.data['next_at'] = self.sessions + FEEDBACK_EVERY
        self._save()

    def mark_rated(self):
        self.data['rated'] = True
        self._save()

    def mark_dismissed(self):
        self.data['dismissed'] = True
        self._save()


def place_below(win, anchor, gap=10):
    """Puts a popup right below the clock (above it if there is no room)."""
    win.adjustSize()
    dw, dh = win.width(), win.height()
    geo = anchor.frameGeometry()
    screen = QApplication.screenAt(geo.center()) or QApplication.primaryScreen()
    area = screen.availableGeometry()
    x = geo.center().x() - dw // 2
    y = geo.bottom() + gap
    if y + dh > area.bottom():
        y = geo.top() - dh - gap
    x = max(area.left() + gap, min(x, area.right() - dw - gap))
    y = max(area.top() + gap, y)
    win.move(x, y)


class FeedbackCard(QWidget):
    """Small 'rate the app' card, drawn in the same four-colour palette.

    Deliberately not modal and not a system dialog: it appears beside the
    clock, closes with the X or 'Not now', and 'Don't ask again' silences it
    for good.
    """

    W, H = 292, 184

    def __init__(self, clock, tracker):
        super().__init__(clock)
        self.tracker = tracker
        self._thanks = ''

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint |
                            Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(self.W, self.H)

    # ── geometry (shared by paint and hit testing) ──
    def _geo(self):
        r = 21
        up = QRectF(22, 82, 2 * r, 2 * r)
        down = QRectF(22 + 2 * r + 12, 82, 2 * r, 2 * r)
        pill_x = down.right() + 14
        not_now = QRectF(pill_x, 88, self.W - pill_x - 22, 32)
        later = QRectF(22, self.H - 33, self.W - 44, 18)
        close = QRectF(self.W - 36, 10, 24, 24)
        return up, down, not_now, later, close

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        body = QRectF(3, 3, self.W - 6, self.H - 6)

        # soft black shadow, yellow rim: readable on any wallpaper
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 110))
        p.drawRoundedRect(body.translated(3, 4), 16, 16)
        p.setBrush(QColor(0, 0, 0, 237))
        p.setPen(QPen(YELLOW, 2))
        p.drawRoundedRect(body, 16, 16)

        up, down, not_now, later, close = self._geo()

        if self._thanks:
            f = QFont('Arial')
            f.setPixelSize(12)
            f.setWeight(QFont.Weight.Bold)
            p.setFont(f)
            p.setPen(WHITE)
            p.drawText(body, Qt.AlignmentFlag.AlignCenter, self._thanks)
            return

        f = QFont('Arial')
        f.setPixelSize(14)
        f.setWeight(QFont.Weight.Bold)
        p.setFont(f)
        p.setPen(WHITE)
        p.drawText(QRectF(22, 18, 232, 22),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   'Enjoying the timer?')

        f = QFont('Arial')
        f.setPixelSize(11)
        p.setFont(f)
        p.setPen(QColor(255, 255, 255, 185))
        p.drawText(QRectF(22, 42, 250, 18),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   'A quick rating helps a lot.')

        # close X
        p.setPen(QPen(QColor(255, 255, 255, 205), 1.8))
        c = close.center()
        k = 4.5
        p.drawLine(QPointF(c.x() - k, c.y() - k), QPointF(c.x() + k, c.y() + k))
        p.drawLine(QPointF(c.x() - k, c.y() + k), QPointF(c.x() + k, c.y() - k))

        # thumbs
        for rect, fill, thumb_up in ((up, YELLOW, True), (down, WHITE, False)):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(fill)
            p.drawEllipse(rect)
            p.setPen(QPen(BLACK, 1.6))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(rect)
            self._thumb(p, rect, thumb_up, fill)

        # 'Not now'
        p.setPen(QPen(WHITE, 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(not_now, not_now.height() / 2, not_now.height() / 2)
        f = QFont('Arial')
        f.setPixelSize(12)
        f.setWeight(QFont.Weight.Bold)
        p.setFont(f)
        p.setPen(WHITE)
        p.drawText(not_now, Qt.AlignmentFlag.AlignCenter, 'Not now')

        # permanent opt-out
        f = QFont('Arial')
        f.setPixelSize(10)
        p.setFont(f)
        p.setPen(YELLOW)
        p.drawText(later, Qt.AlignmentFlag.AlignCenter, "Don't ask again")

    def _thumb(self, p, rect, thumb_up, fill):
        """Hand pictogram: palm, wrist, raised thumb and finger gaps.

        Drawn in a 24-unit box and scaled to the button, then mirrored
        vertically for the thumbs-down button.
        """
        s = rect.width() / 29.0
        p.save()
        p.translate(rect.center())
        p.scale(s, -s if not thumb_up else s)
        p.translate(-10.2, -11.8)

        path = QPainterPath()
        # wrist
        path.addRoundedRect(QRectF(1.4, 9.0, 4.2, 12.0), 1.2, 1.2)
        # palm with folded fingers
        path.addRoundedRect(QRectF(6.2, 9.0, 12.0, 12.0), 2.4, 2.4)
        # raised thumb
        thumb = QPainterPath()
        thumb.moveTo(7.2, 9.0)
        thumb.lineTo(9.0, 4.2)
        thumb.quadTo(9.6, 2.0, 11.6, 2.5)
        thumb.quadTo(13.5, 3.0, 13.0, 5.2)
        thumb.lineTo(12.3, 9.0)
        thumb.closeSubpath()
        path.addPath(thumb)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(BLACK)
        p.drawPath(path)

        # finger gaps, drawn in the button colour
        gap = QPen(fill, 1.6)
        gap.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(gap)
        p.drawLine(QPointF(10.0, 13.0), QPointF(16.8, 13.0))
        p.drawLine(QPointF(10.0, 16.8), QPointF(16.8, 16.8))
        p.restore()

    # ── actions ──
    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position()
        up, down, not_now, later, close = self._geo()
        if not self._thanks:
            if up.contains(pos):
                self._thumbs_up()
                return
            if down.contains(pos):
                self._thumbs_down()
                return
            if later.contains(pos):
                self.tracker.mark_dismissed()
                self.close()
                return
            if not_now.contains(pos) or close.contains(pos):
                self.tracker.mark_later()
                self.close()
                return
        if close.contains(pos):
            self.close()

    def _thanks_and_close(self, text):
        self._thanks = text
        self.update()
        QTimer.singleShot(2400, self.close)

    def _thumbs_up(self):
        self.tracker.mark_rated()
        opened = open_store_review()
        self._thanks_and_close('Thanks! Please rate us in the Store.' if opened
                               else 'Thanks! Glad you like it.')

    def _thumbs_down(self):
        self.tracker.mark_dismissed()
        self._thanks_and_close('Thanks! We will keep improving.')


# ── Main widget ─────────────────────────────────────────────────────────
class TimerWindow(QWidget):

    # --- animation properties ---
    def _get_appear(self): return self._appear
    def _set_appear(self, v): self._appear = v; self.update()
    appear = pyqtProperty(float, _get_appear, _set_appear)

    def _get_warn_mix(self): return self._warn_mix
    def _set_warn_mix(self, v): self._warn_mix = v; self.update()
    warn_mix = pyqtProperty(float, _get_warn_mix, _set_warn_mix)

    def _get_flip_t(self): return self._flip_t
    def _set_flip_t(self, v): self._flip_t = v; self.update()
    flip_t = pyqtProperty(float, _get_flip_t, _set_flip_t)

    def _get_wave_t(self): return self._wave_t
    def _set_wave_t(self, v): self._wave_t = v; self.update()
    wave_t = pyqtProperty(float, _get_wave_t, _set_wave_t)

    def __init__(self):
        super().__init__()

        self.total_seconds = 60
        self.remaining = 60
        self.running = False
        self.paused = False
        self.warning_mode = False
        self.finished = False
        self.drag_pos = None
        self._btn_centers = []

        self._appear = 0.0
        self._warn_mix = 0.0
        self._flip_t = 1.0
        self._wave_t = 1.0
        self._cur_str = self._fmt(self.remaining)
        self._prev_str = self._cur_str
        self._allow_close = False
        self._shown_once = False

        self.feedback = FeedbackTracker()
        self._feedback_card = None

        self._setup_window()
        self._setup_animations()

        self.qtimer = QTimer(self)
        self.qtimer.setInterval(1000)
        self.qtimer.timeout.connect(self._tick)

        # frame timer for the "breathing" effect (runs only when needed)
        self.frame_timer = QTimer(self)
        self.frame_timer.setInterval(16)
        self.frame_timer.timeout.connect(self._frame)

    # ── Window ──
    def _setup_window(self):
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint |
                            Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(SIZE_SMALL, SIZE_SMALL)
        self.setMaximumSize(SIZE_WARNING, SIZE_WARNING)
        self.resize(SIZE_SMALL, SIZE_SMALL)
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.right() - SIZE_SMALL - 20, 20)

    def _anim(self, prop, duration, curve=QEasingCurve.Type.Linear):
        a = QPropertyAnimation(self, prop)
        a.setDuration(duration)
        a.setEasingCurve(curve)
        return a

    def _setup_animations(self):
        self.anim_appear = self._anim(b'appear', 450, QEasingCurve.Type.OutBack)
        self.anim_close = self._anim(b'appear', 260, QEasingCurve.Type.InCubic)
        self.anim_close.finished.connect(self._finish_close)
        self.anim_warn = self._anim(b'warn_mix', 700, QEasingCurve.Type.InOutQuad)
        self.anim_flip = self._anim(b'flip_t', 300, QEasingCurve.Type.OutCubic)
        self.anim_wave = self._anim(b'wave_t', 2200, QEasingCurve.Type.OutQuad)
        self.anim_geom = self._anim(b'geometry', 380, QEasingCurve.Type.OutCubic)

    def _run(self, anim, start, end):
        anim.stop()
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.start()

    # ── Show / close ──
    def showEvent(self, event):
        super().showEvent(event)
        if not self._shown_once:
            self._shown_once = True
            self._appear = 0.0
            self._run(self.anim_appear, 0.0, 1.0)

    def closeEvent(self, event):
        if self._allow_close:
            event.accept()
            return
        event.ignore()
        if self.anim_close.state() == QPropertyAnimation.State.Running:
            return
        self.qtimer.stop()
        self._run(self.anim_close, self._appear, 0.0)

    def _finish_close(self):
        self._allow_close = True
        self.close()
        QApplication.quit()

    # ── Window resize (animated) ──
    def _resize_to(self, size):
        cur = self.geometry()
        rect = QRect(0, 0, size, size)
        rect.moveCenter(cur.center())
        screen = QApplication.primaryScreen().availableGeometry()
        if rect.right() > screen.right() - 10:
            rect.moveRight(screen.right() - 10)
        if rect.left() < screen.left() + 10:
            rect.moveLeft(screen.left() + 10)
        if rect.bottom() > screen.bottom() - 10:
            rect.moveBottom(screen.bottom() - 10)
        if rect.top() < screen.top() + 10:
            rect.moveTop(screen.top() + 10)
        self._run(self.anim_geom, self.geometry(), rect)

    # ── Frames ──
    def _needs_frames(self):
        return self.finished or (self.warning_mode and self.running)

    def _ensure_frames(self):
        if not self.frame_timer.isActive():
            self.frame_timer.start()

    def _frame(self):
        self.update()
        if not self._needs_frames():
            self.frame_timer.stop()

    # ── Time text and digit flip ──
    @staticmethod
    def _fmt(secs):
        h = secs // 3600
        m = (secs % 3600) // 60
        s = secs % 60
        if h > 0:
            return f'{h:02d}:{m:02d}:{s:02d}'
        return f'{m:02d}:{s:02d}'

    def _set_text(self, new, animate):
        if new == self._cur_str:
            return
        if animate and len(new) == len(self._cur_str):
            self._prev_str = self._cur_str
            self._cur_str = new
            self._run(self.anim_flip, 0.0, 1.0)
        else:
            self.anim_flip.stop()
            self._prev_str = self._cur_str = new
            self._flip_t = 1.0
        self.update()

    # ── Warning mode ──
    def _enter_warning(self):
        self.warning_mode = True
        self._run(self.anim_warn, self._warn_mix, 1.0)
        self._resize_to(SIZE_WARNING)
        self._ensure_frames()

    def _leave_warning(self):
        self.warning_mode = False
        self._run(self.anim_warn, self._warn_mix, 0.0)
        self._resize_to(SIZE_SMALL)

    # ── Timer logic ──
    def _tick(self):
        self.remaining -= 1
        self._set_text(self._fmt(max(self.remaining, 0)), animate=True)

        if 0 < self.remaining <= 10:
            if not self.warning_mode:
                self._enter_warning()
            play_tick()

        if self.remaining <= 0:
            self.remaining = 0
            self.running = False
            self.qtimer.stop()
            self.finished = True
            if not self.warning_mode:
                self._enter_warning()
            play_final()
            self._run(self.anim_wave, 0.0, 1.0)
            self._ensure_frames()
            # a session really finished -> the only moment we may ask for a rating
            self.feedback.record_completion()
            QTimer.singleShot(1600, self._maybe_ask_feedback)

        self.update()

    # ── Store rating card ──
    def _maybe_ask_feedback(self):
        """Shows the rating card, but only after a few finished sessions."""
        if not self.feedback.should_prompt():
            return
        if self._feedback_card is not None and self._feedback_card.isVisible():
            return
        self.feedback.mark_shown()
        if self._feedback_card is not None:
            self._feedback_card.deleteLater()
        card = FeedbackCard(self, self.feedback)
        place_below(card, self)
        card.show()
        self._feedback_card = card

    def start(self):
        if self.finished or self.remaining <= 0:
            self.reset()
        if not self.running and not self.paused:
            self.total_seconds = self.remaining
        self.running = True
        self.paused = False
        self.qtimer.start()
        if self.remaining <= 10 and not self.warning_mode:
            self._enter_warning()
        self._ensure_frames()
        self.update()

    def pause(self):
        self.running = False
        self.paused = True
        self.qtimer.stop()
        self.update()

    def reset(self):
        self.qtimer.stop()
        self.running = False
        self.paused = False
        self.finished = False
        self.anim_wave.stop()
        self._wave_t = 1.0
        self.remaining = self.total_seconds
        self._set_text(self._fmt(self.remaining), animate=False)
        if self.warning_mode or self._warn_mix > 0:
            self._leave_warning()
        self.update()

    def _apply_new_time(self, total):
        self.qtimer.stop()
        self.running = False
        self.paused = False
        self.total_seconds = self.remaining = total
        self.finished = False
        self.anim_wave.stop()
        self._wave_t = 1.0
        self._set_text(self._fmt(total), animate=False)
        if self.warning_mode or self._warn_mix > 0:
            self._leave_warning()
        self.update()

    # ── Painting ──────────────────────────────────────────────────────────
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2

        # show animation: opacity + scale
        a = self._appear
        p.setOpacity(max(0.0, min(1.0, a)))
        s = 0.6 + 0.4 * a
        p.translate(cx, cy)
        p.scale(s, s)
        p.translate(-cx, -cy)

        mix = self._warn_mix
        breath = 0.5 + 0.5 * math.sin(time.monotonic() * 2 * math.pi * 0.9)
        b = breath if mix > 0.01 else 0.0
        # hard switch instead of a colour blend, so only the four palette
        # colours are ever on screen
        base_color = RED if mix > 0.5 else YELLOW

        # hard black shadow under the whole dial: the clock keeps its
        # contour on a light background too
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 120))
        p.drawEllipse(QPointF(cx + w * 0.012, cy + w * 0.018), w * 0.47, h * 0.47)

        # background
        bg = BG_FINISHED if self.finished else (BG_WARN if mix > 0.5 else BG_NORMAL)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg)
        p.drawEllipse(QPointF(cx, cy), w * 0.47, h * 0.47)

        # flash at the end
        if self._wave_t < 1.0:
            flash = max(0.0, 1.0 - self._wave_t * 5) * 150
            if flash > 0:
                p.setBrush(QColor(255, 255, 255, int(flash)))
                p.drawEllipse(QPointF(cx, cy), w * 0.47, h * 0.47)

        # progress ring
        m = w * 0.12
        ring = QRectF(m, m, w - 2 * m, h - 2 * m)
        fraction = self.remaining / self.total_seconds if self.total_seconds > 0 else 0
        width = w * 0.055 * (1 + 0.12 * b * mix)

        p.setBrush(Qt.BrushStyle.NoBrush)

        # thin yellow rim framing the clock
        off = width * 1.05
        rim = QRectF(ring.left() - off, ring.top() - off,
                     ring.width() + 2 * off, ring.height() + 2 * off)
        # black backing under the yellow rim -> crisp frame on any background
        back_pen = QPen(QColor(0, 0, 0, 210), max(1.2, width * 0.14) * 2.6)
        back_pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        p.setPen(back_pen)
        p.drawEllipse(rim)

        rim_pen = QPen(YELLOW, max(1.2, width * 0.14))
        rim_pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        p.setPen(rim_pen)
        p.drawEllipse(rim)

        # white track
        pen_bg = QPen(QColor(255, 255, 255, 60), width)
        pen_bg.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen_bg)
        p.drawArc(ring, 0, 360 * 16)

        if fraction > 0:
            span = int(fraction * 360 * 16)
            # black gap that separates the coloured arc from the white track
            sep = QPen(QColor(0, 0, 0, 230), width * 1.30)
            sep.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(sep)
            p.drawArc(ring, 90 * 16, -span)

            if mix > 0.05:   # ring glow while the clock is expiring
                for mult, base_a in ((2.6, 0.10), (1.8, 0.18)):
                    gc = QColor(base_color)
                    gc.setAlpha(int(255 * base_a * (0.4 + 0.6 * b) * mix))
                    gp = QPen(gc, width * mult)
                    gp.setCapStyle(Qt.PenCapStyle.RoundCap)
                    p.setPen(gp)
                    p.drawArc(ring, 90 * 16, -span)
            pen_fg = QPen(base_color, width)
            pen_fg.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen_fg)
            p.drawArc(ring, 90 * 16, -span)

        # waves from the center
        if self._wave_t < 1.0:
            for k in range(3):
                t = self._wave_t * 1.6 - k * 0.3
                if 0 < t < 1:
                    r = w * 0.38 + t * w * 0.14
                    wc = QColor(RED)
                    wc.setAlpha(int(((1 - t) ** 1.2) * 200))
                    p.setPen(QPen(wc, w * 0.03 * (1 - t) + 1.5))
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawEllipse(QPointF(cx, cy), r, r)

        # caption
        if mix > 0.05 or self.finished:
            sub = "Time's up!" if self.finished else 'Remaining'
            f = QFont('Arial')
            f.setPixelSize(max(8, int(w * 0.065)))
            p.setFont(f)
            p.setPen(QColor(255, 255, 255, int(215 * max(mix, 0.0))))
            p.drawText(QRectF(0, cy - h * 0.36, w, h * 0.14),
                       Qt.AlignmentFlag.AlignCenter, sub)

        # digits
        text_color = RED if (self.finished or mix > 0.5) else WHITE
        glow = (0.35 + 0.65 * b) * mix
        self._draw_time(p, cx, cy - h * 0.06, w, text_color, glow)

        # buttons
        self._draw_buttons(p, w, h)

    def _draw_time(self, p, cx, text_cy, w, color, glow):
        text = self._cur_str
        px = w * (0.20 if len(text) <= 5 else 0.135)
        font = QFont('Arial')
        font.setPixelSize(max(8, int(px)))
        font.setWeight(QFont.Weight.Bold)
        fm = QFontMetricsF(font)
        cap_h = fm.capHeight()
        digit_w = fm.horizontalAdvance('0')
        colon_w = fm.horizontalAdvance(':')
        widths = [colon_w if ch == ':' else digit_w for ch in text]
        x = cx - sum(widths) / 2

        t = self._flip_t
        same_len = len(self._prev_str) == len(text)

        for i, ch in enumerate(text):
            cell = widths[i]
            ccx = x + cell / 2
            x += cell
            prev = self._prev_str[i] if same_len else ch
            draw_ch, sy = ch, 1.0
            if prev != ch and t < 1.0:
                if t < 0.5:
                    draw_ch, sy = prev, 1 - 2 * t
                else:
                    draw_ch, sy = ch, 2 * (t - 0.5)
            sy = max(sy, 0.02)

            path = QPainterPath()
            path.addText(0, 0, font, draw_ch)
            adv = fm.horizontalAdvance(draw_ch)

            p.save()
            p.translate(ccx, text_cy)
            p.scale(1.0, sy)
            p.translate(-adv / 2, cap_h / 2)
            if glow > 0.01:
                for wmul, al in ((9, 18), (5, 32), (2.5, 55)):
                    gc = QColor(RED)
                    gc.setAlpha(int(al * glow))
                    gp = QPen(gc, wmul * w / 160)
                    gp.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                    p.strokePath(path, gp)

            # hard black drop shadow: depth, reads on the lightest background
            p.save()
            p.translate(px * 0.05, px * 0.06)
            p.fillPath(path, QColor(0, 0, 0, 170))
            p.restore()

            # wide black halo -> the main contrast contour
            halo = QPen(QColor(0, 0, 0, 235), px * 0.13)
            halo.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.strokePath(path, halo)

            # yellow accent contour on top of the halo
            accent = QPen(YELLOW, px * 0.075)
            accent.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.strokePath(path, accent)

            # thin black keyline between the yellow rim and the glyph itself
            keyline = QPen(BLACK, px * 0.025)
            keyline.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.strokePath(path, keyline)

            p.fillPath(path, color)
            p.restore()

    def _draw_buttons(self, p, w, h):
        r = w * 0.07
        y = h / 2 + h * 0.23
        spacing = w * 0.20
        xs = [w / 2 - spacing, w / 2, w / 2 + spacing]
        fills = [YELLOW, WHITE, RED]      # play/pause, reset, close
        icons = [BLACK, BLACK, WHITE]
        self._btn_centers = []

        for i, (bx, fill) in enumerate(zip(xs, fills)):
            self._btn_centers.append((bx, y, r))
            icon_color = QColor(icons[i])
            icon_pen = QPen(icon_color, max(1.5, r * 0.18))
            icon_pen.setCapStyle(Qt.PenCapStyle.RoundCap)

            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(fill)
            p.drawEllipse(QPointF(bx, y), r, r)

            # black keyline keeps the button readable on top of the ring
            p.setPen(QPen(BLACK, max(1.4, r * 0.16)))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(bx, y), r, r)

            p.setPen(icon_pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            k = r * 0.45
            if i == 0 and not self.running:      # play
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(icon_color)
                p.drawPolygon(QPolygonF([QPointF(bx - k * 0.6, y - k),
                                         QPointF(bx - k * 0.6, y + k),
                                         QPointF(bx + k, y)]))
            elif i == 0:                          # pause
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(icon_color)
                p.drawRect(QRectF(bx - k * 0.9, y - k, k * 0.65, k * 2))
                p.drawRect(QRectF(bx + k * 0.25, y - k, k * 0.65, k * 2))
            elif i == 1:                          # reset
                rr = k * 1.05
                p.drawArc(QRectF(bx - rr, y - rr, 2 * rr, 2 * rr), 40 * 16, 280 * 16)
                th = math.radians(320)
                pt = QPointF(bx + rr * math.cos(th), y - rr * math.sin(th))
                tx, ty = -math.sin(th), -math.cos(th)
                nx, ny = -ty, tx
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(icon_color)
                p.drawPolygon(QPolygonF([
                    QPointF(pt.x() + tx * rr * 0.7, pt.y() + ty * rr * 0.7),
                    QPointF(pt.x() + nx * rr * 0.5, pt.y() + ny * rr * 0.5),
                    QPointF(pt.x() - nx * rr * 0.5, pt.y() - ny * rr * 0.5)]))
            else:                                 # close
                p.drawLine(QPointF(bx - k * 0.8, y - k * 0.8), QPointF(bx + k * 0.8, y + k * 0.8))
                p.drawLine(QPointF(bx - k * 0.8, y + k * 0.8), QPointF(bx + k * 0.8, y - k * 0.8))

    # ── Set time by double click ────────────────────────────────────────
    def mouseDoubleClickEvent(self, event):
        if not self.running:
            self._show_input_dialog()

    def _show_input_dialog(self):
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                                     QSpinBox, QLabel, QPushButton)
        dlg = QDialog(self)
        dlg.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        dlg.setWindowTitle('Set time')
        dlg.setStyleSheet('''
            QDialog { background: #000000; color: #ffffff; }
            QLabel  { color: #ffffff; font-size: 14px; }
            QSpinBox {
                background: #000000; color: #ffffff;
                border: 1px solid #ffd21e; border-radius: 6px;
                padding: 4px; font-size: 18px; width: 60px;
            }
            QPushButton {
                background: #ffd21e; color: #000000; border: none;
                border-radius: 8px; padding: 8px 20px;
                font-size: 14px; font-weight: bold;
            }
            QPushButton:hover { background: #ffffff; }
            QPushButton#cancel { background: #ffffff; color: #000000; }
        ''')
        lay = QVBoxLayout(dlg)
        lay.setSpacing(12)
        lay.addWidget(QLabel('Set the countdown time:'))

        row = QHBoxLayout()
        h_spin = QSpinBox(); h_spin.setRange(0, 23)
        h_spin.setValue(self.total_seconds // 3600)
        m_spin = QSpinBox(); m_spin.setRange(0, 59)
        m_spin.setValue((self.total_seconds % 3600) // 60)
        s_spin = QSpinBox(); s_spin.setRange(0, 59)
        s_spin.setValue(self.total_seconds % 60)
        for spin, lbl in ((h_spin, 'h'), (m_spin, 'm'), (s_spin, 's')):
            row.addWidget(spin)
            row.addWidget(QLabel(lbl))
        lay.addLayout(row)

        btns = QHBoxLayout()
        ok_btn = QPushButton('OK')
        can_btn = QPushButton('Cancel')
        can_btn.setObjectName('cancel')
        btns.addWidget(ok_btn)
        btns.addWidget(can_btn)
        lay.addLayout(btns)
        ok_btn.clicked.connect(dlg.accept)
        can_btn.clicked.connect(dlg.reject)

        self._place_dialog_below(dlg)

        if dlg.exec():
            total = h_spin.value() * 3600 + m_spin.value() * 60 + s_spin.value()
            if total > 0:
                self._apply_new_time(total)
                self.start()

    def _place_dialog_below(self, dlg):
        """Put the dialog right below the clock (above it if there is no room)."""
        place_below(dlg, self)

    # ── Mouse ───────────────────────────────────────────────────────────────
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            for i, (bx, by, r) in enumerate(self._btn_centers):
                dx, dy = pos.x() - bx, pos.y() - by
                if dx * dx + dy * dy <= r * r:
                    self._handle_btn(i)
                    return
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.drag_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            self.anim_geom.stop()
            self.move(event.globalPosition().toPoint() - self.drag_pos)

    def mouseReleaseEvent(self, event):
        self.drag_pos = None

    def _handle_btn(self, idx):
        if idx == 0:
            self.pause() if self.running else self.start()
        elif idx == 1:
            self.reset()
        elif idx == 2:
            self.close()

    def wheelEvent(self, event):
        if not self.running:
            delta = 60 if event.angleDelta().y() > 0 else -60
            self._apply_new_time(max(1, self.total_seconds + delta))


if __name__ == '__main__':
    app = QApplication(sys.argv)
    # The clock is a Qt.Tool window, so Qt would quit as soon as any dialog closes.
    # Quitting is done explicitly by the close button instead.
    app.setQuitOnLastWindowClosed(False)
    win = TimerWindow()
    win.show()
    sys.exit(app.exec())
