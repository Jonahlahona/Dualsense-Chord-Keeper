import os, sys, logging, traceback, threading, winreg, winreg

VERSION = "1.5.9"

def get_data_dir():
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
    else:
        exe_dir = os.path.dirname(os.path.abspath(__file__))
        
    if os.path.exists(os.path.join(exe_dir, "portable.txt")):
        path = os.path.join(exe_dir, "data")
        os.makedirs(path, exist_ok=True)
        return path

    appdata = os.environ.get('APPDATA')
    if not appdata: appdata = os.path.expanduser('~')
    path = os.path.join(appdata, "DualSenseChordKeeper")
    os.makedirs(path, exist_ok=True)
    return path

data_dir = get_data_dir()
log_file = os.path.join(data_dir, 'dualsense_chord_keeper.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)-8s  %(message)s',
    handlers=[logging.FileHandler(log_file, mode='w', encoding='utf-8'), logging.StreamHandler()]
)
logging.info(f"--- Booting DualSense Chord Keeper {VERSION} ---")

def _global_exception_handler(exc_type, exc_value, exc_traceback):
    logging.critical("Uncaught Exception:", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = _global_exception_handler

try:
    import webview
    import time, ctypes, json
    from PIL import Image, ImageDraw
    import pystray
    import hidapi
    from pydualsense import pydualsense
    logging.info("Core libraries imported successfully")
except Exception as e:
    logging.critical(f"FATAL: Failed to import libraries: {e}")
    logging.critical(traceback.format_exc())
    sys.exit(1)


# Enable High DPI awareness
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1) # PROCESS_SYSTEM_DPI_AWARE
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

class CustomDS(pydualsense):
    def __init__(self, target_path, **kwargs):
        self.target_path = target_path
        super().__init__(**kwargs)
        
    def _pydualsense__find_device(self):
        devices = hidapi.enumerate(vendor_id=0x054C)
        for device in devices:
            if device.path == self.target_path:
                dual_sense = hidapi.Device(path=device.path)
                return dual_sense, device.product_id == 0x0DF2
        raise Exception("Device not found")

def get_base_path():
    if hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

base_path = get_base_path()
# UI files are in 'ui' subfolder relative to base_path (or sys._MEIPASS)
config_html       = os.path.join(base_path, 'ui', 'config.html')
notification_html = os.path.join(base_path, 'ui', 'notification.html')
_config_file      = os.path.join(data_dir,  'profiles.json')


# ── Structs ───────────────────────────────────────────────────────────────────

class _RECT(ctypes.Structure):
    _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                ('right', ctypes.c_long), ('bottom', ctypes.c_long)]

OVERLAY_W = 340
OVERLAY_H = 200
MARGIN    = 10

user32 = ctypes.WinDLL("user32")
dwmapi = ctypes.WinDLL("dwmapi")


def _get_corner_pos(corner='bottom-right', hwnd=None, custom_off_x=None, custom_off_y=None):
    """Compute physical (x, y) coordinates using direct window measurement."""
    # Get monitor info for the specific monitor
    # Use 1 (MONITOR_DEFAULTTOPRIMARY) if hwnd is 0 or invalid
    try:
        monitor = user32.MonitorFromWindow(hwnd or 0, 1) 
    except:
        monitor = 0
        
    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_ulong), ("rcMonitor", _RECT),
                    ("rcWork", _RECT), ("dwFlags", ctypes.c_ulong)]
                    
    mi = MONITORINFO()
    mi.cbSize = ctypes.sizeof(MONITORINFO)
    if not monitor or not user32.GetMonitorInfoW(monitor, ctypes.byref(mi)):
        # Absolute fallback to standard primary monitor 1920x1080 work area
        logging.warning("Failed to get monitor info, using fallback 1920x1080")
        wa = _RECT(0, 0, 1920, 1040)
    else:
        wa = mi.rcWork # Physical work area

    # Measure the actual window if possible
    ww, wh = OVERLAY_W, OVERLAY_H
    off_x, off_y = 0, 0
    
    if hwnd and user32.IsWindow(hwnd):
        rect = _RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        
        # Extended frame bounds (shadows)
        vis = _RECT()
        try:
            dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(vis), ctypes.sizeof(vis))
            ww = vis.right - vis.left
            wh = vis.bottom - vis.top
            off_x = vis.left - rect.left
            off_y = vis.top - rect.top
        except:
            ww = rect.right - rect.left
            wh = rect.bottom - rect.top

    # Priority: 1. Passed overrides, 2. Global settings
    off_user_x, off_user_y = 0, 0
    if custom_off_x is not None and custom_off_y is not None:
        off_user_x, off_user_y = custom_off_x, custom_off_y
    else:
        try:
            config = _load_config()
            settings = config.get('settings', {})
            off_user_x = int(settings.get('offsetX', 0))
            off_user_y = int(settings.get('offsetY', 0))
        except: pass

    # Calculate desired PHYSICAL top-left (vx, vy)
    if corner == 'top-left':
        vx, vy = wa.left + MARGIN, wa.top + MARGIN
    elif corner == 'top-right':
        vx, vy = wa.right - ww - MARGIN, wa.top + MARGIN
    elif corner == 'bottom-left':
        vx, vy = wa.left + MARGIN, wa.bottom - wh - MARGIN
    else:  # bottom-right
        vx, vy = wa.right - ww - MARGIN, wa.bottom - wh - MARGIN
        
    final_x, final_y = vx - off_x + off_user_x, vy - off_y + off_user_y
    logging.info(f'[{corner}] WA({wa.left},{wa.top},{wa.right},{wa.bottom}) Window({ww}x{wh}) UserOff({off_user_x},{off_user_y}) -> Final({final_x},{final_y})')
    return (final_x, final_y)


def _load_config():
    try:
        with open(_config_file, 'r') as f:
            return json.load(f)
    except:
        return {}

def _save_config(config):
    try:
        with open(_config_file, 'w') as f:
            json.dump(config, f, indent=4)
    except:
        logging.exception("Failed to save config")

def _read_corner_setting():
    config = _load_config()
    return config.get('settings', {}).get('notificationCorner', 'bottom-right')

# Default bottom-right; the actual corner is applied dynamically at show-time
_INIT_X, _INIT_Y = _get_corner_pos(_read_corner_setting())

# Win32 HWND — filled in once the overlay page loads
_overlay_hwnd = [0]


# ── HWND helpers ──────────────────────────────────────────────────────────────

def _find_overlay_hwnd():
    pid    = os.getpid()
    found  = [0]
    _CB_T  = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    user32 = ctypes.WinDLL("user32")

    @_CB_T
    def _cb(hwnd, _):
        wpid = ctypes.c_ulong(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
        if wpid.value != pid:
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        if n:
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            if 'Overlay' in buf.value:
                found[0] = hwnd
                return False
        return True

    user32.EnumWindows(_cb, None)
    return found[0]


def _win32_show(hwnd):
    user32 = ctypes.WinDLL("user32")
    corner = _read_corner_setting()
    px, py = _get_corner_pos(corner, hwnd=hwnd)
    logging.debug(f'Showing overlay at {corner}: Physical({px}, {py})')
    
    # Show No-Activate
    user32.ShowWindow(hwnd, 8) 
    # Physical move + Topmost
    user32.SetWindowPos(hwnd, -1, px, py, 0, 0, 0x0010 | 0x0001)


def _win32_hide(hwnd):
    ctypes.WinDLL("user32").ShowWindow(hwnd, 0)


# ── Overlay drag prevention (WM_NCHITTEST subclass) ───────────────────────────
# On 64-bit Windows WPARAM/LPARAM are pointer-sized — use c_size_t/c_ssize_t,
# not c_ulong/c_long which are 32-bit on Windows and cause stack corruption.
_WNDPROC_T = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t,  # LRESULT
    ctypes.c_void_p,   # HWND
    ctypes.c_uint,     # UINT msg
    ctypes.c_size_t,   # WPARAM (pointer-sized unsigned)
    ctypes.c_ssize_t,  # LPARAM (pointer-sized signed)
)

_overlay_wndproc_ref = [None]  # keeps the ctypes callable alive (prevents GC crash)
_old_overlay_wndproc = [None]

WM_NCHITTEST  = 0x0084
WM_LBUTTONUP  = 0x0202
HTCLIENT      = 1

def _install_overlay_wndproc(hwnd):
    user32 = ctypes.WinDLL("user32")
    
    try:
        GetWindowLongPtrW = user32.GetWindowLongPtrW
        SetWindowLongPtrW = user32.SetWindowLongPtrW
    except AttributeError:
        GetWindowLongPtrW = user32.GetWindowLongW
        SetWindowLongPtrW = user32.SetWindowLongW

    GetWindowLongPtrW.restype  = ctypes.c_void_p
    GetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int]
    SetWindowLongPtrW.restype  = ctypes.c_void_p
    SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
    
    CallWindowProcW = user32.CallWindowProcW
    CallWindowProcW.restype    = ctypes.c_ssize_t
    CallWindowProcW.argtypes   = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint,
        ctypes.c_size_t, ctypes.c_ssize_t,
    ]

    old = GetWindowLongPtrW(hwnd, -4)  # GWLP_WNDPROC
    if not old:
        logging.warning('_install_overlay_wndproc: no existing WNDPROC found')
        return
    _old_overlay_wndproc[0] = old

    def _proc(hwnd_, msg, wparam, lparam):
        try:
            if msg == WM_NCHITTEST:
                return HTCLIENT  # block dragging; position is corner-locked
            
            if msg == WM_LBUTTONUP:
                threading.Thread(target=api.dismiss_notification, daemon=True).start()
                
            return CallWindowProcW(old, hwnd_, msg, wparam, lparam)
        except Exception:
            logging.exception("Error in overlay WNDPROC")
            return 0

    proc = _WNDPROC_T(_proc)
    _overlay_wndproc_ref[0] = proc  # must stay referenced
    SetWindowLongPtrW(hwnd, -4, ctypes.cast(proc, ctypes.c_void_p))
    logging.debug('_install_overlay_wndproc: installed, hwnd=%s', hwnd)


# ── Startup Registry ──────────────────────────────────────────────────────────

def _get_exe_path():
    if getattr(sys, 'frozen', False):
        return sys.executable
    return os.path.abspath(__file__)

def _is_startup_enabled():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
        value, _ = winreg.QueryValueEx(key, "DualSenseChordKeeper")
        winreg.CloseKey(key)
        return value == _get_exe_path()
    except OSError:
        return False

def _set_startup_enabled(enable):
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
        if enable:
            winreg.SetValueEx(key, "DualSenseChordKeeper", 0, winreg.REG_SZ, _get_exe_path())
        else:
            try:
                winreg.DeleteValue(key, "DualSenseChordKeeper")
            except OSError:
                pass
        winreg.CloseKey(key)
        return True
    except Exception as e:
        logging.error(f"Failed to toggle startup: {e}")
        return False
# ── API ───────────────────────────────────────────────────────────────────────

class Api:
    def __init__(self):
        self._hide_timer    = None

    def get_connected_controllers(self):
        devices = []
        try:
            for d in hidapi.enumerate(vendor_id=0x054C):
                if d.product_id in (0x0CE6, 0x0DF2):
                    mac = d.serial_number
                    if not mac:
                        mac = "Unknown"
                    elif len(mac) == 12: # Add colons to MAC
                        mac = ":".join(mac[i:i+2] for i in range(0, 12, 2)).upper()
                    # Keep path as string, path is a bytes object
                    devices.append({"path": d.path.decode('utf-8') if isinstance(d.path, bytes) else str(d.path), "mac": mac})
        except Exception:
            logging.exception("Failed to enumerate connected controllers")
        return devices

    def show_notification(self, profiles_json):
        global overlay_window
        if not overlay_window:
            return

        duration = 8.0
        try:
            config_str = self.load_config()
            if config_str:
                parsed = json.loads(config_str)
                if isinstance(parsed, dict) and "settings" in parsed:
                    duration = float(parsed["settings"].get("duration", 8.0))
        except Exception:
            pass

        try:
            profiles = json.loads(profiles_json) if isinstance(profiles_json, str) else profiles_json
        except Exception:
            logging.exception('show_notification: failed to parse profiles')
            return

        # Resolve profile-specific offsets
        try:
            config = _load_config()
            settings = config.get('settings', {})
            corner = settings.get('notificationCorner', 'bottom-right')
            
            # Find active profile to get its offsets
            active_id = config.get('activeProfileId')
            profiles_list = config.get('profileList', [])
            active_profile = next((p for p in profiles_list if str(p.get('id')) == str(active_id)), profiles_list[0] if profiles_list else {})
            
            off_x = active_profile.get('offsetX', settings.get('offsetX', 0))
            off_y = active_profile.get('offsetY', settings.get('offsetY', 0))
        except:
            corner = 'bottom-right'
            off_x, off_y = 0, 0

        hwnd = _overlay_hwnd[0]
        if hwnd:
            # Position at the correct corner with profile offsets
            px, py = _get_corner_pos(corner, hwnd=hwnd, custom_off_x=off_x, custom_off_y=off_y)
            user32.ShowWindow(hwnd, 8) 
            user32.SetWindowPos(hwnd, -1, px, py, 0, 0, 0x0010 | 0x0001)
        else:
            overlay_window.show()

        try:
            overlay_window.evaluate_js(
                f"window.triggerGlobalNotification({json.dumps(profiles)})"
            )
        except Exception as e:
            logging.error(f"show_notification evaluate_js error: {e}")

        self._fade_cancelled = True
        h = _overlay_hwnd[0]
        if h:
            try:
                ctypes.WinDLL("user32").SetLayeredWindowAttributes(h, 0, 255, 2)
            except Exception: pass

        def _hide():
            h = _overlay_hwnd[0]
            if h:
                _win32_hide(h)
            elif overlay_window:
                overlay_window.hide()
                
        def _fade_out_and_hide():
            h = _overlay_hwnd[0]
            if h:
                user32 = ctypes.WinDLL("user32")
                for i in range(15, -1, -1):
                    if getattr(self, '_fade_cancelled', False):
                        user32.SetLayeredWindowAttributes(h, 0, 255, 2)
                        return
                    alpha = int((i / 15.0) * 255)
                    user32.SetLayeredWindowAttributes(h, 0, alpha, 2)
                    time.sleep(0.02)
                _win32_hide(h)
                user32.SetLayeredWindowAttributes(h, 0, 255, 2)
            elif overlay_window:
                overlay_window.hide()

        def _start_fade():
            self._fade_cancelled = False
            if overlay_window:
                overlay_window.evaluate_js("document.body.classList.add('fading-out')")
            t = threading.Thread(target=_fade_out_and_hide, daemon=True)
            self._fade_thread = t
            t.start()

        self._hide_timer = threading.Timer(duration, _start_fade)
        self._hide_timer.daemon = True
        self._hide_timer.start()

    def dismiss_notification(self):
        logging.debug('dismiss_notification called')
        if self._hide_timer and self._hide_timer.is_alive():
            self._hide_timer.cancel()
        self._fade_cancelled = True
        h = _overlay_hwnd[0]
        if h:
            _win32_hide(h)
            try:
                ctypes.WinDLL("user32").SetLayeredWindowAttributes(h, 0, 255, 2)
            except Exception: pass
        elif overlay_window:
            overlay_window.hide()

    def get_notification_corner(self):
        return _read_corner_setting()

    def set_notification_corner(self, corner):
        # Show preview at the new corner with profile-specific offsets
        config = _load_config()
        active_id = config.get('activeProfileId')
        profiles = config.get('profileList', [])
        active_profile = next((p for p in profiles if str(p.get('id')) == str(active_id)), profiles[0] if profiles else {})
        off_x = active_profile.get('offsetX', config.get('settings', {}).get('offsetX', 0))
        off_y = active_profile.get('offsetY', config.get('settings', {}).get('offsetY', 0))

        h = _overlay_hwnd[0]
        if h:
            x, y = _get_corner_pos(corner, hwnd=h, custom_off_x=off_x, custom_off_y=off_y)
            overlay_window.move(x, y)
            ctypes.WinDLL("user32").ShowWindow(h, 8) # Show NA
            # Ensure it's on top
            ctypes.WinDLL("user32").SetWindowPos(h, -1, 0, 0, 0, 0, 0x0010 | 0x0001 | 0x0002)
            # Auto-hide after 2s
            threading.Timer(2.0, lambda: ctypes.WinDLL("user32").ShowWindow(h, 0)).start()

    def load_config(self):
        try:
            with open(_config_file) as f:
                return f.read()
        except Exception:
            return None

    def save_config(self, config_json):
        try:
            # Merge settings if only partial config provided (to prevent clobbering)
            new_data = json.loads(config_json)
            try:
                with open(_config_file, 'r') as f:
                    old_data = json.load(f)
                # If new_data only has settings and not profileList, merge it
                if 'settings' in new_data and 'profileList' not in new_data:
                    old_data['settings'] = new_data['settings']
                    new_data = old_data
            except: pass

            with open(_config_file, 'w') as f:
                json.dump(new_data, f, indent=4)
            logging.debug('save_config: successful')
        except Exception:
            logging.exception('save_config: failed')

    def get_startup_status(self):
        return _is_startup_enabled()

    def toggle_startup(self, enable):
        return _set_startup_enabled(enable)


api = Api()

config_window = webview.create_window(
    'DualSense Chord Keeper - Config', config_html,
    width=1024, height=768, js_api=api,
)
overlay_window = webview.create_window(
    'DualSense Chord Keeper - Overlay', notification_html,
    frameless=True, on_top=True,
    width=OVERLAY_W, height=OVERLAY_H,
    x=_INIT_X, y=_INIT_Y,
)

# Removed api window properties to prevent logger recursion bugs


def on_config_closing():
    config_window.hide()
    return False

config_window.events.closing += on_config_closing


_overlay_ready = False

def on_overlay_loaded():
    global _overlay_ready
    if _overlay_ready:
        return
    _overlay_ready = True

    def _setup():
        hwnd = 0
        for _ in range(20):
            hwnd = _find_overlay_hwnd()
            if hwnd:
                break
            time.sleep(0.3)

        if not hwnd:
            return

        _overlay_hwnd[0] = hwnd
        user32 = ctypes.WinDLL("user32")

        # Use the corner setting to compute position
        corner = _read_corner_setting()
        x, y = _get_corner_pos(corner)

        # WS_EX_TOOLWINDOW  — keep out of taskbar
        # WS_EX_NOACTIVATE  — never steals keyboard/mouse focus, even when clicked
        try:
            GetWindowLongW = user32.GetWindowLongW
            SetWindowLongW = user32.SetWindowLongW
        except AttributeError:
            pass

        style = user32.GetWindowLongW(hwnd, -20)
        # WS_EX_LAYERED = 0x00080000
        user32.SetWindowLongW(hwnd, -20, style | 0x00000080 | 0x08000000 | 0x00080000)

        try:
            SetLayeredWindowAttributes = user32.SetLayeredWindowAttributes
            SetLayeredWindowAttributes(hwnd, 0, 255, 2)
        except Exception:
            pass

        # Move to configured corner using pywebview API (SetWindowPos blocked by WebView2)
        overlay_window.move(x, y)

        _install_overlay_wndproc(hwnd)

        _win32_hide(hwnd)

    threading.Thread(target=_setup, daemon=True).start()

overlay_window.events.loaded += on_overlay_loaded


# ── Tray ──────────────────────────────────────────────────────────────────────

def _get_tray_image():
    icon_path = os.path.join(base_path, 'ui', 'DualsenseChordKeeper.png')
    if os.path.exists(icon_path):
        return Image.open(icon_path)
    # Fallback if image is missing
    img = Image.new('RGB', (64, 64), (30, 41, 59))
    ImageDraw.Draw(img).rectangle([16, 16, 48, 48], fill=(59, 130, 246))
    return img


def setup_tray():
    menu = pystray.Menu(
        pystray.MenuItem('Open Config', lambda: config_window.show(), default=True),
        pystray.MenuItem('Exit', lambda: os._exit(0)),
    )
    pystray.Icon('DualSenseChordKeeper', _get_tray_image(), 'DualSense Chord Keeper', menu).run()


# ── Entry ─────────────────────────────────────────────────────────────────────

def _dualsense_polling_loop():
    active_controllers = {}  # {path: {'ds': CustomDS, 'mac': str, 'last_trigger': float}}
    
    while True:
        try:
            # 1. Enumerate currently connected controllers
            current_paths = set()
            for d in hidapi.enumerate(vendor_id=0x054C):
                if d.product_id in (0x0CE6, 0x0DF2):
                    current_paths.add(d.path)
            
            # 2. Disconnect missing controllers
            for path in list(active_controllers.keys()):
                if path not in current_paths:
                    logging.info("Controller disconnected")
                    try:
                        active_controllers[path]['ds'].close()
                    except: pass
                    del active_controllers[path]
            
            # 3. Connect new controllers
            for d in hidapi.enumerate(vendor_id=0x054C):
                if d.product_id in (0x0CE6, 0x0DF2) and d.path not in active_controllers:
                    try:
                        mac = d.serial_number
                        if not mac: mac = "Unknown"
                        elif len(mac) == 12: mac = ":".join(mac[i:i+2] for i in range(0, 12, 2)).upper()
                        
                        ds = CustomDS(d.path)
                        ds.init()
                        active_controllers[d.path] = {'ds': ds, 'mac': mac, 'last_trigger': 0}
                        logging.info(f"Connected new DualSense controller: {mac}")
                    except Exception as e:
                        logging.error(f"Failed to connect to {d.path}: {e}")
                        
            # 4. Load config once per cycle
            trigger_type = "single"
            trigger_b1 = "PS"
            trigger_b2 = "Mute"
            parsed = {}
            
            config_str = api.load_config()
            if config_str:
                try:
                    parsed = json.loads(config_str)
                    if isinstance(parsed, dict) and "settings" in parsed:
                        settings = parsed["settings"]
                        trigger_type = settings.get("triggerType", trigger_type)
                        trigger_b1 = settings.get("triggerButton1", trigger_b1)
                        trigger_b2 = settings.get("triggerButton2", trigger_b2)
                except Exception as e:
                    logging.error(f"Failed to parse config in polling loop: {e}")
                    
            b1 = trigger_b1.lower()
            b2 = trigger_b2.lower()
            
            def is_pressed(ds, btn_name):
                state = ds.state
                if btn_name == 'mute': return state.micBtn
                if btn_name == 'ps': return state.ps
                if btn_name == 'create': return state.share
                if btn_name == 'options': return state.options
                if btn_name == 'triangle': return state.triangle
                if btn_name == 'circle': return state.circle
                if btn_name == 'cross': return state.cross
                if btn_name == 'square': return state.square
                if btn_name == 'l1': return state.L1
                if btn_name == 'r1': return state.R1
                if btn_name == 'l2': return state.L2
                if btn_name == 'r2': return state.R2
                if btn_name == 'touchpad': return state.touchBtn
                return False

            # 5. Poll each active controller
            now = time.time()
            for path, c in list(active_controllers.items()):
                try:
                    ds = c['ds']
                    pressed = False
                    if trigger_type == 'chord':
                        pressed = is_pressed(ds, b1) and is_pressed(ds, b2)
                    else:
                        pressed = is_pressed(ds, b2)
                        
                    if pressed and (now - c['last_trigger'] > 1.5):
                        c['last_trigger'] = now
                        mac = c['mac']
                        
                        # Resolve profile for this controller
                        profiles = []
                        if isinstance(parsed, dict):
                            settings = parsed.get("settings", {})
                            mappings = settings.get("controllerMappings", {})
                            
                            profile_list = parsed.get("profileList", [])
                            # Find assigned profile or fallback to active
                            target_id = mappings.get(mac)
                            if not target_id:
                                target_id = parsed.get("activeProfileId")
                                
                            active_profile = next((p for p in profile_list if str(p.get("id")) == str(target_id)), None)
                            if not active_profile and profile_list:
                                active_profile = profile_list[0]
                                
                            if active_profile:
                                profiles = active_profile.get("chords", [])
                        elif isinstance(parsed, list):
                            profiles = parsed
                            
                        api.show_notification(json.dumps(profiles))
                except OSError:
                    # Will be caught and disconnected on next loop
                    pass
            
            time.sleep(0.05)
            
        except Exception as e:
            logging.error(f"Error in polling loop: {e}")
            time.sleep(2.0)


if __name__ == '__main__':
    threading.Thread(target=_dualsense_polling_loop, daemon=True).start()
    threading.Thread(target=setup_tray, daemon=True).start()
    webview.start(gui='edgechromium')
