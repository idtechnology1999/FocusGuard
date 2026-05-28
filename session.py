import threading
import time
import json
import os
import sys
from datetime import datetime
from blocker import block_sites, unblock_sites

_INSTALL_CONFIG = os.path.join(
    os.getenv("PROGRAMFILES", "C:\\Program Files"), "FocusGuard", "config.json"
)
if getattr(sys, 'frozen', False):
    _LOCAL_CONFIG = os.path.join(os.path.dirname(sys.executable), "config.json")
else:
    _LOCAL_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def _config_path() -> str:
    return _INSTALL_CONFIG if os.path.exists(_INSTALL_CONFIG) else _LOCAL_CONFIG


def _load_config():
    with open(_config_path()) as f:
        return json.load(f)


def _save_config(cfg):
    with open(_config_path(), "w") as f:
        json.dump(cfg, f, indent=4)


def get_active_session():
    """Return active session dict if one is saved and still running, else None."""
    try:
        cfg = _load_config()
        s = cfg.get("active_session")
        if not s:
            return None
        remaining = s["end_unix"] - time.time()
        if remaining > 0:
            return s
        # Expired — unblock and clear
        unblock_sites(s.get("sites") or [])
        cfg["active_session"] = None
        _save_config(cfg)
        return None
    except Exception:
        return None


class FocusSession:
    """
    Wall-clock based session: persists across reboots.
    remaining = end_unix - now, regardless of how long the system was off.
    """

    def __init__(self, duration_minutes=0, sites=None,
                 on_tick=None, on_end=None,
                 resume_end_unix=None, resume_duration_secs=None):
        self.sites    = sites or []
        self.on_tick  = on_tick
        self.on_end   = on_end
        self.active   = False
        self._thread  = None
        self.start_time = datetime.now()

        if resume_end_unix:
            self.end_unix      = resume_end_unix
            self.duration_secs = resume_duration_secs or max(1, int(resume_end_unix - time.time()))
        else:
            self.duration_secs = duration_minutes * 60
            self.end_unix      = time.time() + self.duration_secs

        self.remaining = max(0, int(self.end_unix - time.time()))

    @property
    def total_duration(self):
        return self.duration_secs

    def start(self, resume=False):
        """Start or resume the session."""
        self.active = True
        if not resume:
            block_sites(self.sites)
        self._persist()
        _register_startup()
        _register_watchdog()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        while self.active:
            time.sleep(1)
            self.remaining = max(0, int(self.end_unix - time.time()))
            if self.on_tick:
                self.on_tick(self.remaining)
            if self.remaining <= 0:
                break
        self._end_session()

    def _end_session(self):
        self.active = False
        unblock_sites(self.sites)
        self._clear_persisted()
        _unregister_startup()
        _unregister_watchdog()
        self._log_session()
        if self.on_end:
            self.on_end()

    def force_end(self):
        self.active = False

    def _persist(self):
        try:
            cfg = _load_config()
            cfg["active_session"] = {
                "end_unix":      self.end_unix,
                "duration_secs": self.duration_secs,
                "sites":         self.sites,
            }
            _save_config(cfg)
        except Exception:
            pass

    def _clear_persisted(self):
        try:
            cfg = _load_config()
            cfg["active_session"] = None
            _save_config(cfg)
        except Exception:
            pass

    def _log_session(self):
        elapsed = self.duration_secs - self.remaining
        entry = {
            "date":             self.start_time.strftime("%Y-%m-%d"),
            "start":            self.start_time.strftime("%H:%M:%S"),
            "duration_minutes": max(0, elapsed // 60),
        }
        try:
            cfg = _load_config()
            cfg.setdefault("session_log", []).append(entry)
            _save_config(cfg)
        except Exception:
            pass


# ── Windows startup registration ──────────────────────────────────────────────

def _startup_exe_path():
    # Always use the installed Program Files location — never the USB path.
    # If the session is started from the USB drive, sys.executable is the USB
    # path, which disappears after reboot. We must point to Program Files so
    # Focus Guard actually launches on next login.
    install_dir = os.path.join(os.getenv("PROGRAMFILES", "C:\\Program Files"), "FocusGuard")
    installed_exe = os.path.join(install_dir, "FocusGuard.exe")
    if os.path.exists(installed_exe):
        return installed_exe
    # Not installed yet — fall back to current executable
    if getattr(sys, 'frozen', False):
        return sys.executable
    return installed_exe


def _register_startup():
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "FocusGuard", 0, winreg.REG_SZ, _startup_exe_path())
        winreg.CloseKey(key)
    except Exception:
        pass


def _unregister_startup():
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE)
        try:
            winreg.DeleteValue(key, "FocusGuard")
        except FileNotFoundError:
            pass
        winreg.CloseKey(key)
    except Exception:
        pass


def _register_watchdog():
    """Task Scheduler task that re-launches FocusGuard every 5 min if killed."""
    import subprocess
    try:
        exe = _startup_exe_path()
        subprocess.run([
            "schtasks", "/create",
            "/tn", "FocusGuardWatchdog",
            "/tr", f'"{exe}"',
            "/sc", "minute",
            "/mo", "5",
            "/f",
            "/rl", "HIGHEST",
        ], capture_output=True, check=False, timeout=20)
    except Exception:
        pass


def _unregister_watchdog():
    import subprocess
    try:
        subprocess.run(
            ["schtasks", "/delete", "/tn", "FocusGuardWatchdog", "/f"],
            capture_output=True, check=False, timeout=10
        )
    except Exception:
        pass
