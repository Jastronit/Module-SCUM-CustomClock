import os
import json
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import QTimer, Qt, QPoint
from PySide6.QtGui import QFont, QPixmap, QPainter, QColor, QPolygon
from shortcut_listener import get_shortcut_listener

DEFAULT_CONFIG = {
    "font_family": "Arial",
    "font_size": 28,
    "font_color": "#00ffcc",
    "countdown_colors": {
        "100": "#4080cc",
        "75": "#00ff00",
        "50": "#ffff00",
        "25": "#ff8000",
        "20": "#ff6000",
        "15": "#ff4000",
        "10": "#ff2000",
        "5": "#ff0000",
        "0": "#ff0000"
    },
    "show_seconds": True,
    "direction": "up",
    "start_time_sec": 0,
    "shortcuts": {
        "start": "ctrl+s",
        "reset": "ctrl+r",
        "add_min": "ctrl+up",
        "add_10min": "ctrl+shift+up",
        "add_hour": "ctrl+right",
        "sub_min": "ctrl+down",
        "sub_hour": "ctrl+left",
        "direction_toggle": "ctrl+d"
    }
}

stopwatch_instance = [None]  # mutable reference to the current widget

def ensure_dir(path):
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        pass

def seconds_to_str(secs, show_seconds=True):
    neg = secs < 0
    secs = abs(int(secs))
    h = secs // 3600
    m = (secs % 3600) // 60
    s = secs % 60
    if show_seconds:
        return f"{'-' if neg else ''}{h:02}:{m:02}:{s:02}"
    else:
        return f"{'-' if neg else ''}{h:02}:{m:02}"

def get_percent_color(percent, colors):
    percent = int(percent)
    for p in sorted([int(k) for k in colors.keys()], reverse=True):
        if percent >= p:
            return colors[str(p)]
    return colors.get("0", "#ff0000")

def draw_arrow(direction="up", size=32, color="#00ffcc"):
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(Qt.NoPen)
    if direction == "up":
        points = [
            (size // 2, size // 4),
            (size // 4, 3 * size // 4),
            (3 * size // 4, 3 * size // 4)
        ]
    else:
        points = [
            (size // 2, 3 * size // 4),
            (size // 4, size // 4),
            (3 * size // 4, size // 4)
        ]
    poly = QPolygon([QPoint(x, y) for x, y in points])
    painter.drawPolygon(poly)
    painter.end()
    return pixmap

def create_widget(BaseClass, module_name):
    class StopwatchWidget(BaseClass):
        def __init__(self):
            super().__init__(module_name)
            stopwatch_instance[0] = self

            layout = QHBoxLayout(self)
            layout.setAlignment(Qt.AlignCenter)
            self.setLayout(layout)
            self.setMinimumSize(200, 80)
            self.setMaximumSize(4000, 200)

            self.arrow_label = QLabel()
            self.arrow_label.setAlignment(Qt.AlignVCenter | Qt.AlignRight)
            self.arrow_label.setFixedWidth(36)

            self.time_label = QLabel("00:00")
            self.time_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

            layout.addWidget(self.arrow_label)
            layout.addWidget(self.time_label)

            self._config_path = self.get_config_path("stopwatch.json")
            self._last_config_mtime = None

            self._running = False
            self._direction = "up"
            self._show_seconds = True
            self._start_time = 0
            self._current_time = 0
            self._percent_base_time = self._current_time
            self._countdown_colors = DEFAULT_CONFIG["countdown_colors"].copy()
            self._shortcuts = DEFAULT_CONFIG["shortcuts"].copy()
            self._font_color = DEFAULT_CONFIG["font_color"]

            self._ensure_config()
            self._load_and_apply_config()

            self.timer = QTimer(self)
            self.timer.timeout.connect(self.update_widget)
            self.timer.start(1000)
            self.update_widget()

            # Registrácia do shortcut listenera
            get_shortcut_listener().register_object(self)

        # ---- Config helpers ----
        def _ensure_config(self):
            cfg_dir = os.path.dirname(self._config_path)
            ensure_dir(cfg_dir)
            if not os.path.exists(self._config_path):
                try:
                    with open(self._config_path, "w", encoding="utf-8") as f:
                        json.dump(DEFAULT_CONFIG, f, indent=2)
                except Exception:
                    pass

        def _load_and_apply_config(self):
            try:
                mtime = os.path.getmtime(self._config_path) if os.path.exists(self._config_path) else None
            except Exception:
                mtime = None
            if mtime and mtime == self._last_config_mtime:
                return
            self._last_config_mtime = mtime

            cfg = DEFAULT_CONFIG.copy()
            try:
                with open(self._config_path, "r", encoding="utf-8") as f:
                    user_cfg = json.load(f)
                    if isinstance(user_cfg, dict):
                        cfg.update(user_cfg)
            except Exception:
                pass

            self._shortcuts = cfg.get("shortcuts", DEFAULT_CONFIG["shortcuts"])
            self._font_color = cfg.get("font_color", DEFAULT_CONFIG["font_color"])
            self._show_seconds = cfg.get("show_seconds", DEFAULT_CONFIG["show_seconds"])
            self._direction = cfg.get("direction", "up")
            self._start_time = cfg.get("start_time_sec", 0)
            self._countdown_colors = cfg.get("countdown_colors", DEFAULT_CONFIG["countdown_colors"])
            self._current_time = self._start_time

            fam = str(cfg.get("font_family", DEFAULT_CONFIG["font_family"]))
            size = int(cfg.get("font_size", DEFAULT_CONFIG["font_size"]))
            font = QFont(fam, size)
            self.time_label.setFont(font)
            self.update_arrow()

        def update_arrow(self):
            color = self._font_color
            if self._direction == "up":
                self.arrow_label.setPixmap(draw_arrow("up", 32, color))
            else:
                self.arrow_label.setPixmap(draw_arrow("down", 32, color))

        # ---- Tick každú sekundu ----
        def update_widget(self):
            if self._running:
                if self._direction == "up":
                    self._current_time += 1
                else:
                    self._current_time -= 1
                    if self._current_time < 0:
                        self._current_time = 0
                        self._running = False

            percent = 100
            if self._direction == "down" and self._percent_base_time > 0:
                percent = int(100 * self._current_time / self._percent_base_time)
                percent = max(0, min(100, percent))
                color = get_percent_color(percent, self._countdown_colors)
            else:
                color = self._font_color

            self.time_label.setStyleSheet(f"color: {color}; font-weight: bold;")
            self.time_label.setText(seconds_to_str(self._current_time, self._show_seconds))
            self.update_arrow()

        def close_widget(self):
            try:
                self.timer.stop()
            except Exception:
                pass
            get_shortcut_listener().unregister_object(self)
            stopwatch_instance[0] = None

        # ---- Handler pre shortcut_listener ----
        def handle_shortcut(self, key: str):
            # print("Shortcut received:", key)
            """Porovná stlačenú kombináciu s hodnotami z _shortcuts"""
            for action, shortcut in self._shortcuts.items():
                if key.lower() == shortcut.lower():
                    if action == "start":
                        self._running = not self._running
                        if self._running:
                            self._percent_base_time = self._current_time
                    elif action == "reset":
                        self._current_time = self._start_time
                        self._running = False
                        self._percent_base_time = self._current_time
                    elif action == "add_min":
                        self._current_time += 60
                    elif action == "add_10min":
                        self._current_time += 600
                    elif action == "add_hour":
                        self._current_time += 3600
                    elif action == "sub_min":
                        self._current_time = max(0, self._current_time - 60)
                    elif action == "sub_hour":
                        self._current_time = max(0, self._current_time - 3600)
                    elif action == "direction_toggle":
                        self._direction = "down" if self._direction == "up" else "up"
                        self.update_arrow()
                    self.update_widget()
                    break  # už sme našli zodpovedajúcu akciu

    return StopwatchWidget()


def get_widget_dock_position():
    return Qt.LeftDockWidgetArea, 4

