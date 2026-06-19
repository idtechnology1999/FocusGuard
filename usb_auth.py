import json
import os
import sys
import string
import ctypes
import wmi
import hashlib

_INSTALL_CONFIG = os.path.join(
    os.getenv("PROGRAMFILES", "C:\\Program Files"), "FocusGuard", "config.json"
)
if getattr(sys, 'frozen', False):
    _exe_dir = os.path.dirname(sys.executable)
    # Running from FocusGuard_installed subfolder on USB — config.json is one level up (USB root)
    if os.path.basename(_exe_dir).lower() == 'focusguard_installed':
        _exe_dir = os.path.dirname(_exe_dir)
    _LOCAL_CONFIG = os.path.join(_exe_dir, "config.json")
else:
    _LOCAL_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def _config_path() -> str:
    """Always prefer Program Files config once it exists — checked every call."""
    return _INSTALL_CONFIG if os.path.exists(_INSTALL_CONFIG) else _LOCAL_CONFIG


def _load_config():
    with open(_config_path(), "r", encoding="utf-8-sig") as f:
        return json.load(f)


def _save_config(config):
    with open(_config_path(), "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)


def _device_id(device):
    """Generate a stable fingerprint for a USB device.

    PNPDeviceID contains the USB VID, PID and serial number — it stays the
    same regardless of which port the drive is plugged into or how many other
    drives are connected.  Fall back to the old fields only if PNPDeviceID is
    blank (very rare on modern hardware).
    """
    pnp = getattr(device, "PNPDeviceID", None) or ""
    if pnp:
        raw = pnp
    else:
        raw = f"{device.DeviceID}-{device.Manufacturer}-{device.Name}"
    return hashlib.sha256(raw.encode()).hexdigest()


def get_connected_usb_drives():
    """Return list of connected USB disk drives via WMI."""
    c = wmi.WMI()
    drives = []
    for disk in c.Win32_DiskDrive():
        iface = (getattr(disk, 'InterfaceType', None) or '').upper()
        if 'USB' in iface:
            drives.append(disk)
    return drives


def _find_fg_drive() -> str | None:
    """Find a non-system drive that has FocusGuard.exe, excluding the
    installed copy.  Uses only GetDriveTypeW (kernel API, zero WMI) so
    it works even when WMI is slow or unavailable.  Checks both
    removable (type 2) and fixed (type 3) drives — NTFS USB sticks
    appear as type 3 on most Windows machines."""
    install_exe = os.path.normcase(os.path.join(
        os.getenv("PROGRAMFILES", "C:\\Program Files"),
        "FocusGuard", "FocusGuard.exe"
    ))
    system_letter = os.path.splitdrive(
        os.getenv("SystemRoot", "C:\\Windows")
    )[0].upper().rstrip(":")

    for letter in string.ascii_uppercase:
        if letter == system_letter:
            continue            # never look on the Windows drive (C:\)
        root = f"{letter}:\\"
        try:
            dtype = ctypes.windll.kernel32.GetDriveTypeW(root)
            if dtype not in (2, 3):   # 2=removable  3=fixed (NTFS USB → 3)
                continue
            candidate  = os.path.join(root, "FocusGuard.exe")
            candidate2 = os.path.join(root, "FocusGuard_installed", "FocusGuard.exe")
            if os.path.normcase(candidate) == install_exe:
                continue        # never match the installed copy in Program Files
            if os.path.exists(candidate) or os.path.exists(candidate2):
                return root
        except Exception:
            pass
    return None


def get_usb_drive_path() -> str | None:
    """Return the root path of the drive that contains FocusGuard.exe.

    Using _find_fg_drive() as primary means we return the EXACT USB path,
    not just 'the first non-system drive' which could be an internal HDD.
    Falls back to the first FAT32/exFAT removable drive (DriveType 2) for
    the rare case where a registered key no longer has FocusGuard.exe."""
    fg = _find_fg_drive()
    if fg:
        return fg
    # Fallback — first FAT32/exFAT removable drive only (never an HDD)
    for letter in string.ascii_uppercase:
        root = f"{letter}:\\"
        try:
            if ctypes.windll.kernel32.GetDriveTypeW(root) == 2:
                return root
        except Exception:
            pass
    return None


def detect_focus_guard_usb():
    """
    Returns (device_id, is_new) if a Focus Guard USB is found.
    - Registered USB  → trusted by hardware ID alone (no file check).
    - New USB         → must carry FocusGuard.exe on its root to qualify.
    Returns (None, False) if no valid USB found.
    """
    config = _load_config()
    registered = config.get("registered_devices", [])

    # --- Primary path: WMI hardware fingerprint ---
    try:
        drives = get_connected_usb_drives()
    except Exception:
        drives = []

    if drives:
        # Check every connected USB drive — not just drives[0] — so a second
        # USB device (card reader, mouse receiver…) doesn't shadow the key.
        for device in drives:
            dev_id = _device_id(device)
            if dev_id in registered:
                return dev_id, False   # registered — trust by hardware ID

        # None of the WMI-visible drives are registered.
        if registered:
            return None, False   # a USB is already registered — reject any unknown drive
        # No registered devices yet — allow first-time setup only
        if _find_fg_drive():
            return _device_id(drives[0]), True

        return None, False   # random flash drive(s), no FocusGuard.exe

    # --- Fallback: WMI returned no drives ---
    # Some USB sticks use UASP and appear as SCSI in Win32_DiskDrive,
    # so they are invisible to the WMI filter above.  Fall back to
    # scanning drive letters for FocusGuard.exe directly.
    fg_drive = _find_fg_drive()
    if not fg_drive:
        return None, False   # no FocusGuard.exe on any drive → not our key

    # Get a stable fingerprint from the volume serial number.
    try:
        vsn = ctypes.c_ulong(0)
        ctypes.windll.kernel32.GetVolumeInformationW(
            fg_drive, None, 0, ctypes.byref(vsn), None, None, None, 0
        )
        dev_id = hashlib.sha256(f"vsn:{vsn.value}".encode()).hexdigest()
    except Exception:
        dev_id = hashlib.sha256(fg_drive.upper().encode()).hexdigest()

    if dev_id in registered:
        return dev_id, False   # registered via volume serial

    # Registered devices exist but WMI can't fingerprint this hardware — reject.
    if registered:
        return None, False

    # No registered devices yet → treat as a brand-new Focus Guard USB.
    return dev_id, True


def register_device(device_id):
    """Register a USB device as trusted."""
    config = _load_config()
    if device_id not in config["registered_devices"]:
        config["registered_devices"].append(device_id)
        _save_config(config)


def is_device_registered(device_id):
    config = _load_config()
    return device_id in config.get("registered_devices", [])
