import os
import json
from PySide6.QtWidgets import QVBoxLayout, QLabel
from PySide6.QtCore import QTimer, Qt, QDateTime
from PySide6.QtGui import QFont

# ////---- Default config for system_clock.json ----////
DEFAULT_CONFIG = {
    "font_family": "Arial",
    "font_size": 28,
    "font_color": "#00ffcc",
    "show_seconds": True,
    "show_date": False,
    "date_format": "dd.MM.yyyy"
}

def ensure_dir(path):
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        pass

def create_widget(BaseClass, module_name):
    class SystemClockWidget(BaseClass):
        def __init__(self):
            super().__init__(module_name)

            # layout
            layout = QVBoxLayout(self)
            self.setLayout(layout)
            self.setMinimumSize(200, 80)
            self.setMaximumSize(4000, 200)

            # label pre čas
            self.clock_label = QLabel("00:00")
            self.clock_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(self.clock_label)

            # label pre dátum
            self.date_label = QLabel("")
            self.date_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(self.date_label)

            # paths
            self._config_path = self.get_config_path("system_clock.json")

            # interné stavy
            self._last_config_mtime = None
            self._show_seconds = DEFAULT_CONFIG["show_seconds"]
            self._show_date = DEFAULT_CONFIG["show_date"]
            self._date_format = DEFAULT_CONFIG["date_format"]

            # ensure config exists
            self._ensure_config()
            self._load_and_apply_config()

            # timer
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.update_widget)
            self.timer.start(1000)

            # prvé vykreslenie
            self.update_widget()

        # ////---- Config helpers ----////
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

            fam = str(cfg.get("font_family", DEFAULT_CONFIG["font_family"]))
            size = int(cfg.get("font_size", DEFAULT_CONFIG["font_size"]))
            color = cfg.get("font_color", DEFAULT_CONFIG["font_color"])
            self._show_seconds = bool(cfg.get("show_seconds", DEFAULT_CONFIG["show_seconds"]))
            self._show_date = bool(cfg.get("show_date", DEFAULT_CONFIG["show_date"]))
            self._date_format = str(cfg.get("date_format", DEFAULT_CONFIG["date_format"]))

            font = QFont(fam, size)
            self.clock_label.setFont(font)
            self.date_label.setFont(font)
            self.clock_label.setStyleSheet(f"color: {color}; font-weight: bold;")
            self.date_label.setStyleSheet(f"color: {color};")

        # ////---- Tick každú sekundu ----////
        def update_widget(self):
            self._load_and_apply_config()

            now = QDateTime.currentDateTime()
            time_format = "HH:mm:ss" if self._show_seconds else "HH:mm"
            self.clock_label.setText(now.toString(time_format))

            if self._show_date:
                self.date_label.setText(now.toString(self._date_format))
                self.date_label.show()
            else:
                self.date_label.hide()

        def close_widget(self):
            try:
                self.timer.stop()
            except Exception:
                pass

    return SystemClockWidget()

def get_widget_dock_position():
    return Qt.LeftDockWidgetArea, 1

