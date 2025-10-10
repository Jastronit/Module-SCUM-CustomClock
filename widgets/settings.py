from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton
from PySide6.QtCore import Qt
import os
import sys
import subprocess

def create_widget(BaseClass, module_name):
    class SettingsWidget(BaseClass):
        def __init__(self):
            super().__init__(module_name)

            layout = QVBoxLayout(self)
            self.setLayout(layout)

            self.setMaximumSize(500, 200)

            # Tlačidlo na otvorenie
            self.btn_config = QPushButton("custom_overlays.json")
            self.btn_config.clicked.connect(lambda: self.open_file("custom_overlays.json"))
            layout.addWidget(self.btn_config)

            # Tlačidlo na otvorenie
            self.btn_config = QPushButton("system_clock.json")
            self.btn_config.clicked.connect(lambda: self.open_file("system_clock.json"))
            layout.addWidget(self.btn_config)

            # Tlačidlo na otvorenie
            self.btn_config = QPushButton("game_clock.json")
            self.btn_config.clicked.connect(lambda: self.open_file("game_clock.json"))
            layout.addWidget(self.btn_config)

            # Tlačidlo na otvorenie
            self.btn_config = QPushButton("stopwatch.json")
            self.btn_config.clicked.connect(lambda: self.open_file("stopwatch.json"))
            layout.addWidget(self.btn_config)

            # Tlačidlo na otvorenie path.ini
            self.btn_path = QPushButton("path.ini")
            self.btn_path.clicked.connect(lambda: self.open_file("path.ini"))
            layout.addWidget(self.btn_path)

        def open_file(self, filename):
            # Otvorí súbor z config zložky v predvolenom textovom editore
            # Využiť metódu BaseWidget
            file_path = self.get_config_path(filename)

            if not os.path.exists(file_path):
                print(f"not exist: {file_path}")
                return

            try:
                if sys.platform.startswith("win"):
                    os.startfile(file_path)
                elif sys.platform.startswith("darwin"):
                    subprocess.run(["open", file_path])
                else:
                    subprocess.run(["xdg-open", file_path])
            except Exception as e:
                print(f"Chyba pri otváraní súboru {file_path}: {e}")

        def get_widget_dock_position():
            # Predvolená pozícia pre tento widget
            from PySide6.QtCore import Qt
            return Qt.RightDockWidgetArea

    return SettingsWidget()

# Predvolená pozícia dock widgetu
def get_widget_dock_position():
    return Qt.RightDockWidgetArea, 2  # oblasť, poradie

