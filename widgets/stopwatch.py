# stopwatch.py
# Widget: Stopky (stopwatch) s možnosťou počítania nahor a nadol, farebným indikátorom a skratkami
# Autor: Jastronit
# Verzia: 2.1

# /////////////////////////////////////////////////////////////////////////////////////////////
# ////---- Importy ----////
# /////////////////////////////////////////////////////////////////////////////////////////////
import os
import json
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import QTimer, Qt, QPoint
from PySide6.QtGui import QFont, QPixmap, QPainter, QColor, QPolygon

from shortcut_manager import get_bridge

# ////---- Default config ----////
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
        "5": "#ff1000",
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
        "sub_10min": "ctrl+shift+down",
        "sub_hour": "ctrl+left",
        "direction_toggle": "ctrl+d"
    }
}

stopwatch_instance = [None]  # optional global ref

# /////////////////////////////////////////////////////////////////////////////////////////////
# ////---- Pomocné funkcie ----////
# /////////////////////////////////////////////////////////////////////////////////////////////

# ////---- Zabezpečí, že adresár existuje ----////
def ensure_dir(path):
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        pass
# ////-----------------------------------------------------------------------------------------

# ////---- Prevod sekúnd na formát HH:MM:SS ----////
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
# ////-----------------------------------------------------------------------------------------

# ////---- Získanie farby podľa percentuálneho stavu ----////
def get_percent_color(percent, colors):
    percent = int(percent)
    # keys in config are strings like "100","75",...
    keys = sorted([int(k) for k in colors.keys()], reverse=True)
    for p in keys:
        if percent >= p:
            return colors[str(p)]
    return colors.get("0", "#ff0000")
# ////-----------------------------------------------------------------------------------------

# ////---- Vykreslenie šípky (nahor alebo nadol) ----////
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
# ////-----------------------------------------------------------------------------------------

# ////---- Normalizácia skratky na formát bez medzier a malými písmenami ----////
def normalize_combo(combo: str) -> str:
    """Normalize a combo string to the form that ShortcutListener emits:
       - lower case
       - no spaces
       - modifiers and keys joined by '+' (we accept user input like 'Ctrl + Shift + Up')
    """
    if not combo:
        return combo
    # remove spaces and lower
    return combo.replace(" ", "").lower()
# ////-----------------------------------------------------------------------------------------

# /////////////////////////////////////////////////////////////////////////////////////////////
# ////---- Hlavná trieda widgetu ----////
# /////////////////////////////////////////////////////////////////////////////////////////////

# ////---- Vytvorenie widgetu ----////
def create_widget(BaseClass, module_name):
    class StopwatchWidget(BaseClass):
        # ////---- Inicializácia widgetu ----////
        def __init__(self):
            super().__init__(module_name)
            stopwatch_instance[0] = self

            # UI layout (kept similar to your original)
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

            # config/state
            self._config_path = self.get_config_path("stopwatch.json")
            self._last_config_mtime = None

            self._running = False
            self._direction = "up"  # "up" or "down"
            self._show_seconds = True
            self._start_time = 0
            self._current_time = 0
            self._percent_base_time = 0  # base time for percent calculation in countdown mode
            self._countdown_colors = DEFAULT_CONFIG["countdown_colors"].copy()
            self._shortcuts = DEFAULT_CONFIG["shortcuts"].copy()
            self._font_color = DEFAULT_CONFIG["font_color"]

            # Bridge related
            self.bridge = get_bridge()
            self._bridge_handlers = {}  # map normalized_combo -> zero-arg handler

            # timers
            self.timer = QTimer(self)
            self.timer.timeout.connect(self._tick)
            self.timer.start(1000)  # every second

            # load config now (and register shortcuts)
            self._ensure_config()
            self._load_and_apply_config()
            self._register_shortcuts()

            # initial UI update
            self.update_widget()
        # ////---------------------------------------------------------------------------------

        # ////---- Zabezpečí, že config súbor existuje ----////
        def _ensure_config(self):
            cfg_dir = os.path.dirname(self._config_path)
            ensure_dir(cfg_dir)
            if not os.path.exists(self._config_path):
                try:
                    with open(self._config_path, "w", encoding="utf-8") as f:
                        json.dump(DEFAULT_CONFIG, f, indent=2)
                except Exception:
                    pass
        # ////---------------------------------------------------------------------------------

        # ////---- Načíta config súbor a aplikuje nastavenia ----////
        def _load_and_apply_config(self):
            try:
                mtime = os.path.getmtime(self._config_path) if os.path.exists(self._config_path) else None
            except Exception:
                mtime = None
            # If not changed, keep current
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

            # apply config
            self._shortcuts = cfg.get("shortcuts", DEFAULT_CONFIG["shortcuts"])
            self._font_color = cfg.get("font_color", DEFAULT_CONFIG["font_color"])
            self._show_seconds = cfg.get("show_seconds", DEFAULT_CONFIG["show_seconds"])
            self._direction = cfg.get("direction", "up")
            self._start_time = cfg.get("start_time_sec", 0)
            self._countdown_colors = cfg.get("countdown_colors", DEFAULT_CONFIG["countdown_colors"]).copy()

            # reset current time to start_time on config load (original behaviour)
            self._current_time = self._start_time
            self._percent_base_time = self._current_time

            # font
            fam = str(cfg.get("font_family", DEFAULT_CONFIG["font_family"]))
            size = int(cfg.get("font_size", DEFAULT_CONFIG["font_size"]))
            font = QFont(fam, size)
            self.time_label.setFont(font)

            # update arrow color/graphic
            self.update_arrow()
        # ////---------------------------------------------------------------------------------

        # ////---- Registrácia skratiek do bridge ----////
        def _register_shortcuts(self):
            """Register current shortcuts into bridge. Uses normalized combo keys:
               e.g. "ctrl+shift+up" -> register event name "shortcut.ctrl+shift+up".
               Handlers are zero-arg callables because bridge.emit doesn't pass args.
            """
            # unregister old
            try:
                for combo_norm, handler in list(self._bridge_handlers.items()):
                    self.bridge.off(f"shortcut.{combo_norm}", handler)
            except Exception:
                pass
            self._bridge_handlers.clear()

            # register new
            for action, combo in self._shortcuts.items():
                combo_norm = normalize_combo(combo)
                event_name = f"shortcut.{combo_norm}"
                # handler must be zero-arg because bridge.emit triggers callback without args
                def make_handler(act):
                    return lambda act=act, combo_norm=combo_norm: self._on_shortcut_triggered(act, combo_norm)
                handler = make_handler(action)
                self.bridge.on(event_name, handler)
                self._bridge_handlers[combo_norm] = handler
        # ////---------------------------------------------------------------------------------

        # ////---- Spracovanie spustenej skratky ----////
        def _on_shortcut_triggered(self, action_name: str, combo_norm: str):
            """Execute action mapped to a shortcut action_name (like 'start' or 'add_min')."""
            # note: action_name is the logical name from config, not the combo string
            if action_name == "start":
                self._running = not self._running
                if self._running:
                    # if starting to count (e.g. start), set percent base for countdown
                    if self._direction == "down" and self._percent_base_time == 0:
                        self._percent_base_time = self._current_time if self._current_time > 0 else 1
                else:
                    # paused - keep percent base as-is so percentage remains meaningful
                    pass
            elif action_name == "reset":
                self._current_time = self._start_time
                self._running = False
                self._percent_base_time = self._current_time
            elif action_name == "add_min":
                self._current_time += 60
            elif action_name == "add_10min":
                self._current_time += 600
            elif action_name == "add_hour":
                self._current_time += 3600
            elif action_name == "sub_min":
                self._current_time = max(0, self._current_time - 60)
            elif action_name == "sub_10min":
                self._current_time = max(0, self._current_time - 600)
            elif action_name == "sub_hour":
                self._current_time = max(0, self._current_time - 3600)
            elif action_name == "direction_toggle":
                # switch direction and recompute percent base accordingly
                old = self._direction
                self._direction = "down" if old == "up" else "up"
                # when switching to countdown, set base if needed
                if self._direction == "down":
                    self._percent_base_time = self._current_time if self._current_time > 0 else 1
                else:
                    self._percent_base_time = self._current_time
                self.update_arrow()
            # update immediately UI
            self.update_widget()
        # ////---------------------------------------------------------------------------------

        # ////---- Tick handler (every second) ----////
        def _tick(self):
            """Called every second by QTimer: update time, reload config if changed, update UI."""
            # Check config mtime and reload (so we reuse the same second timer)
            try:
                cur_mtime = os.path.getmtime(self._config_path) if os.path.exists(self._config_path) else None
            except Exception:
                cur_mtime = None
            if cur_mtime != self._last_config_mtime:
                # config changed -> reload and re-register shortcuts
                self._load_and_apply_config()
                self._register_shortcuts()

            # Advance time if running
            if self._running:
                if self._direction == "up":
                    self._current_time += 1
                else:
                    self._current_time -= 1
                    if self._current_time < 0:
                        self._current_time = 0
                        self._running = False

            # update UI every tick
            self.update_widget()
        # ////---------------------------------------------------------------------------------

        # ////---- Aktualizácia šípky podľa smeru ----////
        def update_arrow(self):
            color = self._font_color
            if self._direction == "up":
                self.arrow_label.setPixmap(draw_arrow("up", 32, color))
            else:
                self.arrow_label.setPixmap(draw_arrow("down", 32, color))
        # ////---------------------------------------------------------------------------------

        # ////---- Aktualizácia vizuálu a textu podľa času ----////
        def update_widget(self):
            """Update visual label and color according to direction/percent."""
            # compute color
            color = self._font_color
            if self._direction == "down" and self._percent_base_time > 0:
                percent = int(100 * self._current_time / max(1, self._percent_base_time))
                percent = max(0, min(100, percent))
                color = get_percent_color(percent, self._countdown_colors)
            # update style and text
            self.time_label.setStyleSheet(f"color: {color}; font-weight: bold;")
            self.time_label.setText(seconds_to_str(self._current_time, self._show_seconds))
            self.update_arrow()
        # ////---------------------------------------------------------------------------------

        # ////---- Cleanup on close ----////
        def close_widget(self):
            # cleanup timers and unregister shortcuts
            try:
                self.timer.stop()
            except Exception:
                pass
            for combo_norm, handler in list(self._bridge_handlers.items()):
                try:
                    self.bridge.off(f"shortcut.{combo_norm}", handler)
                except Exception:
                    pass
            self._bridge_handlers.clear()
            stopwatch_instance[0] = None
        # ////---------------------------------------------------------------------------------

        # ////---- Event pri zobrazení widgetu (pre registráciu skratiek) ----////
        def showEvent(self, event):
            super().showEvent(event)
            self._register_shortcuts()
        # ////---------------------------------------------------------------------------------

    return StopwatchWidget()

# ////---- Pozícia docku (vľavo, index 4) ----////
def get_widget_dock_position():
    return Qt.LeftDockWidgetArea, 4

