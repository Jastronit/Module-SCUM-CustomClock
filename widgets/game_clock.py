import os
import json
import configparser
from datetime import datetime
from PySide6.QtWidgets import QVBoxLayout, QLabel
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFont

# ////---- Default config for game_clock.json ----////
DEFAULT_CONFIG = {
    "font_family": "Arial",
    "font_size": 32,
    "font_color": "#ff8000",
    "simulate_seconds": 120  # max počet sekúnd simulácie po update z INI
}

def ensure_dir(path):
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        pass

def create_widget(BaseClass, module_name):
    class GameClockWidget(BaseClass):
        def __init__(self):
            super().__init__(module_name)

            # layout
            layout = QVBoxLayout(self)
            self.setLayout(layout)
            self.setMinimumSize(200, 80)
            self.setMaximumSize(4000, 150)

            # label pre čas
            self.clock_label = QLabel("00:00:00")
            self.clock_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(self.clock_label)

            # paths
            self._config_path = self.get_config_path("game_clock.json")
            self._data_path = self.get_data_path("data.ini")

            # interné stavy
            self._last_config_mtime = None
            self._last_data_mtime = None
            self._time_float = 0.0
            self._time_speed = 1.0
            self._simulate_seconds = DEFAULT_CONFIG["simulate_seconds"]
            self._simulated_seconds_count = 0
            self._last_loaded_time_float = None
            self._last_loaded_time_speed = None
            self._time_disabled = False  # ak je True, hodiny sa neaktualizujú

            # ensure config exists
            self._ensure_config()
            self._load_and_apply_config()

            # timer
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.update_widget)
            self.timer.start(1000)

            # prvé načítanie
            self._load_data(force=True)

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
            self._simulate_seconds = int(cfg.get("simulate_seconds", DEFAULT_CONFIG["simulate_seconds"]))

            font = QFont(fam, size)
            self.clock_label.setFont(font)
            self.clock_label.setStyleSheet(f"color: {color}; font-weight: bold;")

        # ////---- Data helpers ----////
        def _load_data(self, force=False):
            # Načíta nový čas a speed z INI. Vracia True, ak sa zmenil čas alebo speed.
            if not os.path.exists(self._data_path):
                return False
            try:
                mtime = os.path.getmtime(self._data_path)
            except Exception:
                mtime = None

            # Ak sa súbor nezmenil, nič nerobíme
            if not force and self._last_data_mtime == mtime:
                return False

            # Uložíme nový mtime
            self._last_data_mtime = mtime

            try:
                cfg = configparser.ConfigParser()
                cfg.read(self._data_path)
                updated = False

                if "Time" in cfg:
                    # Detekcia hodnoty None (ignorovanie simulácie)
                    time_str = cfg["Time"].get("time_of_day", "None")
                    if time_str.strip().lower() == "none":
                        # skry hodiny
                        self.clock_label.setText("")
                        self._time_disabled = True
                        return False
                    else:
                        self._time_disabled = False

                    new_time = float(cfg["Time"].get("time_of_day", "0"))
                    new_speed = float(cfg["Time"].get("time_speed", "1.0"))

                    # Reset simulácie len ak sa zmenila hodnota s toleranciou pre float
                    if (self._last_loaded_time_float is None or
                        abs(new_time - self._last_loaded_time_float) > 0.001 or
                        self._last_loaded_time_speed is None or
                        abs(new_speed - self._last_loaded_time_speed) > 0.001):
                        
                        self._time_float = new_time
                        self._time_speed = new_speed
                        self._simulated_seconds_count = 0
                        updated = True

                    self._last_loaded_time_float = new_time
                    self._last_loaded_time_speed = new_speed

                if "Time_Simulation" in cfg:
                    self._simulate_seconds = int(cfg["Time_Simulation"].get("Second", self._simulate_seconds))

                return updated
            except Exception:
                return False

        # ////---- Tick každú sekundu ----////
        def update_widget(self):
            self._load_and_apply_config()
            updated = self._load_data(force=False)

            # Ak sú hodiny vypnuté, nesimuluj a nerenderuj
            if self._time_disabled:
                return

            # Reset simulácie sa deje len ak prišiel update z INI
            if updated:
                self._simulated_seconds_count = 0

            # simulácia iba ak nepresiahla max počet sekúnd
            if self._simulated_seconds_count < self._simulate_seconds:
                self._time_float += (1.0 / 3600.0) * self._time_speed
                self._time_float %= 24
                self._simulated_seconds_count += 1

            # update UI vždy ak nie je hodnota None
            hours = int(self._time_float)
            minutes = int((self._time_float - hours) * 60)
            seconds = int((((self._time_float - hours) * 60) - minutes) * 60)
            self.clock_label.setText(f"{hours:02}:{minutes:02}:{seconds:02}")

        def close_widget(self):
            try:
                self.timer.stop()
            except Exception:
                pass

    return GameClockWidget()

def get_widget_dock_position():
    return Qt.LeftDockWidgetArea, 2
