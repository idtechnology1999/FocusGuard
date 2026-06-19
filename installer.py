import os
import sys
import shutil
import subprocess

INSTALL_DIR = os.path.join(os.getenv("PROGRAMFILES", "C:\\Program Files"), "FocusGuard")
CONFIG_PATH = os.path.join(INSTALL_DIR, "config.json")
EXE_PATH    = os.path.join(INSTALL_DIR, "FocusGuard.exe")

_STARTUP_FOLDER = os.path.join(
    os.environ.get("APPDATA", ""),
    "Microsoft", "Windows", "Start Menu", "Programs", "Startup"
)


def is_installed():
    if getattr(sys, 'frozen', False):
        return os.path.exists(EXE_PATH)
    return os.path.exists(INSTALL_DIR) and os.path.exists(CONFIG_PATH)


def get_usb_path():
    if getattr(sys, 'frozen', False):
        path = os.path.dirname(sys.executable)
        # Running from FocusGuard_installed subfolder on USB — go up to USB root
        if os.path.basename(path).lower() == 'focusguard_installed':
            path = os.path.dirname(path)
        return path
    return os.path.dirname(os.path.abspath(__file__))


def is_running_from_usb():
    drive = os.path.splitdrive(get_usb_path())[0]
    try:
        import win32file
        return win32file.GetDriveType(drive + "\\") == win32file.DRIVE_REMOVABLE
    except Exception:
        return True


def install_to_computer():
    """Install Focus Guard to Program Files. Returns (success, error_message)."""
    try:
        usb_path = get_usb_path()

        # Prefer the onedir build (FocusGuard_installed/) — fast launch, no temp extraction.
        # Falls back to copying the single-file EXE if the folder is not present.
        installed_src = os.path.join(usb_path, "FocusGuard_installed")
        if os.path.isdir(installed_src):
            if os.path.exists(INSTALL_DIR):
                shutil.rmtree(INSTALL_DIR)
            shutil.copytree(installed_src, INSTALL_DIR)
        else:
            os.makedirs(INSTALL_DIR, exist_ok=True)
            if getattr(sys, 'frozen', False):
                shutil.copy2(sys.executable, EXE_PATH)
            else:
                for f in ["main.py", "usb_auth.py", "blocker.py",
                          "session.py", "gui.py", "installer.py"]:
                    src = os.path.join(usb_path, f)
                    if os.path.exists(src):
                        shutil.copy2(src, os.path.join(INSTALL_DIR, f))
                img_src = os.path.join(usb_path, "image")
                img_dst = os.path.join(INSTALL_DIR, "image")
                if os.path.exists(img_src):
                    if os.path.exists(img_dst):
                        shutil.rmtree(img_dst)
                    shutil.copytree(img_src, img_dst)

        cfg_src = os.path.join(usb_path, "config.json")
        if os.path.exists(cfg_src) and not os.path.exists(CONFIG_PATH):
            shutil.copy2(cfg_src, CONFIG_PATH)
        elif not os.path.exists(CONFIG_PATH):
            import json
            with open(CONFIG_PATH, "w") as f:
                json.dump({
                    "blocked_sites": [],
                    "registered_devices": [],
                    "session_log": [],
                    "active_session": None
                }, f, indent=4)

        # Create shortcuts, startup entries and registry records
        _create_desktop_shortcut()
        _create_startmenu_shortcut()
        _register_task_scheduler()
        _register_autoplay_handler()
        _enable_driver_event_log()
        _register_usb_launch_task()
        _register_uninstall_entry()
        _register_startup_task()   # logon task — elevates silently, no UAC dialog
        remove_startup()           # remove any stale registry Run key (uac_admin=True makes it show UAC)
        _install_trusted_cert()
        _add_defender_exclusions()

        return True, None
    except Exception as e:
        return False, str(e)


# ── Desktop path ───────────────────────────────────────────────────────────────

def _get_desktop():
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders")
        path = winreg.QueryValueEx(key, "Desktop")[0]
        winreg.CloseKey(key)
        if os.path.isdir(path):
            return path
    except Exception:
        pass
    for p in [
        os.path.join(os.path.expanduser("~"), "Desktop"),
        os.path.join(os.environ.get("USERPROFILE", ""), "Desktop"),
        os.path.join("C:\\Users", os.environ.get("USERNAME", ""), "Desktop"),
    ]:
        if os.path.isdir(p):
            return p
    return os.path.expanduser("~")


def _get_target():
    if getattr(sys, 'frozen', False):
        return EXE_PATH
    return os.path.join(INSTALL_DIR, "main.py")


# ── Shortcut creation ──────────────────────────────────────────────────────────

def _create_desktop_shortcut():
    desktop = _get_desktop()
    lnk     = os.path.join(desktop, "Focus Guard.lnk")
    target  = _get_target()
    if _make_lnk(lnk, target):
        return True
    # Ultimate fallback: copy EXE directly to Desktop
    if getattr(sys, 'frozen', False) and os.path.exists(EXE_PATH):
        try:
            dest = os.path.join(desktop, "Focus Guard.exe")
            shutil.copy2(EXE_PATH, dest)
            return os.path.exists(dest)
        except Exception:
            pass
    return False


def _create_startmenu_shortcut():
    try:
        sm = os.path.join(os.environ.get("APPDATA", ""),
                          "Microsoft", "Windows", "Start Menu",
                          "Programs", "Focus Guard.lnk")
        _make_lnk(sm, _get_target())
    except Exception:
        pass


def _create_startup_folder_entry():
    """Add shortcut to Windows Startup folder — runs on every login."""
    try:
        os.makedirs(_STARTUP_FOLDER, exist_ok=True)
        lnk = os.path.join(_STARTUP_FOLDER, "FocusGuard.lnk")
        _make_lnk(lnk, _get_target())
    except Exception:
        pass


def _make_lnk(lnk_path, target):
    """Try 4 methods to create a .lnk shortcut."""
    # Method 1: win32com
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        sc = shell.CreateShortCut(lnk_path)
        sc.TargetPath = target
        sc.WorkingDirectory = INSTALL_DIR
        sc.Description = "Focus Guard — Productivity Enforcement System"
        sc.IconLocation = target + ",0"
        sc.save()
        if os.path.exists(lnk_path):
            return True
    except Exception:
        pass

    # Method 2: PowerShell with ExecutionPolicy bypass
    try:
        ps = (
            f'$ws = New-Object -ComObject WScript.Shell; '
            f'$sc = $ws.CreateShortcut("{lnk_path}"); '
            f'$sc.TargetPath = "{target}"; '
            f'$sc.WorkingDirectory = "{INSTALL_DIR}"; '
            f'$sc.Description = "Focus Guard"; '
            f'$sc.Save()'
        )
        subprocess.run(
            ["powershell", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps],
            check=True, capture_output=True, timeout=15
        )
        if os.path.exists(lnk_path):
            return True
    except Exception:
        pass

    # Method 3: VBScript via cscript
    try:
        vbs = (
            f'Set oWS = WScript.CreateObject("WScript.Shell")\n'
            f'Set oLink = oWS.CreateShortcut("{lnk_path}")\n'
            f'oLink.TargetPath = "{target}"\n'
            f'oLink.WorkingDirectory = "{INSTALL_DIR}"\n'
            f'oLink.Description = "Focus Guard"\n'
            f'oLink.Save\n'
        )
        tmp = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "fg_lnk.vbs")
        with open(tmp, "w") as f:
            f.write(vbs)
        subprocess.run(["cscript", "//Nologo", tmp],
                       check=True, capture_output=True, timeout=15)
        try:
            os.remove(tmp)
        except Exception:
            pass
        if os.path.exists(lnk_path):
            return True
    except Exception:
        pass

    # Method 4: Write raw .lnk bytes (minimal header, points to target)
    try:
        _write_raw_lnk(lnk_path, target)
        if os.path.exists(lnk_path):
            return True
    except Exception:
        pass

    return False


def _write_raw_lnk(lnk_path, target_path):
    """Write a minimal Windows Shell Link (.lnk) file pointing to target_path."""
    import struct
    target_bytes = (target_path + "\x00").encode("utf-16-le")
    # Shell Link header (76 bytes)
    header  = b'\x4c\x00\x00\x00'                  # HeaderSize = 76
    header += b'\x01\x14\x02\x00\x00\x00\x00\x00'  # LinkCLSID part 1
    header += b'\xc0\x00\x00\x00\x00\x00\x00\x46'  # LinkCLSID part 2
    header += struct.pack('<I', 0x0001)              # LinkFlags: HasLinkTargetIDList
    header += struct.pack('<I', 0x0020)              # FileAttributes: FILE_ATTRIBUTE_ARCHIVE
    header += b'\x00' * 8                           # CreationTime
    header += b'\x00' * 8                           # AccessTime
    header += b'\x00' * 8                           # WriteTime
    header += struct.pack('<I', 0)                   # FileSize
    header += struct.pack('<I', 0)                   # IconIndex
    header += struct.pack('<I', 1)                   # ShowCommand: SW_NORMAL
    header += struct.pack('<H', 0)                   # HotKey
    header += b'\x00' * 10                          # Reserved
    # StringData: LocalBasePath (Unicode)
    str_data  = struct.pack('<H', len(target_path))
    str_data += target_path.encode("utf-16-le")
    # IDList placeholder (minimal)
    id_list   = b'\x14\x00' + b'\x1f\x50' + b'\xe0\x4f\xd0\x20\xea\x3a\x69\x10'
    id_list  += b'\xa2\xd8\x08\x00\x2b\x30\x30\x9d' + b'\x00\x00'
    id_list_size = struct.pack('<H', len(id_list))

    with open(lnk_path, 'wb') as f:
        f.write(header)
        f.write(id_list_size)
        f.write(id_list)
        f.write(str_data)


# ── Task Scheduler: USB auto-launch ───────────────────────────────────────────

def _register_usb_launch_task():
    """Create FocusGuardUSBLaunch — fires 3 s after any USB storage is inserted.

    Uses a Windows event trigger (DriverFrameworks EventID 2003) so the
    installed app opens the moment the flash drive is plugged in, with no
    AutoPlay dialog and no click required.  The PowerShell action checks
    whether Focus Guard is already running before launching it.
    """
    try:
        exe_ps = EXE_PATH.replace("'", "''")   # escape for PowerShell single-quoted string

        # No -Verb RunAs here — the task itself runs at HighestAvailable (admin)
        # so adding -Verb RunAs would trigger an unwanted UAC prompt.
        ps_cmd = (
            f"Start-Sleep 2; "
            f"$fg = Get-WmiObject Win32_LogicalDisk | "
            f"Where-Object {{$_.DriveType -eq 2}} | "
            f"Where-Object {{Test-Path \"$($_.DeviceID)\\FocusGuard.exe\"}}; "
            f"if ($fg -and (Test-Path '{exe_ps}') -and "
            f"-not (Get-Process FocusGuard -ErrorAction SilentlyContinue)) "
            f"{{ Start-Process '{exe_ps}' -ArgumentList '--usb-trigger' }}"
        )

        # Inner event-subscription XML embedded as text inside the outer XML —
        # angle brackets must be escaped.
        sub_raw = (
            '<QueryList><Query Id="0" '
            'Path="Microsoft-Windows-DriverFrameworks-UserMode/Operational">'
            '<Select Path="Microsoft-Windows-DriverFrameworks-UserMode/Operational">'
            "*[System[Provider[@Name='Microsoft-Windows-DriverFrameworks-UserMode']"
            " and EventID=2003]]"
            '</Select></Query></QueryList>'
        )
        sub_esc = sub_raw.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        # Arguments value — escape angle brackets for XML text content
        args_esc = (
            f"-WindowStyle Hidden -NonInteractive -Command \"{ps_cmd}\""
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )

        xml = (
            '<?xml version="1.0" encoding="UTF-16"?>\n'
            '<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">\n'
            '  <Triggers><EventTrigger><Enabled>true</Enabled>\n'
            f'    <Subscription>{sub_esc}</Subscription>\n'
            '  </EventTrigger></Triggers>\n'
            '  <Principals><Principal id="Author">\n'
            '    <LogonType>InteractiveToken</LogonType>\n'
            '    <RunLevel>HighestAvailable</RunLevel>\n'
            '  </Principal></Principals>\n'
            '  <Settings>\n'
            '    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>\n'
            '    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>\n'
            '    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>\n'
            '    <ExecutionTimeLimit>PT1M</ExecutionTimeLimit>\n'
            '    <Hidden>true</Hidden>\n'
            '  </Settings>\n'
            '  <Actions Context="Author"><Exec>\n'
            '    <Command>powershell.exe</Command>\n'
            f'    <Arguments>{args_esc}</Arguments>\n'
            '  </Exec></Actions>\n'
            '</Task>'
        )

        import tempfile
        tmp = tempfile.NamedTemporaryFile(
            suffix='.xml', delete=False, mode='w', encoding='utf-16'
        )
        tmp.write(xml)
        tmp.close()
        try:
            subprocess.run(
                ['schtasks', '/create', '/tn', 'FocusGuardUSBLaunch',
                 '/xml', tmp.name, '/f'],
                capture_output=True, check=False, timeout=30
            )
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
    except Exception:
        pass


def _enable_driver_event_log():
    """Enable the DriverFrameworks event log used by the USB launch task trigger.

    This log is disabled by default on many Windows machines.  Without it the
    FocusGuardUSBLaunch task never fires because its event trigger has nothing
    to listen to.
    """
    try:
        subprocess.run(
            ['wevtutil', 'set-log',
             'Microsoft-Windows-DriverFrameworks-UserMode/Operational',
             '/enabled:true'],
            capture_output=True, check=False, timeout=15
        )
    except Exception:
        pass


def _unregister_usb_launch_task():
    try:
        subprocess.run(
            ['schtasks', '/delete', '/tn', 'FocusGuardUSBLaunch', '/f'],
            capture_output=True, check=False, timeout=10
        )
    except Exception:
        pass


# ── Task Scheduler startup task ────────────────────────────────────────────────

def _register_startup_task():
    """Create FocusGuardStartup — runs FocusGuard at every logon with admin.

    LogonType=InteractiveToken + RunLevel=HighestAvailable means Windows
    elevates the process silently (no UAC dialog) when the logged-in user is
    an administrator.  This replaces the registry Run key approach, which would
    show a UAC prompt on every boot because the EXE now embeds a
    requireAdministrator manifest (uac_admin=True in the spec).
    """
    try:
        import tempfile
        exe_esc = EXE_PATH.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        xml = (
            '<?xml version="1.0" encoding="UTF-16"?>\n'
            '<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">\n'
            '  <Triggers>\n'
            '    <LogonTrigger><Enabled>true</Enabled><Delay>PT3S</Delay></LogonTrigger>\n'
            '  </Triggers>\n'
            '  <Principals><Principal id="Author">\n'
            '    <LogonType>InteractiveToken</LogonType>\n'
            '    <RunLevel>HighestAvailable</RunLevel>\n'
            '  </Principal></Principals>\n'
            '  <Settings>\n'
            '    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>\n'
            '    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>\n'
            '    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>\n'
            '    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>\n'
            '    <Hidden>true</Hidden>\n'
            '  </Settings>\n'
            '  <Actions Context="Author"><Exec>\n'
            f'    <Command>{exe_esc}</Command>\n'
            '  </Exec></Actions>\n'
            '</Task>'
        )
        tmp = tempfile.NamedTemporaryFile(
            suffix='.xml', delete=False, mode='w', encoding='utf-16'
        )
        tmp.write(xml)
        tmp.close()
        try:
            subprocess.run(
                ['schtasks', '/create', '/tn', 'FocusGuardStartup',
                 '/xml', tmp.name, '/f'],
                capture_output=True, check=False, timeout=30
            )
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
    except Exception:
        pass


def _unregister_startup_task():
    try:
        subprocess.run(
            ['schtasks', '/delete', '/tn', 'FocusGuardStartup', '/f'],
            capture_output=True, check=False, timeout=10
        )
    except Exception:
        pass


# ── Task Scheduler watchdog ────────────────────────────────────────────────────

def _register_task_scheduler():
    """Register a scheduled task that auto-restarts FocusGuard every 5 min."""
    try:
        exe = EXE_PATH if getattr(sys, 'frozen', False) else _get_target()
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


def _unregister_task_scheduler():
    try:
        subprocess.run(
            ["schtasks", "/delete", "/tn", "FocusGuardWatchdog", "/f"],
            capture_output=True, check=False, timeout=10
        )
    except Exception:
        pass


# ── AutoPlay handler ───────────────────────────────────────────────────────────

def _register_autoplay_handler():
    """Register Focus Guard as the DEFAULT AutoPlay action for USB storage.

    After this runs, inserting the flash drive automatically opens the
    installed Focus Guard app — no dialog, no click required.
    Called both at install time and on every launch so the EXE path
    stays current after updates.
    """
    try:
        import winreg
        exe = EXE_PATH if getattr(sys, 'frozen', False) else _get_target()

        # 1. Register the handler definition
        h = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer"
            r"\AutoplayHandlers\Handlers\FocusGuardHandler")
        winreg.SetValueEx(h, "Action",        0, winreg.REG_SZ, "Open Focus Guard")
        winreg.SetValueEx(h, "Provider",       0, winreg.REG_SZ, "Focus Guard")
        winreg.SetValueEx(h, "DefaultIcon",    0, winreg.REG_SZ, f"{exe},0")
        winreg.SetValueEx(h, "InvokeProgram",  0, winreg.REG_SZ, exe)
        winreg.CloseKey(h)

        # 2. Bind to USB/storage arrival event
        h = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer"
            r"\AutoplayHandlers\EventHandlers\StorageOnArrival")
        winreg.SetValueEx(h, "FocusGuardHandler", 0, winreg.REG_SZ, "")
        winreg.CloseKey(h)

        # 3. Set as DEFAULT — skip the dialog, auto-launch on every insert
        h = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer"
            r"\AutoplayHandlers\UserChosenExecuteHandlers\StorageOnArrival")
        winreg.SetValueEx(h, "", 0, winreg.REG_SZ, "FocusGuardHandler")
        winreg.CloseKey(h)

    except Exception:
        pass


def _unregister_autoplay_handler():
    try:
        import winreg
        for path in [
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\AutoplayHandlers\Handlers\FocusGuardHandler",
        ]:
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
            except Exception:
                pass
        try:
            ekey = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\AutoplayHandlers\EventHandlers\StorageOnArrival",
                0, winreg.KEY_SET_VALUE)
            try:
                winreg.DeleteValue(ekey, "FocusGuardHandler")
            except FileNotFoundError:
                pass
            winreg.CloseKey(ekey)
        except Exception:
            pass
    except Exception:
        pass


# ── Startup registry ───────────────────────────────────────────────────────────

def get_installed_path():
    return INSTALL_DIR


def set_startup(exe_path=None):
    try:
        import winreg
        if exe_path is None:
            exe_path = EXE_PATH if getattr(sys, 'frozen', False) else _get_target()
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "FocusGuard", 0, winreg.REG_SZ, exe_path)
        winreg.CloseKey(key)
    except Exception:
        pass


def remove_startup():
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


def uninstall():
    try:
        remove_startup()
        _unregister_startup_task()
        _unregister_task_scheduler()
        _unregister_usb_launch_task()
        _unregister_autoplay_handler()
        _unregister_uninstall_entry()
        _uninstall_trusted_cert()
        if os.path.exists(INSTALL_DIR):
            shutil.rmtree(INSTALL_DIR)
        desktop = _get_desktop()
        for p in [
            os.path.join(desktop, "Focus Guard.lnk"),
            os.path.join(desktop, "Focus Guard.exe"),
            os.path.join(os.environ.get("APPDATA", ""),
                         "Microsoft", "Windows", "Start Menu",
                         "Programs", "Focus Guard.lnk"),
            os.path.join(_STARTUP_FOLDER, "FocusGuard.lnk"),
        ]:
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
        return True
    except Exception:
        return False


# ── Programs & Features (Add/Remove Programs) ─────────────────────────────────

def _register_uninstall_entry():
    """Add Focus Guard to Windows Programs & Features list."""
    try:
        import winreg, time as _t
        key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\FocusGuard"
        # Try HKLM first (shows for all users), fall back to HKCU
        for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                key = winreg.CreateKey(root, key_path)
                winreg.SetValueEx(key, "DisplayName",     0, winreg.REG_SZ,    "Focus Guard")
                winreg.SetValueEx(key, "DisplayVersion",  0, winreg.REG_SZ,    "1.0")
                winreg.SetValueEx(key, "Publisher",       0, winreg.REG_SZ,
                                  "NACOMES — The Polytechnic, Ibadan (2026)")
                winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ,    INSTALL_DIR)
                winreg.SetValueEx(key, "DisplayIcon",     0, winreg.REG_SZ,    f"{EXE_PATH},0")
                winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ,    f'"{EXE_PATH}" --uninstall')
                winreg.SetValueEx(key, "InstallDate",     0, winreg.REG_SZ,    _t.strftime("%Y%m%d"))
                winreg.SetValueEx(key, "NoModify",        0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(key, "NoRepair",        0, winreg.REG_DWORD, 1)
                try:
                    kb = sum(os.path.getsize(os.path.join(INSTALL_DIR, f))
                             for f in os.listdir(INSTALL_DIR)
                             if os.path.isfile(os.path.join(INSTALL_DIR, f))) // 1024
                    winreg.SetValueEx(key, "EstimatedSize", 0, winreg.REG_DWORD, kb)
                except Exception:
                    pass
                winreg.CloseKey(key)
                break   # Success — no need to try HKCU
            except Exception:
                continue
    except Exception:
        pass


def _unregister_uninstall_entry():
    try:
        import winreg
        key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\FocusGuard"
        for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                winreg.DeleteKey(root, key_path)
            except Exception:
                pass
    except Exception:
        pass


# ── Windows Defender exclusions ───────────────────────────────────────────────

def _add_defender_exclusions():
    """Tell Windows Defender that the Focus Guard install folder is safe.

    PyInstaller EXEs are sometimes flagged on first run, causing a brief
    'access denied' error while Defender scans them.  Adding the install
    directory as an exclusion prevents this.
    """
    try:
        subprocess.run(
            ['powershell', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
             '-Command',
             f'Add-MpPreference -ExclusionPath "{INSTALL_DIR}" -ErrorAction SilentlyContinue;'
             f'Add-MpPreference -ExclusionProcess "FocusGuard.exe" -ErrorAction SilentlyContinue'],
            capture_output=True, check=False, timeout=20
        )
    except Exception:
        pass


# ── Trusted CA certificate ────────────────────────────────────────────────────

_CERT_STORE_CN = "focusguard.local"   # matches CN in block_server._CERT_PEM


def _install_trusted_cert():
    """Add the Focus Guard self-signed cert to Windows Trusted Root CAs.

    This makes the HTTPS block page load without a browser warning.
    Requires admin rights, which Focus Guard already runs with.
    """
    try:
        from block_server import _CERT_PEM
        tmp = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "fg_ca.cer")
        with open(tmp, "w") as f:
            f.write(_CERT_PEM)
        subprocess.run(
            ["certutil", "-addstore", "-f", "Root", tmp],
            capture_output=True, check=False, timeout=20
        )
        try:
            os.remove(tmp)
        except OSError:
            pass
    except Exception:
        pass


def _uninstall_trusted_cert():
    """Remove the Focus Guard CA cert from Windows Trusted Root CAs."""
    try:
        subprocess.run(
            ["certutil", "-delstore", "Root", _CERT_STORE_CN],
            capture_output=True, check=False, timeout=20
        )
    except Exception:
        pass


# ── EXE self-update ───────────────────────────────────────────────────────────

def _update_installed_exe(src, dst):
    """Replace the installed EXE with a newer copy from the USB.

    Tries three escalating strategies so the update survives even when
    Windows still has the old EXE's image in memory:

    1. Direct copy  — works when no process holds the file open.
    2. Kill + copy  — terminates any running installed-app process first,
                      then retries the copy.
    3. MoveFileEx   — schedules the replacement at next Windows boot if the
                      file is still locked (e.g. antivirus, Defender cache).
    """
    import time, ctypes

    # Skip if already the same file (no update needed)
    try:
        if os.path.getsize(src) == os.path.getsize(dst):
            return
    except OSError:
        pass

    # Strategy 1 — plain copy (most common success path)
    for _ in range(2):
        try:
            shutil.copy2(src, dst)
            return
        except Exception:
            time.sleep(0.4)

    # Strategy 2 — kill any running installed instance, then copy
    try:
        import psutil
        for proc in psutil.process_iter(["exe"]):
            try:
                if os.path.normpath(proc.info["exe"]).lower() == dst.lower():
                    proc.kill()
                    time.sleep(0.8)
                    break
            except Exception:
                pass
        shutil.copy2(src, dst)
        return
    except Exception:
        pass

    # Strategy 3 — schedule replacement on next reboot via MoveFileEx
    try:
        MOVEFILE_REPLACE_EXISTING  = 0x1
        MOVEFILE_DELAY_UNTIL_REBOOT = 0x4
        ctypes.windll.kernel32.MoveFileExW(
            src, dst,
            MOVEFILE_REPLACE_EXISTING | MOVEFILE_DELAY_UNTIL_REBOOT
        )
    except Exception:
        pass


# ── Repair / self-heal ────────────────────────────────────────────────────────

def repair_if_needed():
    """Called on every launch. Silently fixes shortcuts, startup path,
    and updates the installed EXE when running a newer copy from USB."""
    if not is_installed():
        return
    try:
        # If running from USB/external path, update the installed EXE silently
        if getattr(sys, 'frozen', False):
            current_exe = os.path.normpath(sys.executable)
            target_exe  = os.path.normpath(EXE_PATH)
            if current_exe.lower() != target_exe.lower() and os.path.exists(current_exe):
                _update_installed_exe(current_exe, target_exe)

        # Keep logon task up-to-date; remove registry Run key (UAC-noisy with uac_admin=True)
        _register_startup_task()
        remove_startup()

        # Re-register AutoPlay default so inserting the flash always opens the app
        _register_autoplay_handler()
        _enable_driver_event_log()
        _register_usb_launch_task()   # keeps task up-to-date (checks FocusGuard.exe on USB)

        # Re-create desktop shortcut if it disappeared
        desktop = _get_desktop()
        lnk = os.path.join(desktop, "Focus Guard.lnk")
        exe_copy = os.path.join(desktop, "Focus Guard.exe")
        if not os.path.exists(lnk) and not os.path.exists(exe_copy):
            _create_desktop_shortcut()

        # Re-create startup folder entry if missing
        startup_lnk = os.path.join(_STARTUP_FOLDER, "FocusGuard.lnk")
        if not os.path.exists(startup_lnk):
            _create_startup_folder_entry()

        # Ensure Programs & Features entry exists
        try:
            import winreg
            key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\FocusGuard"
            found = False
            for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                try:
                    k = winreg.OpenKey(root, key_path)
                    winreg.CloseKey(k)
                    found = True
                    break
                except Exception:
                    pass
            if not found:
                _register_uninstall_entry()
        except Exception:
            pass
    except Exception:
        pass
