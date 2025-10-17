# /////////////////////////////////////////////////////////////////////////////////////////////
# ////---- Importovanie potrebných knižníc, cesty k súborom a nastavenia ----////
# /////////////////////////////////////////////////////////////////////////////////////////////
import sqlite3
import time
import configparser
import os
import platform
from datetime import datetime

# ////---- Cesty k súborom ----////
module_root = os.path.dirname(os.path.dirname(__file__))
data_path = os.path.join(module_root, 'data', 'data.ini')
path_ini_path = os.path.join(module_root, 'config' ,'path.ini')

# ////-----------------------------------------------------------------------------------------

# ////---- Logovanie do konzoly ----////
def log_to_console(message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {message}\n"
    print(line, end='')

# ////-----------------------------------------------------------------------------------------

# ////---- Automatická detekcia cesty k SCUM.db ----////
def detect_db_path():
    import configparser
    config = configparser.ConfigParser()
    if os.path.exists(path_ini_path):
        config.read(path_ini_path)
        if 'paths' in config and 'db_path' in config['paths']:
            db_path = config['paths']['db_path']
            if os.path.exists(db_path):
                return db_path

    # Pokus o automatickú detekciu
    system = platform.system()
    if system == 'Windows':
        default_win = os.path.expandvars(r"%LOCALAPPDATA%\SCUM\Saved\SaveFiles\SCUM.db")
        if os.path.exists(default_win):
            return default_win
    elif system == 'Linux':
        candidates = [
            os.path.expanduser("~/Steam/steamapps/compatdata/513710/pfx/drive_c/users/steamuser/AppData/Local/SCUM/Saved/SaveFiles/SCUM.db"),
            os.path.expanduser("~/.var/app/com.valvesoftware.Steam/.steam/steam/steamapps/compatdata/513710/pfx/drive_c/users/steamuser/AppData/Local/SCUM/Saved/SaveFiles/SCUM.db")
        ]
        for path in candidates:
            if os.path.exists(path):
                return path

    log_to_console("[Weather] SCUM.db nebol nájdený. Prosím zadajte cestu ručne do path.ini")
    return None

# ////-----------------------------------------------------------------------------------------

# ////---- Zabezpečenie indexov pre weather_parameters a entity ----////
def ensure_indexes(conn):
    try:
        cursor = conn.cursor()
        # entity - pre detekciu aktívneho hráča
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entity_flags ON entity(flags);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entity_entity_system_id ON entity(entity_system_id);")

        # entity_system
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entity_system_id ON entity_system(id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entity_system_user_profile_id ON entity_system(user_profile_id);")

        # weather_parameters - pre rýchle vyhľadanie
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_weather_user_profile_id ON weather_parameters(user_profile_id);")
        conn.commit()
    except sqlite3.Error as e:
        log_to_console(f"[Weather] Chyba pri vytváraní indexov: {e}")

# ////-----------------------------------------------------------------------------------------

# ////---- Otvorenie spojenia s databázou ----////
def open_db_connection(db_path):
    try:
        conn = sqlite3.connect(db_path, timeout=1)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA locking_mode=NORMAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA read_uncommitted = true;")
        conn.row_factory = sqlite3.Row
        ensure_indexes(conn)
        return conn
    except sqlite3.Error as e:
        log_to_console(f"[Weather] Chyba pri otváraní databázy: {e}")
        return None

# ////-----------------------------------------------------------------------------------------

# ////---- Zatvorenie spojenia s databázou ----////
def close_db_connection(conn):
    if conn:
        try:
            conn.close()
        except sqlite3.Error as e:
            log_to_console(f"[Weather] Chyba pri zatváraní databázy: {e}")

# ////-----------------------------------------------------------------------------------------

# ////---- Získanie aktívneho user_profile_id hráča (flag=0) ----////
def get_active_user_profile_id(conn):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT entity_system_id
        FROM entity
        WHERE class = 'FPrisonerEntity' AND flags = 0
    """)
    row = cursor.fetchone()
    if not row:
        return None
    entity_system_id = row['entity_system_id']

    cursor.execute("""
        SELECT user_profile_id
        FROM entity_system
        WHERE id = ?
    """, (entity_system_id,))
    result = cursor.fetchone()
    return result['user_profile_id'] if result else None

# ////-----------------------------------------------------------------------------------------

# ////---- Získanie time_of_day pre konkrétneho hráča ----////
def get_time_of_day(conn, user_profile_id):
    if not user_profile_id:
        return None
    cursor = conn.cursor()
    cursor.execute("""
        SELECT time_of_day
        FROM weather_parameters
        WHERE user_profile_id = ?
    """, (user_profile_id,))
    row = cursor.fetchone()
    return row['time_of_day'] if row else None

# ////-----------------------------------------------------------------------------------------

# ////---- Premena float času na 00:00-23:59 hodiny a minúty ----////
def convert_float_time_to_hm(time_float):
    if time_float is None:
        return 0, 0
    time_float = round(time_float, 2) # Zaokrúhlenie na 2 desatinné miesta

    hours = int(time_float)
    minutes = int(round((time_float - hours) * 60))

    # Drobné korekcie
    if minutes == 60:
        minutes = 59
    if hours == 24:
        hours = 0
    return hours, minutes

# ////-----------------------------------------------------------------------------------------

def detect_ss_path():
    #Automatická detekcia ServerSettings.ini podobne ako detect_db_path()
    config = configparser.ConfigParser()
    ss_path = None

    # 1️⃣ Skús path.ini
    path_ini_path = os.path.join(module_root, 'config', 'path.ini')
    if os.path.exists(path_ini_path):
        config.read(path_ini_path)
        if 'paths' in config and 'ss_path' in config['paths']:
            candidate = config['paths']['ss_path']
            if os.path.exists(candidate):
                return candidate

    # 2️⃣ Defaultné cesty podľa OS
    system = platform.system()
    candidates = []
    if system == "Windows":
        candidates.append(os.path.expandvars(r"%LOCALAPPDATA%/SCUM/Saved/Config/WindowsNoEditor/ServerSettings.ini"))
    elif system == "Linux":
        candidates.append(os.path.expanduser("~/Steam/steamapps/compatdata/513710/pfx/drive_c/users/steamuser/AppData/Local/SCUM/Config/WindowsNoEditor/ServerSettings.ini"))
        candidates.append(os.path.expanduser("~/.var/app/com.valvesoftware.Steam/.steam/steam/steamapps/compatdata/513710/pfx/drive_c/users/steamuser/AppData/Local/SCUM/Config/WindowsNoEditor/ServerSettings.ini"))

    # 3️⃣ Ak je databáza dostupná, posun sa z jej cesty
    db_path = detect_db_path()
    if db_path:
        save_root = os.path.dirname(os.path.dirname(db_path))
        candidates.append(os.path.join(save_root, "Config", "WindowsNoEditor", "ServerSettings.ini"))

    # 4️⃣ Prejdi kandidátov
    for path in candidates:
        if os.path.exists(path):
            return path

    # Ak sa nenašlo nič
    log_to_console("[Weather] ServerSettings.ini nenájdené. Prosím zadajte cestu ručne do config/path.ini")
    return None

# ////---- Načítanie TimeOfDaySpeed zo ServerSettings.ini ----////
def get_time_of_day_speed():
    """
    Načíta scum.TimeOfDaySpeed zo ServerSettings.ini
    """
    ss_path = detect_ss_path()
    if not ss_path or not os.path.exists(ss_path):
        return None

    try:
        config = configparser.ConfigParser(strict=False)
        config.read(ss_path)

        time_speed = None
        if 'World' in config and 'scum.TimeOfDaySpeed' in config['World']:
            time_speed = float(config['World']['scum.TimeOfDaySpeed'])
    except Exception as e:
        log_to_console(f"[Weather] Chyba pri čítaní TimeOfDaySpeed: {e}")

    return time_speed

# ////---- Zápis času a rýchlosti do data.ini ----////
def write_time_to_ini(time_float, hours, minutes):
    """
    Zapíše čas do data.ini v sekcii [Time]:
    time_of_day = float
    hours = int
    minutes = int
    time_speed = float
    """
    config = configparser.ConfigParser()
    if os.path.exists(data_path):
        config.read(data_path)

    if 'Time' not in config:
        config['Time'] = {}

    config['Time']['time_of_day'] = str(time_float)
    config['Time']['hours'] = str(hours)
    config['Time']['minutes'] = str(minutes)

    # načítanie rýchlosti z ServerSettings.ini
    speed = get_time_of_day_speed()
    if speed is not None:
        config['Time']['time_speed'] = str(speed)

    with open(data_path, 'w') as f:
        config.write(f)

# ////-----------------------------------------------------------------------------------------

# ////---- Hlavná slučka ----////
def main_loop(conn=None, stop_event=None):
    while not (stop_event and stop_event.is_set()):
        try:
            user_profile_id = get_active_user_profile_id(conn)
            time_of_day = get_time_of_day(conn, user_profile_id)
            hours, minutes = convert_float_time_to_hm(time_of_day)
            write_time_to_ini(time_of_day,hours, minutes)
        except Exception as e:
            log_to_console(f"[Weather] Chyba: {e}")

        if stop_event and stop_event.is_set():
            break
        time.sleep(1)

# ////-----------------------------------------------------------------------------------------

# ////---- Spustenie logiky ----////
def logic_main_init(stop_event=None):
    db_path = detect_db_path()
    if not db_path or not os.path.exists(db_path):
        log_to_console("[Weather] SCUM.db file not found or disk disconnected. Please enter the path manually in config/path.ini")
        return

    conn = open_db_connection(db_path)
    if not conn:
        return

    main_loop(conn, stop_event)
    close_db_connection(conn)

# ////-----------------------------------------------------------------------------------------

# ////---- Spustenie priamo ----////
if __name__ == "__main__":
    logic_main_init()

