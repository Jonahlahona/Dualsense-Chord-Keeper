import webview
import os, sys, threading, time, ctypes, json, logging, traceback
from PIL import Image, ImageDraw
import pystray
import hidapi
from pydualsense import pydualsense

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


def get_data_dir():
    """Writable directory for logs and profiles."""
    app_name = "DualSenseChordKeeper"
    if hasattr(sys, '_MEIPASS'):
        base = os.path.dirname(sys.executable)
    else:
        # Project root (parent of src/)
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base, app_name)
    os.makedirs(path, exist_ok=True)
    return path


data_dir = get_data_dir()
log_file = os.path.join(data_dir, 'dualsense_chord_keeper.log')

logging.basicConfig(
    filename=log_file,
    level=logging.DEBUG,
    format='%(asctime)s  %(levelname)-8s  %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)

def _log_unhandled(exc_type, exc_value, exc_tb):
    logging.critical(
        'Unhandled exception:\n' + ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
    )
    sys.__excepthook__(exc_type, exc_value, exc_tb)

sys.excepthook = _log_unhandled

# Also catch exceptions on non-main threads
def _thread_excepthook(args):
    logging.critical(
        'Unhandled thread exception:\n' + ''.join(
            traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)
        )
    )

threading.excepthook = _thread_excepthook

logging.info('DualSense Chord Keeper starting up')


base_path         = get_base_path()
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
MARGIN    = 6
VERSION   = "1.3.6"

# Individual corner fine-tuning (X, Y)
CORNER_OFFSETS = {
    'top-left':      (0, 0),
    'top-right':     (-2, 0),
    'bottom-left':   (0, 0),
    'bottom-right':  (-2, -2)
}


def get_dpi_scale(hwnd):
    """Get the DPI scaling factor for the given window or system."""
    try:
        # GetDpiForWindow is available on Win10 1607+
        # If hwnd is 0 or invalid, it may return 0.
        val = 0
        if hwnd:
            try:
                val = ctypes.windll.user32.GetDpiForWindow(hwnd)
            except: pass
        
        if val == 0:
            try:
                val = ctypes.windll.user32.GetDpiForSystem()
            except: pass
            
        if val <= 0:
            return 1.0
            
        return val / 96.0
    except Exception:
        return 1.0


def _get_corner_pos(corner='bottom-right', hwnd=None):
    """Compute (x, y) for the overlay window origin using monitor-aware logical coordinates."""
    user32 = ctypes.WinDLL("user32")
    
    # Get monitor info for the specific monitor
    monitor = user32.MonitorFromWindow(hwnd or 0, 2) # MONITOR_DEFAULTTONEAREST
    
    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_ulong),
                    ("rcMonitor", _RECT),
                    ("rcWork", _RECT),
                    ("dwFlags", ctypes.c_ulong)]
                    
    mi = MONITORINFO()
    mi.cbSize = ctypes.sizeof(MONITORINFO)
    user32.GetMonitorInfoW(monitor, ctypes.byref(mi))
    
    # Physical work area
    p_wa = mi.rcWork
    
    # DPI Scaling: pywebview.move() expects LOGICAL pixels, but GetMonitorInfo returns PHYSICAL.
    # We must normalize by the DPI scale factor.
    scale = get_dpi_scale(hwnd)
    wa_l = p_wa.left / scale
    wa_t = p_wa.top / scale
    wa_r = p_wa.right / scale
    wa_b = p_wa.bottom / scale
    
    # Logical dimensions (pywebview constants)
    ww, wh = OVERLAY_W, OVERLAY_H
    
    # Shadow offset (logical)
    off_lx, off_ly = 0, 0
    
    if hwnd:
        dwmapi = ctypes.WinDLL("dwmapi")
        full = _RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(full))
        
        vis = _RECT()
        try:
            dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(vis), ctypes.sizeof(vis))
            # Convert physical offsets to logical
            off_lx = (vis.left - full.left) / scale
            off_ly = (vis.top - full.top) / scale
        except:
            pass

    # Calculate desired VISIBLE LOGICAL top-left (vx, vy)
    if corner == 'top-left':
        vx, vy = wa_l + MARGIN, wa_t + MARGIN
    elif corner == 'top-right':
        vx, vy = wa_r - ww - MARGIN, wa_t + MARGIN
    elif corner == 'bottom-left':
        vx, vy = wa_l + MARGIN, wa_b - wh - MARGIN
    else:  # bottom-right (default)
        vx, vy = wa_r - ww - MARGIN, wa_b - wh - MARGIN
        
    # Apply individual corner offsets
    ox, oy = CORNER_OFFSETS.get(corner, (0, 0))
    vx += ox
    vy += oy
        
    # Return the window ORIGIN (visible pos minus offset) in logical pixels
    final_x, final_y = int(vx - off_lx), int(vy - off_ly)
    logging.debug(f'Corner Pos [{corner}]: LogicalWA({wa_l},{wa_t},{wa_r},{wa_b}) Scale({scale}) -> Final({final_x},{final_y})')
    return (final_x, final_y)


def _read_corner_setting():
    """Read the notificationCorner from the config file."""
    try:
        with open(_config_file) as f:
            data = json.load(f)
        return data.get('settings', {}).get('notificationCorner', 'bottom-right')
    except Exception:
        return 'bottom-right'


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
    x, y = _get_corner_pos(corner, hwnd=hwnd)
    logging.debug(f'Showing overlay at {corner}: ({x}, {y})')
    
    # Move to the configured corner using pywebview's API
    # (pywebview handles logical/physical coordinate translation internally)
    try:
        overlay_window.move(x, y)
    except: pass
    
    # SW_SHOWNA (8) - Shows the window in its current size and position. The active window remains active.
    user32.ShowWindow(hwnd, 8)
    
    # Z-Order only (topmost). 0x0010 = NOACTIVATE, 0x0001 = NOSIZE, 0x0002 = NOMOVE
    user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0010 | 0x0001 | 0x0002)


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
        logging.debug('show_notification: %s', [p.get('button2') for p in profiles])

        overlay_window.evaluate_js(
            f"window.triggerGlobalNotification({json.dumps(profiles)})"
        )

        hwnd = _overlay_hwnd[0]
        if hwnd:
            _win32_show(hwnd)
        else:
            overlay_window.show()

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
        """Update corner in config and immediately preview the new position."""
        logging.debug('set_notification_corner: %s', corner)
        # Update config file
        try:
            config_str = self.load_config()
            data = json.loads(config_str) if config_str else {}
            if 'settings' not in data:
                data['settings'] = {}
            data['settings']['notificationCorner'] = corner
            self.save_config(json.dumps(data))
        except Exception:
            logging.exception('set_notification_corner: failed to save')
        # Preview: show the notification at the new corner for 2 seconds
        h = _overlay_hwnd[0]
        if h:
            x, y = _get_corner_pos(corner, hwnd=h)
            overlay_window.move(x, y)
            ctypes.WinDLL("user32").ShowWindow(h, 8) # Show NA
            ctypes.WinDLL("user32").SetWindowPos(h, -1, x, y, OVERLAY_W, OVERLAY_H, 0x0010)
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

def _create_tray_image():
    img = Image.new('RGB', (64, 64), (30, 41, 59))
    ImageDraw.Draw(img).rectangle([16, 16, 48, 48], fill=(59, 130, 246))
    return img


def setup_tray():
    menu = pystray.Menu(
        pystray.MenuItem('Open Config', lambda: config_window.show(), default=True),
        pystray.MenuItem('Exit', lambda: os._exit(0)),
    )
    pystray.Icon('DualSenseChordKeeper', _create_tray_image(), 'DualSense Chord Keeper', menu).run()


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
    webview.start(http_server=True, gui='edgechromium')
