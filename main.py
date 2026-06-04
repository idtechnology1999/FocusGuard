import sys
import os
import ctypes
import json

from PySide6.QtWidgets import QApplication, QMessageBox

from installer import (is_installed, install_to_computer,
                       repair_if_needed, uninstall)
from usb_auth import detect_focus_guard_usb, register_device
from session import get_active_session
from blocker import block_sites
from gui import FocusGuardApp, WelcomeDialog

# Keep the mutex handle alive for the process lifetime — releasing it would
# allow a second instance to start.
_MUTEX = None


def _ensure_single_instance():
    """Exit silently if another instance of Focus Guard is already running."""
    global _MUTEX
    _MUTEX = ctypes.windll.kernel32.CreateMutexW(
        None, False, "Global\\FocusGuardSingleInstance"
    )
    if ctypes.windll.kernel32.GetLastError() == 183:   # ERROR_ALREADY_EXISTS
        ctypes.windll.kernel32.CloseHandle(_MUTEX)
        _MUTEX = None
        sys.exit(0)


def _cfg_path():
    base = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) \
           else os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "config.json")


def _is_first_run(cfg_path: str) -> bool:
    try:
        with open(cfg_path) as f:
            return json.load(f).get("first_run", True)
    except Exception:
        return True


def _mark_first_run_done(cfg_path: str):
    try:
        with open(cfg_path) as f:
            cfg = json.load(f)
        cfg["first_run"] = False
        with open(cfg_path, "w") as f:
            json.dump(cfg, f, indent=4)
    except Exception:
        pass


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def request_admin_and_restart():
    script = sys.argv[0]
    params = " ".join(f'"{a}"' for a in sys.argv[1:])
    ret = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, f'"{script}" {params}', None, 1
    )
    return ret > 32


def _close_splash():
    try:
        import pyi_splash
        pyi_splash.close()
    except Exception:
        pass


def main():
    _ensure_single_instance()   # Exit immediately if already running
    _close_splash()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # ── 1. Uninstall handler (called by Programs & Features "Uninstall") ──────
    if "--uninstall" in sys.argv:
        reply = QMessageBox.question(None, "Uninstall Focus Guard",
            "Are you sure you want to uninstall Focus Guard?\n\n"
            "All shortcuts and startup entries will be removed.",
            QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            uninstall()
            QMessageBox.information(None, "Uninstalled",
                "Focus Guard has been removed from this computer.")
        sys.exit(0)

    # ── 2. Admin check ────────────────────────────────────────────────────────
    if not is_admin():
        if request_admin_and_restart():
            sys.exit()
        QMessageBox.critical(None, "Administrator Required",
            "Focus Guard needs Administrator privileges to block websites.\n\n"
            "Right-click → Run as Administrator.")
        sys.exit(1)

    # ── 3. Check for active session that survived a reboot ───────────────────
    resume_info = get_active_session()
    if resume_info:
        block_sites(resume_info.get("sites") or [])
        repair_if_needed()
        # Start silently — tray only, no window popup.
        # The user sees the red padlock tray icon with remaining time.
        # They can click it to open the session screen.
        app.setQuitOnLastWindowClosed(False)
        window = FocusGuardApp(resume_info=resume_info)
        # window stays hidden; tray icon is shown inside FocusGuardApp.__init__
        sys.exit(app.exec())

    # ── 4. Installation flow ─────────────────────────────────────────────────
    installed = is_installed()

    if not installed:
        reply = QMessageBox.question(None, "Install Focus Guard",
            "Focus Guard is not installed on this computer.\n\n"
            "Install it now?\n\n"
            "After installation you can open Focus Guard from\n"
            "your Desktop — no USB needed to launch the app.\n\n"
            "The USB key is only required to start and stop sessions.",
            QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            success, err = install_to_computer()
            if success:
                QMessageBox.information(None, "Installation Complete",
                    "Focus Guard has been installed!\n\n"
                    "✔  Desktop shortcut created\n"
                    "✔  Start Menu entry created\n"
                    "✔  Listed in Programs & Features\n\n"
                    "You can now open Focus Guard from your Desktop\n"
                    "without the USB. Insert the USB key only when\n"
                    "you want to start a focus session.")
                installed = True
            else:
                QMessageBox.critical(None, "Installation Failed",
                    f"Could not install Focus Guard.\n\n{err or ''}\n\n"
                    "Try running as Administrator.")
                sys.exit(1)
        else:
            sys.exit()
    else:
        # Already installed — silently repair missing shortcuts/startup entries
        repair_if_needed()

    # ── 5. First-run welcome screen ───────────────────────────────────────────
    cfg_path = _cfg_path()
    if _is_first_run(cfg_path):
        dlg = WelcomeDialog()
        dlg.exec()
        if not dlg.agreed():
            sys.exit()
        _mark_first_run_done(cfg_path)

    # ── 6. Launch app ─────────────────────────────────────────────────────────
    window = FocusGuardApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
