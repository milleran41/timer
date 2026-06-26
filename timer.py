import sys
import math
import numpy as np
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import (Qt, QTimer, QPropertyAnimation, QEasingCurve,
                           QRect, pyqtProperty, QPoint)
from PyQt6.QtGui import (QPainter, QColor, QPen, QFont, QFontMetrics,
                          QLinearGradient, QMouseEvent)
import pygame


# ── Аудио ──────────────────────────────────────────────────────────────────
pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)

def make_beep(freq=880, duration=0.12, volume=0.3, sample_rate=44100):
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    wave = (np.sin(2 * np.pi * freq * t) * volume * 32767).astype(np.int16)
    # затухание
    fade = np.linspace(1, 0, len(wave))
    wave = (wave * fade).astype(np.int16)
    # создать стерео массив
    stereo_wave = np.column_stack((wave, wave))
    sound = pygame.sndarray.make_sound(stereo_wave)
    return sound

TICK_SOUND  = make_beep(880, 0.12, 0.25)
FINAL_BEEP1 = make_beep(660, 0.35, 0.4)
FINAL_BEEP2 = make_beep(880, 0.6,  0.45)

def play_tick():
    TICK_SOUND.play()

def play_final():
    FINAL_BEEP1.play()
    QTimer.singleShot(450, lambda: FINAL_BEEP1.play())
    QTimer.singleShot(900, lambda: FINAL_BEEP2.play())


# ── Главный виджет ─────────────────────────────────────────────────────────
SIZE_SMALL   = 160   # обычный режим
SIZE_WARNING = 300   # последние 10 секунд

class TimerWindow(QWidget):

    def __init__(self):
        super().__init__()

        # Состояние таймера
        self.total_seconds  = 60
        self.remaining      = 60
        self.running        = False
        self.paused         = False
        self.warning_mode   = False
        self.pulse_alpha    = 0      # для пульсации цифр
        self.drag_pos       = None

        # Редактирование времени
        self.editing        = False
        self.edit_field     = None   # 'h', 'm', 's'
        self.edit_value     = ''

        self._setup_window()
        self._setup_timer()
        self._setup_animation()

    # ── Окно ──
    def _setup_window(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setFixedSize(SIZE_SMALL, SIZE_SMALL)
        # Позиция — правый верхний угол экрана
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.right() - SIZE_SMALL - 20, 20)

    # ── Таймер ──
    def _setup_timer(self):
        self.qtimer = QTimer(self)
        self.qtimer.setInterval(1000)
        self.qtimer.timeout.connect(self._tick)

        # Пульсация
        self.pulse_timer = QTimer(self)
        self.pulse_timer.setInterval(16)
        self.pulse_timer.timeout.connect(self._pulse_step)
        self.pulse_phase  = 0.0
        self.pulse_active = False

    # ── Анимация размера ──
    def _setup_animation(self):
        self.anim = QPropertyAnimation(self, b'geometry')
        self.anim.setDuration(350)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _resize_to(self, size):
        cur = self.geometry()
        cx  = cur.center().x()
        cy  = cur.top() + size // 2
        new_rect = QRect(cx - size // 2, cy - size // 2, size, size)
        # не выходить за правый/нижний край
        screen = QApplication.primaryScreen().availableGeometry()
        if new_rect.right() > screen.right() - 10:
            new_rect.moveRight(screen.right() - 10)
        if new_rect.bottom() > screen.bottom() - 10:
            new_rect.moveBottom(screen.bottom() - 10)
        self.anim.stop()
        self.anim.setStartValue(self.geometry())
        self.anim.setEndValue(new_rect)
        self.anim.start()

    # ── Пульсация ──
    def _start_pulse(self):
        self.pulse_phase  = 0.0
        self.pulse_active = True
        self.pulse_timer.start()

    def _pulse_step(self):
        self.pulse_phase += 0.08
        if self.pulse_phase >= math.pi:
            self.pulse_phase  = 0.0
            self.pulse_active = False
            self.pulse_timer.stop()
        self.update()

    def _pulse_scale(self):
        if not self.pulse_active:
            return 1.0
        return 1.0 + 0.15 * math.sin(self.pulse_phase)

    # ── Логика таймера ──
    def _tick(self):
        self.remaining -= 1

        if self.remaining <= 10 and self.remaining > 0:
            play_tick()
            self._start_pulse()
            if not self.warning_mode:
                self.warning_mode = True
                self.setFixedSize(SIZE_WARNING, SIZE_WARNING)
                self._resize_to(SIZE_WARNING)

        if self.remaining <= 0:
            self.remaining = 0
            self.running   = False
            self.qtimer.stop()
            play_final()
            self._start_pulse()

        self.update()

    def start(self):
        if not self.running and not self.paused:
            self.total_seconds = self.remaining
        self.running = True
        self.paused  = False
        self.qtimer.start()

    def pause(self):
        self.running = False
        self.paused  = True
        self.qtimer.stop()

    def reset(self):
        self.qtimer.stop()
        self.running      = False
        self.paused       = False
        self.warning_mode = False
        self.remaining    = self.total_seconds
        self.setFixedSize(SIZE_SMALL, SIZE_SMALL)
        self._resize_to(SIZE_SMALL)
        self.update()

    # ── Отрисовка ──────────────────────────────────────────────────────────
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        cx, cy = w / 2, h / 2
        warn = self.warning_mode and self.remaining > 0
        finished = self.remaining == 0 and not self.running and self.total_seconds > 0

        # ── Фон (полупрозрачный круг) ──
        bg_color = QColor(58, 18, 18, 210) if warn else QColor(27, 27, 31, 200)
        if finished:
            bg_color = QColor(80, 0, 0, 220)
        p.setBrush(bg_color)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(int(cx - w*0.47), int(cy - h*0.47),
                      int(w*0.94), int(h*0.94))

        # ── Кольцо прогресса ──
        margin  = w * 0.10
        ring_r  = QRect(int(margin), int(margin),
                        int(w - margin*2), int(h - margin*2))
        fraction = self.remaining / self.total_seconds if self.total_seconds > 0 else 0

        # фоновое кольцо
        pen_bg = QPen(QColor(255, 255, 255, 30))
        pen_bg.setWidth(int(w * 0.055))
        pen_bg.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen_bg)
        p.drawArc(ring_r, 0, 360 * 16)

        # цветное кольцо
        if fraction > 0:
            ring_color = QColor('#ff5252') if warn else QColor('#4caf50')
            pen_fg = QPen(ring_color)
            pen_fg.setWidth(int(w * 0.055))
            pen_fg.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen_fg)
            span = int(fraction * 360 * 16)
            p.drawArc(ring_r, 90 * 16, -span)

        # ── Время ──
        scale  = self._pulse_scale()
        time_str = self._format_time(self.remaining)

        font_size = int(w * 0.22)
        font = QFont('Arial', font_size, QFont.Weight.Bold)
        p.setFont(font)

        if warn:
            text_color = QColor('#ff5252')
        elif finished:
            text_color = QColor('#ff1744')
        else:
            text_color = QColor(255, 255, 255, 230)

        p.setPen(text_color)
        p.save()
        p.translate(cx, cy - h * 0.05)
        p.scale(scale, scale)
        fm = QFontMetrics(font)
        tw = fm.horizontalAdvance(time_str)
        p.drawText(-tw // 2, fm.ascent() // 2, time_str)
        p.restore()

        # ── Подпись снизу ──
        if warn or finished:
            sub = 'Time is up!' if finished else 'Remaining'
            sub_font = QFont('Arial', int(w * 0.07))
            p.setFont(sub_font)
            p.setPen(QColor(180, 180, 180, 180))
            sfm = QFontMetrics(sub_font)
            sw  = sfm.horizontalAdvance(sub)
            p.drawText(int(cx - sw / 2), int(cy + h * 0.32), sub)

        # ── Кнопки управления ──
        self._draw_buttons(p, w, h, warn)

    def _draw_buttons(self, p, w, h, warn):
        btn_y   = int(h * 0.78)
        btn_r   = int(w * 0.09)
        spacing = int(w * 0.25)
        centers = [int(w/2 - spacing), int(w/2), int(w/2 + spacing)]
        labels  = ['▶' if not self.running else '⏸', '↺', '✕']
        colors  = [QColor('#4caf50'), QColor('#607d8b'), QColor('#f44336')]
        if self.running:
            colors[0] = QColor('#ff9800')

        self._btn_centers = []
        for i, (cx_b, lbl, col) in enumerate(zip(centers, labels, colors)):
            self._btn_centers.append((cx_b, btn_y, btn_r))
            p.setBrush(QColor(col.red(), col.green(), col.blue(), 200))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(cx_b - btn_r, btn_y - btn_r, btn_r*2, btn_r*2)
            font = QFont('Arial', btn_r - 2)
            p.setFont(font)
            p.setPen(QColor(255, 255, 255, 230))
            fm  = QFontMetrics(font)
            tw  = fm.horizontalAdvance(lbl)
            p.drawText(cx_b - tw//2, btn_y + fm.ascent()//2 - 1, lbl)

    def _format_time(self, secs):
        h = secs // 3600
        m = (secs % 3600) // 60
        s = secs % 60
        if h > 0:
            return f'{h:02d}:{m:02d}:{s:02d}'
        return f'{m:02d}:{s:02d}'

    # ── Ввод времени двойным кликом ────────────────────────────────────────
    def mouseDoubleClickEvent(self, event):
        if not self.running:
            self._show_input_dialog()

    def _show_input_dialog(self):
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                     QPushButton, QSpinBox)
        from PyQt6.QtCore import Qt

        dlg = QDialog(self)
        dlg.setWindowTitle('Set Time')
        dlg.setWindowModality(Qt.WindowModality.ApplicationModal)
        dlg.setMinimumWidth(400)
        dlg.setStyleSheet('''
            QDialog { background: #1e1e24; color: white; }
            QLabel  { color: #ccc; font-size: 14px; }
            QSpinBox { 
                background: #2a2a30; color: white;
                border: 1px solid #555; border-radius: 6px;
                padding: 4px; font-size: 16px; width: 80px; height: 36px;
            }
            QPushButton {
                background: #4caf50; color: white;
                border: none; border-radius: 8px;
                padding: 4px 12px; font-size: 18px; font-weight: bold;
                min-width: 40px; min-height: 36px;
            }
            QPushButton:hover { background: #66bb6a; }
            QPushButton#ok { 
                background: #4caf50; min-width: 120px;
            }
            QPushButton#cancel { 
                background: #607d8b; min-width: 120px;
            }
            QPushButton#cancel:hover { background: #78909c; }
        ''')

        lay = QVBoxLayout(dlg)
        lay.setSpacing(20)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.addWidget(QLabel('Set the time:'))

        # Часы
        h_val = self.total_seconds // 3600
        h_lay = QHBoxLayout()
        h_minus = QPushButton('−')
        h_label = QLabel(str(h_val).zfill(2))
        h_label.setMinimumWidth(40)
        h_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h_label.setStyleSheet('color: white; font-size: 18px; font-weight: bold;')
        h_plus = QPushButton('+')
        h_lay.addWidget(QLabel('Hours:'))
        h_lay.addStretch()
        h_lay.addWidget(h_minus)
        h_lay.addWidget(h_label)
        h_lay.addWidget(h_plus)
        lay.addLayout(h_lay)

        # Минуты
        m_val = (self.total_seconds % 3600) // 60
        m_lay = QHBoxLayout()
        m_minus = QPushButton('−')
        m_label = QLabel(str(m_val).zfill(2))
        m_label.setMinimumWidth(40)
        m_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        m_label.setStyleSheet('color: white; font-size: 18px; font-weight: bold;')
        m_plus = QPushButton('+')
        m_lay.addWidget(QLabel('Minutes:'))
        m_lay.addStretch()
        m_lay.addWidget(m_minus)
        m_lay.addWidget(m_label)
        m_lay.addWidget(m_plus)
        lay.addLayout(m_lay)

        # Секунды
        s_val = self.total_seconds % 60
        s_lay = QHBoxLayout()
        s_minus = QPushButton('−')
        s_label = QLabel(str(s_val).zfill(2))
        s_label.setMinimumWidth(40)
        s_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        s_label.setStyleSheet('color: white; font-size: 18px; font-weight: bold;')
        s_plus = QPushButton('+')
        s_lay.addWidget(QLabel('Seconds:'))
        s_lay.addStretch()
        s_lay.addWidget(s_minus)
        s_lay.addWidget(s_label)
        s_lay.addWidget(s_plus)
        lay.addLayout(s_lay)

        # Функции изменения
        def update_h(delta):
            nonlocal h_val
            h_val = max(0, min(23, h_val + delta))
            h_label.setText(str(h_val).zfill(2))

        def update_m(delta):
            nonlocal m_val
            m_val = max(0, min(59, m_val + delta))
            m_label.setText(str(m_val).zfill(2))

        def update_s(delta):
            nonlocal s_val
            s_val = max(0, min(59, s_val + delta))
            s_label.setText(str(s_val).zfill(2))

        h_minus.clicked.connect(lambda: update_h(-1))
        h_plus.clicked.connect(lambda: update_h(1))
        m_minus.clicked.connect(lambda: update_m(-1))
        m_plus.clicked.connect(lambda: update_m(1))
        s_minus.clicked.connect(lambda: update_s(-1))
        s_plus.clicked.connect(lambda: update_s(1))

        # Кнопки OK/Cancel
        btn_lay = QHBoxLayout()
        btn_lay.setSpacing(12)
        ok_btn = QPushButton('OK')
        ok_btn.setObjectName('ok')
        cancel_btn = QPushButton('Cancel')
        cancel_btn.setObjectName('cancel')
        
        ok_btn.clicked.connect(dlg.accept)
        cancel_btn.clicked.connect(dlg.reject)
        
        btn_lay.addStretch()
        btn_lay.addWidget(ok_btn)
        btn_lay.addWidget(cancel_btn)
        lay.addLayout(btn_lay)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            total = h_val * 3600 + m_val * 60 + s_val
            if total > 0:
                self.total_seconds = total
                self.remaining     = total
                self.warning_mode  = False
                self.setFixedSize(SIZE_SMALL, SIZE_SMALL)
                self._resize_to(SIZE_SMALL)
                self.update()
                self.start()  # Автоматически запустить таймер

    # ── Мышь: перетаскивание и кнопки ─────────────────────────────────────
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            # Проверяем попадание в кнопку
            if hasattr(self, '_btn_centers'):
                for i, (cx_b, cy_b, r) in enumerate(self._btn_centers):
                    dx = pos.x() - cx_b
                    dy = pos.y() - cy_b
                    if dx*dx + dy*dy <= r*r:
                        self._handle_btn(i)
                        return
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.drag_pos and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_pos)

    def mouseReleaseEvent(self, event):
        self.drag_pos = None

    def _handle_btn(self, idx):
        if idx == 0:   # Старт / Пауза
            if self.running:
                self.pause()
            else:
                self.start()
        elif idx == 1: # Сброс
            self.reset()
        elif idx == 2: # Закрыть
            self.close()

    # ── Колесо мыши: изменение времени ────────────────────────────────────
    def wheelEvent(self, event):
        if not self.running:
            delta = 60 if event.angleDelta().y() > 0 else -60
            self.total_seconds = max(1, self.total_seconds + delta)
            self.remaining     = self.total_seconds
            self.update()

    # ── Закрытие приложения ──
    def closeEvent(self, event):
        """Правильное завершение приложения при закрытии окна"""
        # Остановить все таймеры
        self.qtimer.stop()
        self.pulse_timer.stop()
        # Остановить звуки pygame
        pygame.mixer.stop()
        pygame.mixer.quit()
        # Завершить приложение полностью
        event.accept()
        QApplication.quit()
        sys.exit(0)


# ── Запуск ─────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    win = TimerWindow()
    win.show()
    sys.exit(app.exec())
