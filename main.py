import sys
import os
import ctypes
import json

from PySide6.QtWidgets import QApplication, QMessageBox

from installer import uninstall
from session import get_active_session
from blocker import block_sites
from gui import FocusGuardApp, WelcomeDialog


# ── Helpers ───────────────────────────────────────────────────────────────────

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


def _register_autoplay():
    """Register Focus Guard as the AutoPlay handler for USB storage arrival.

    Called on every launch so the stored EXE path stays current even when
    the flash drive is assigned a different letter on a new PC.

    After the first run the handler is set as the DEFAULT action for storage
    arrival — meaning Windows will auto-launch Focus Guard the next time the
    flash is inserted, with no dialog and no click required.
    """
    try:
        import winreg
        exe = sys.executable if getattr(sys, 'frozen', False) \
              else os.path.abspath(__file__)

        # 1. Handler definition
        h = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer"
            r"\AutoplayHandlers\Handlers\FocusGuardHandler")
        winreg.SetValueEx(h, "Action",        0, winreg.REG_SZ, "Run Focus Guard")
        winreg.SetValueEx(h, "Provider",       0, winreg.REG_SZ, "Focus Guard")
        winreg.SetValueEx(h, "DefaultIcon",    0, winreg.REG_SZ, f"{exe},0")
        winreg.SetValueEx(h, "InvokeProgram",  0, winreg.REG_SZ, exe)
        winreg.CloseKey(h)

        # 2. Bind handler to USB/storage arrival event
        h = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer"
            r"\AutoplayHandlers\EventHandlers\StorageOnArrival")
        winreg.SetValueEx(h, "FocusGuardHandler", 0, winreg.REG_SZ, "")
        winreg.CloseKey(h)

        # 3. Set as DEFAULT — future USB inserts skip the dialog entirely
        h = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer"
            r"\AutoplayHandlers\UserChosenExecuteHandlers\StorageOnArrival")
        winreg.SetValueEx(h, "", 0, winreg.REG_SZ, "FocusGuardHandler")
        winreg.CloseKey(h)

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


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    _close_splash()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # ── 1. Cleanup handler ────────────────────────────────────────────────────
    if "--uninstall" in sys.argv:
        reply = QMessageBox.question(None, "Remove Focus Guard",
            "Remove Focus Guard from this computer?\n\n"
            "Startup entries and scheduled tasks will be deleted.",
            QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            uninstall()
            QMessageBox.information(None, "Removed",
                "Focus Guard has been removed from this computer.")
        sys.exit(0)

    # ── 2. Admin elevation ────────────────────────────────────────────────────
    if not is_admin():
        if request_admin_and_restart():
            sys.exit()
        QMessageBox.critical(None, "Administrator Required",
            "Focus Guard needs Administrator privileges to block websites.\n\n"
            "Right-click the EXE → Run as Administrator.")
        sys.exit(1)

    # ── 3. Register AutoPlay so next USB insert launches this EXE directly ────
    _register_autoplay()

    # ── 4. Resume a session that survived a reboot ────────────────────────────
    resume_info = get_active_session()
    if resume_info:
        block_sites(resume_info.get("sites") or [])
        window = FocusGuardApp(resume_info=resume_info)
        window.show()
        sys.exit(app.exec())

    # ── 5. First-run welcome ──────────────────────────────────────────────────
    cfg_path = _cfg_path()
    if _is_first_run(cfg_path):
        dlg = WelcomeDialog()
        dlg.exec()
        if not dlg.agreed():
            sys.exit()
        _mark_first_run_done(cfg_path)

    # ── 6. Launch ─────────────────────────────────────────────────────────────
    window = FocusGuardApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
