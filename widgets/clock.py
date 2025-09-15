from PySide6.QtWidgets import QVBoxLayout, QLabel, QApplication
from PySide6.QtCore import QTimer, Qt
import os, configparser

# ////---- Jednoduchá detekcia dark mode ----////
def is_dark_mode():
    palette = QApplication.instance().palette()
    window_color = palette.color(QPalette.Window)
    return window_color.lightness() < 128

# ////---- Vytvorenie widgetu hodín ----////
def create_widget(BaseClass, module_name):
    class ClockWidget(BaseClass):
        def __init__(self):
            super().__init__(module_name)

            # layout
            layout = QVBoxLayout(self)
            self.setLayout(layout)

            self.setMinimumSize(200, 80)
            self.setMaximumSize(4000, 150)

            # Jeden label pre čas
            self.clock_label = QLabel("00:00")
            self.clock_label.setAlignment(Qt.AlignCenter)
            self.clock_label.setStyleSheet("font-size: 32px; font-weight: bold; color: #ff8000;")
            layout.addWidget(self.clock_label)

            # timer na pravidelný update
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.update_widget)
            self.timer.start(1000)  # každú sekundu

            # prvý update hneď
            self.update_widget()

        def update_widget(self):
            data_file = self.get_data_path("weather_time.ini")
            hours, minutes = "00", "00"

            if os.path.exists(data_file):
                config = configparser.ConfigParser()
                config.read(data_file)

                if "weather_time" in config:
                    hours = config["weather_time"].get("hours", "00")
                    minutes = config["weather_time"].get("minutes", "00")

            # Aktualizácia UI
            self.clock_label.setText(f"{hours.zfill(2)}:{minutes.zfill(2)}")

        def close_widget(self):
            self.timer.stop()

    return ClockWidget()

# ////---- Predvolená pozícia dock widgetu ----////
def get_widget_dock_position():
    return Qt.LeftDockWidgetArea, 1  # oblasť, poradie
