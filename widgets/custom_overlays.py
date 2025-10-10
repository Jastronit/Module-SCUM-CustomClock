import os
import json
import importlib.util
import glob
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel, QListWidget, QListWidgetItem,
    QHBoxLayout, QSpinBox, QMessageBox, QApplication, QColorDialog, QLineEdit
)
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QPixmap, QPalette, QColor
import overlay_manager
from pynput import keyboard

# ------------------ GLOBAL SHORTCUTS ------------------
active_shortcuts = {}
pressed_keys = set()

def normalize_key(k):
    # Mapovanie pre modifikátory
    if isinstance(k, keyboard.Key):
        if k in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            return "ctrl"
        if k in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r):
            return "alt"
        if k in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r):
            return "shift"
        return str(k).replace("Key.", "")
    elif hasattr(k, "char") and k.char:
        return k.char.lower()
    return str(k)

# Pomocná sada, aby sa overlay prepínal len raz na stlačenie
already_triggered = set()

def on_press(key):
    k = normalize_key(key)
    pressed_keys.add(k)
    for overlay_id, shortcut in active_shortcuts.items():
        if not shortcut:
            continue
        keys = [x.lower() for x in shortcut.split("+")]
        # Porovnávaj ako množiny
        if set(keys).issubset(pressed_keys):
            if (overlay_id, tuple(sorted(pressed_keys))) in already_triggered:
                continue
            module, cname = overlay_id.split(":", 1)
            mgr = overlay_manager.start_overlay_manager()
            full_name = f"{module}:{cname}"
            if full_name in mgr.overlays:
                win = mgr.overlays[full_name]
                new_state = not getattr(win, "user_visible", True)
                win.user_visible = new_state
                try:
                    win.set_overlay_visible(new_state and mgr.global_show)
                except Exception:
                    win.setVisible(new_state and mgr.global_show)
                # Refresh ikon
                app = QApplication.instance()
                for widget in app.allWidgets():
                    if hasattr(widget, "refresh_overlay_list") and callable(widget.refresh_overlay_list):
                        if hasattr(widget, "module_name") and widget.module_name == module:
                            widget.refresh_overlay_list()
            already_triggered.add((overlay_id, tuple(sorted(pressed_keys))))

def on_release(key):
    k = normalize_key(key)
    if k in pressed_keys:
        pressed_keys.remove(k)
    # Po uvoľnení klávesy vymaž trigger pre všetky overlaye
    to_remove = set()
    for item in already_triggered:
        overlay_id, keys_tuple = item
        if k in keys_tuple:
            to_remove.add(item)
    already_triggered.difference_update(to_remove)

listener = keyboard.Listener(on_press=on_press, on_release=on_release)
listener.daemon = True
listener.start()

# ------------------ RGBA MODE DETECTION ------------------
def detect_rgba_mode():
    test = QLabel()
    try:
        test.setStyleSheet("background-color: rgba(0,0,0,128);")
        effective = test.palette().color(test.backgroundRole()).alpha()
        if 120 <= effective <= 135:
            return "int"
    except Exception:
        pass
    return "float"

RGBA_MODE = detect_rgba_mode()

class DraggableListWidget(QListWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setDragDropMode(QListWidget.InternalMove)

def is_dark_mode():
    palette = QApplication.instance().palette()
    window_color = palette.color(QPalette.Window)
    return window_color.lightness() < 128

def get_config_path(module_name):
    return os.path.join("modules", module_name, "config", "custom_overlays.json")

def get_default_overlay_params():
    return {
        "x": 100, "y": 100, "w": 400, "h": 200,
        "bg": "rgba(0,0,0,0)",
        "widgets": [],
        "widget_bgs": {},
        "user_visible": True,
        "shortcut": ""
    }

def load_custom_overlays(module_name):
    path = get_config_path(module_name)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_custom_overlays(module_name, data):
    path = get_config_path(module_name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def load_widget(widget_name, BaseClass, module_name):
    widget_path = os.path.join("modules", module_name, "widgets", f"{widget_name}.py")
    if not os.path.exists(widget_path):
        print(f"Widget {widget_name} for module {module_name} does not exist.")
        return None

    spec = importlib.util.spec_from_file_location(widget_name, widget_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    if hasattr(mod, "create_widget"):
        return mod.create_widget(BaseClass, module_name)
    return None

def build_overlay_window(name, params, BaseClass, module_name):
    overlay_widget = QWidget()
    vbox = QVBoxLayout(overlay_widget)
    overlay_widget.setStyleSheet(f"background-color: {params.get('bg','rgba(0,0,0,0)')}; border: none;")

    for widget_name in params.get("widgets", []):
        w = load_widget(widget_name, BaseClass, module_name)
        if w:
            try:
                w.setObjectName(widget_name)
            except Exception:
                pass
            bg = params.get("widget_bgs", {}).get(widget_name, "rgba(0,0,0,0)")
            try:
                w.setStyleSheet(f"background-color: {bg}; border: none;")
            except Exception:
                pass
            vbox.addWidget(w)

    mgr = overlay_manager.start_overlay_manager()
    full_name = f"{module_name}:{name}"
    mgr.add_overlay(
        overlay_widget,
        name=full_name,
        params={
            "x": params.get("x", 100),
            "y": params.get("y", 100),
            "w": params.get("w", 400),
            "h": params.get("h", 200),
            "bg": params.get("bg", "rgba(0,0,0,0)"),
            "module_name": module_name
        },
        module_name=module_name
    )

    win = mgr.overlays.get(full_name)
    if win is not None:
        win.user_visible = params.get("user_visible", True)
        try:
            win.set_overlay_visible(win.user_visible and mgr.global_show)
        except Exception:
            win.setVisible(win.user_visible and mgr.global_show)
        win._overlay_root = overlay_widget
        try:
            win.params['bg'] = params.get('bg', win.params.get('bg', 'rgba(0,0,0,0)'))
        except Exception:
            win.params = win.params or {}
            win.params['bg'] = params.get('bg', 'rgba(0,0,0,0)')

def create_color_preview(spins, on_color_changed=None):
    preview = QLabel()
    preview.setFixedSize(30, 20)
    preview.setStyleSheet(f"background-color: rgba({spins[0].value()},{spins[1].value()},{spins[2].value()},{spins[3].value()}); border: 1px solid #888;")

    def update_preview():
        preview.setStyleSheet(f"background-color: rgba({spins[0].value()},{spins[1].value()},{spins[2].value()},{spins[3].value()}); border: 1px solid #888;")
        if on_color_changed:
            on_color_changed()

    def on_click(event):
        initial = QColor(spins[0].value(), spins[1].value(), spins[2].value(), spins[3].value())
        color = QColorDialog.getColor(initial, None, "Vyber farbu", QColorDialog.ShowAlphaChannel)
        if color.isValid():
            spins[0].setValue(color.red())
            spins[1].setValue(color.green())
            spins[2].setValue(color.blue())
            spins[3].setValue(color.alpha())
            update_preview()

    preview.mousePressEvent = on_click
    for spin in spins:
        spin.valueChanged.connect(update_preview)
    return preview

def create_widget(BaseClass, module_name):
    class CustomOverlaysWidget(BaseClass):
        def __init__(self):
            super().__init__(module_name)
            self.module_name = module_name
            self.setWindowTitle("Vlastné Overlays (drag & drop)")
            self._suppress_widget_updates = False

            layout = QVBoxLayout(self)
            self.setLayout(layout)

            # banner
            try:
                banner_path = os.path.join(os.path.dirname(__file__),
                                           "../assets/banners/CUSTOM_OVERLAY.png" if is_dark_mode() else "../assets/banners/CUSTOM_OVERLAY_DARK.png")
                if os.path.exists(banner_path):
                    self.banner = QLabel()
                    pixmap = QPixmap(banner_path)
                    self.banner.setPixmap(pixmap.scaledToHeight(32, Qt.SmoothTransformation))
                    self.banner.setAlignment(Qt.AlignCenter)
                    layout.addWidget(self.banner)
            except Exception:
                pass

            layout.addWidget(QLabel("Custom overlays list:"))
            self.overlay_list = QListWidget()
            layout.addWidget(self.overlay_list)
            self.overlay_list.itemSelectionChanged.connect(self.on_select_overlay)

            # Shortcut field
            self.shortcut_label = QLabel("Overlay shortcut (press keys here):")
            layout.addWidget(self.shortcut_label)
            self.shortcut_field = QLineEdit()
            self.shortcut_field.setReadOnly(True)
            self.shortcut_field.setPlaceholderText("Click and press keys...")
            layout.addWidget(self.shortcut_field)
            self.recording_shortcut = False
            self.shortcut_field.installEventFilter(self)

            layout.addWidget(QLabel("Select widgets (drag to reorder, check to include):"))
            self.widget_list = DraggableListWidget()
            self.widget_list.setSelectionMode(QListWidget.SingleSelection)
            layout.addWidget(self.widget_list)

            self.widget_bg_spins = {}
            widgets_path = os.path.join("modules", module_name, "widgets")
            files = sorted(glob.glob(os.path.join(widgets_path, "*.py"))) if os.path.isdir(widgets_path) else []
            for file in files:
                wname = os.path.splitext(os.path.basename(file))[0]
                if wname.startswith("custom_overlays") or wname == "__init__":
                    continue
                item = QListWidgetItem(wname)
                flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled
                item.setFlags(flags)
                item.setCheckState(Qt.Unchecked)
                item.setData(Qt.UserRole, wname)
                self.widget_list.addItem(item)

                hbox = QHBoxLayout()
                label = QLabel(f"BG {wname}:")
                hbox.addWidget(label, 1)
                spins = []
                for color in ["R", "G", "B", "A"]:
                    lbl = QLabel(color + ":")
                    lbl.setFixedWidth(14)
                    hbox.addWidget(lbl, 0, Qt.AlignRight)
                    spin = QSpinBox()
                    spin.setRange(0, 255)
                    spin.setValue(0 if color != "A" else 0)
                    spin.setFixedWidth(60)
                    hbox.addWidget(spin, 0, Qt.AlignRight)
                    spins.append(spin)
                preview = create_color_preview(spins)
                hbox.addWidget(preview, 0, Qt.AlignRight)
                layout.addLayout(hbox)
                self.widget_bg_spins[wname] = spins
                for spin in spins:
                    spin.valueChanged.connect(lambda _val, wn=wname: self.update_widget_bg(wn))

            color_layout = QHBoxLayout()
            label = QLabel("Background:")
            color_layout.addWidget(label, 1)
            self.spin_r = QSpinBox(); self.spin_r.setRange(0,255); self.spin_r.setValue(0)
            self.spin_r.setFixedWidth(60)
            self.spin_g = QSpinBox(); self.spin_g.setRange(0,255); self.spin_g.setValue(0)
            self.spin_g.setFixedWidth(60)
            self.spin_b = QSpinBox(); self.spin_b.setRange(0,255); self.spin_b.setValue(0)
            self.spin_b.setFixedWidth(60)
            self.spin_a = QSpinBox(); self.spin_a.setRange(0,255); self.spin_a.setValue(0)
            self.spin_a.setFixedWidth(60)
            overlay_spins = [self.spin_r, self.spin_g, self.spin_b, self.spin_a]
            for spin in overlay_spins:
                spin.valueChanged.connect(self.update_overlay_bg)
            for lbl_text, spin in zip(["R","G","B","A"], overlay_spins):
                lbl = QLabel(lbl_text + ":")
                lbl.setFixedWidth(14)
                color_layout.addWidget(lbl, 0, Qt.AlignRight)
                color_layout.addWidget(spin, 0, Qt.AlignRight)
            overlay_preview = create_color_preview(overlay_spins, on_color_changed=self.update_overlay_bg)
            color_layout.addWidget(overlay_preview, 0, Qt.AlignRight)
            layout.addLayout(color_layout)

            layout.addWidget(QLabel("Game must be borderless windowed for overlays to work properly!"))

            btn_create = QPushButton("Create new overlay")
            btn_create.clicked.connect(self.create_overlay)
            layout.addWidget(btn_create)

            btn_delete = QPushButton("Delete selected overlay")
            btn_delete.clicked.connect(self.delete_selected_overlay)
            layout.addWidget(btn_delete)

            btn_toggle = QPushButton("Toggle visibility (selected)")
            btn_toggle.clicked.connect(self.toggle_selected_overlay)
            layout.addWidget(btn_toggle)

            layout.addWidget(QLabel("F9: show/hide all overlays, F10: edit mode"))
            layout.addWidget(QLabel("Edit mode: left mouse drag to move, right mouse drag to resize"))

            self.selected_overlay = None
            self.custom_overlays = load_custom_overlays(module_name)
            self.refresh_overlay_list()

            for cname, params in self.custom_overlays.items():
                build_overlay_window(cname, params, BaseClass, module_name)
                # zaregistruj skratku
                shortcut = params.get("shortcut", "")
                if shortcut:
                    active_shortcuts[f"{module_name}:{cname}"] = shortcut

        def eventFilter(self, source, event):
            if source == self.shortcut_field:
                if event.type() == QEvent.FocusIn:
                    self.recording_shortcut = True
                    self.shortcut_field.setText("")
                    return True
                if event.type() == QEvent.KeyPress and self.recording_shortcut:
                    seq = []
                    if event.modifiers() & Qt.ControlModifier: seq.append("ctrl")
                    if event.modifiers() & Qt.AltModifier: seq.append("alt")
                    if event.modifiers() & Qt.ShiftModifier: seq.append("shift")
                    key = event.key()
                    # Ak je to len modifikátor, neukončuj recording_shortcut!
                    if key in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta):
                        return True
                    text = event.text().lower()
                    if text and text not in seq:
                        seq.append(text)
                    shortcut = "+".join(seq)
                    self.shortcut_field.setText(shortcut)
                    # uloz do JSON, atď.
                    if self.selected_overlay:
                        self.custom_overlays[self.selected_overlay]["shortcut"] = shortcut
                        save_custom_overlays(self.module_name, self.custom_overlays)
                        active_shortcuts[f"{self.module_name}:{self.selected_overlay}"] = shortcut
                    self.recording_shortcut = False
                    self.shortcut_field.clearFocus()
                    return True
            return super().eventFilter(source, event)

        def get_overlay_bg(self):
            r,g,b,a = self.spin_r.value(), self.spin_g.value(), self.spin_b.value(), self.spin_a.value()
            return f"rgba({r},{g},{b},{a})"

        def get_widget_bg(self, widget_name):
            spins = self.widget_bg_spins.get(widget_name)
            if not spins:
                return "rgba(0,0,0,0)"
            r,g,b,a = [s.value() for s in spins]
            return f"rgba({r},{g},{b},{a})"

        def refresh_widget_list_from_json(self, cname):
            self._suppress_widget_updates = True
            try:
                for i in range(self.widget_list.count()):
                    it = self.widget_list.item(i)
                    it.setCheckState(Qt.Unchecked)
                if not cname:
                    return
                params = self.custom_overlays.get(cname, {})
                wanted = params.get("widgets", [])
                widget_bgs = params.get("widget_bgs", {})
                for i in range(self.widget_list.count()):
                    it = self.widget_list.item(i)
                    wname = it.data(Qt.UserRole)
                    it.setCheckState(Qt.Checked if wname in wanted else Qt.Unchecked)
                    if wname in widget_bgs:
                        rgba = widget_bgs[wname]
                        try:
                            inside = rgba.split("(",1)[1].split(")")[0]
                            parts = [int(x.strip()) for x in inside.split(",")]
                            spins = self.widget_bg_spins.get(wname)
                            if spins and len(parts) == 4:
                                for s,v in zip(spins, parts):
                                    s.setValue(v)
                        except Exception:
                            pass
                bg = params.get("bg")
                if bg:
                    try:
                        inside = bg.split("(",1)[1].split(")")[0]
                        parts = [int(x.strip()) for x in inside.split(",")]
                        if len(parts) == 4:
                            self.spin_r.setValue(parts[0])
                            self.spin_g.setValue(parts[1])
                            self.spin_b.setValue(parts[2])
                            self.spin_a.setValue(parts[3])
                    except Exception:
                        pass
                # načítaj skratku
                self.shortcut_field.setText(params.get("shortcut", ""))
            finally:
                self._suppress_widget_updates = False

        def refresh_overlay_list(self):
            self.overlay_list.clear()
            mgr = overlay_manager.start_overlay_manager()
            self.custom_overlays = load_custom_overlays(self.module_name)
            for cname, params in self.custom_overlays.items():
                name = f"{self.module_name}:{cname}"
                if name in mgr.overlays:
                    win = mgr.overlays[name]
                    state_icon = "✅ " if getattr(win, 'user_visible', True) else "❌ "
                else:
                    state_icon = "✅ " if params.get('user_visible', True) else "❌ "
                item = QListWidgetItem(state_icon + cname)
                item.setData(Qt.UserRole, cname)
                self.overlay_list.addItem(item)

        def create_overlay(self):
            base_name, idx = "Overlay", 1
            while f"{base_name}_{idx}" in self.custom_overlays:
                idx += 1
            name = f"{base_name}_{idx}"
            widgets = []
            for i in range(self.widget_list.count()):
                it = self.widget_list.item(i)
                if it.checkState() == Qt.Checked:
                    widgets.append(it.data(Qt.UserRole))
            if not widgets:
                QMessageBox.warning(self, "Error", "Select at least one widget!")
                return
            params = get_default_overlay_params()
            params['widgets'] = widgets
            params['bg'] = self.get_overlay_bg()
            params['widget_bgs'] = {w: self.get_widget_bg(w) for w in widgets}
            params['user_visible'] = True
            params['shortcut'] = self.shortcut_field.text()
            self.custom_overlays[name] = params
            save_custom_overlays(self.module_name, self.custom_overlays)
            self.refresh_overlay_list()
            # Pridaj overlay len ak ešte nie je v manageri
            mgr = overlay_manager.start_overlay_manager()
            full_name = f"{self.module_name}:{name}"
            if full_name not in mgr.overlays:
                build_overlay_window(name, params, BaseClass, self.module_name)
            # zaregistruj skratku
            if params['shortcut']:
                active_shortcuts[full_name] = params['shortcut']

        def on_select_overlay(self):
            items = self.overlay_list.selectedItems()
            self.selected_overlay = items[0].data(Qt.UserRole) if items else None
            self.refresh_widget_list_from_json(self.selected_overlay)
            if self.selected_overlay:
                params = self.custom_overlays.get(self.selected_overlay, {})
                self.shortcut_field.setText(params.get("shortcut", ""))

        def delete_selected_overlay(self):
            if not self.selected_overlay:
                return
            if self.selected_overlay in self.custom_overlays:
                del self.custom_overlays[self.selected_overlay]
                save_custom_overlays(self.module_name, self.custom_overlays)
            mgr = overlay_manager.start_overlay_manager()
            full_name = f"{self.module_name}:{self.selected_overlay}"
            if full_name in mgr.overlays:
                mgr.remove_overlay(full_name)
            # odstráň skratku
            if full_name in active_shortcuts:
                del active_shortcuts[full_name]
            self.refresh_overlay_list()

        def toggle_selected_overlay(self):
            items = self.overlay_list.selectedItems()
            if not items:
                return
            cname = items[0].data(Qt.UserRole)
            mgr = overlay_manager.start_overlay_manager()
            full_name = f"{self.module_name}:{cname}"
            if full_name in mgr.overlays:
                win = mgr.overlays[full_name]
                new_state = not getattr(win, 'user_visible', True)
                win.user_visible = new_state
                try:
                    win.set_overlay_visible(new_state and mgr.global_show)
                except Exception:
                    win.setVisible(new_state and mgr.global_show)
            self.custom_overlays = load_custom_overlays(self.module_name)
            if cname in self.custom_overlays:
                self.custom_overlays[cname]['user_visible'] = not self.custom_overlays[cname].get('user_visible', True)
                save_custom_overlays(self.module_name, self.custom_overlays)
            self.refresh_overlay_list()

        def update_widget_bg(self, widget_name):
            if self._suppress_widget_updates:
                return
            if not self.selected_overlay:
                return
            params = self.custom_overlays.get(self.selected_overlay)
            if params is None:
                params = get_default_overlay_params()
                self.custom_overlays[self.selected_overlay] = params
            rgba = self.get_widget_bg(widget_name)
            if 'widget_bgs' not in params:
                params['widget_bgs'] = {}
            params['widget_bgs'][widget_name] = rgba
            save_custom_overlays(self.module_name, self.custom_overlays)
            mgr = overlay_manager.start_overlay_manager()
            full_name = f"{self.module_name}:{self.selected_overlay}"
            if full_name in mgr.overlays:
                win = mgr.overlays[full_name]
                try:
                    child = win.findChild(QWidget, widget_name)
                    if child is not None:
                        child.setStyleSheet(f"background-color: {rgba}; border: none;")
                except Exception:
                    try:
                        for child in win.findChildren(QWidget):
                            if child.objectName() == widget_name:
                                child.setStyleSheet(f"background-color: {rgba}; border: none;")
                                break
                    except Exception:
                        pass
        
        def update_overlay_bg(self, _val=None):
            if self._suppress_widget_updates:
                return
            if not self.selected_overlay:
                return
            r = int(self.spin_r.value())
            g = int(self.spin_g.value())
            b = int(self.spin_b.value())
            a = self.spin_a.value()
            if RGBA_MODE == "int":
                rgba_str = f"rgba({r},{g},{b},{a})"
            else:
                rgba_str = f"rgba({r},{g},{b},{round(a/255.0, 3)})"
            params = self.custom_overlays.get(self.selected_overlay)
            if params is None:
                params = get_default_overlay_params()
                self.custom_overlays[self.selected_overlay] = params
            params['bg'] = rgba_str
            save_custom_overlays(self.module_name, self.custom_overlays)
            mgr = overlay_manager.start_overlay_manager()
            full_name = f"{self.module_name}:{self.selected_overlay}"
            if full_name in mgr.overlays:
                win = mgr.overlays[full_name]
                try:
                    win.params['bg'] = rgba_str
                except Exception:
                    try:
                        win.params = dict(win.params or {})
                        win.params['bg'] = rgba_str
                    except Exception:
                        pass
                root = getattr(win, "_overlay_root", None)
                if root is not None:
                    try:
                        root.setStyleSheet(f"background-color: {rgba_str}; border: none;")
                    except Exception:
                        try:
                            root.setStyleSheet(f"background-color: {rgba_str}; border: none;")
                        except Exception:
                            pass
                try:
                    win.setStyleSheet(f"background-color: {rgba_str}; border: none;")
                except Exception:
                    try:
                        win.setStyleSheet(f"background-color: {rgba_str}; border: none;")
                    except Exception:
                        pass

    return CustomOverlaysWidget()

def get_widget_dock_position():
    return Qt.RightDockWidgetArea, 1

