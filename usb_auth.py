import json
import os
import sys
import wmi
import hashlib

_INSTALL_CONFIG = os.path.join(
    os.getenv("PROGRAMFILES", "C:\\Program Files"), "FocusGuard", "config.json"
)
if getattr(sys, 'frozen', False):
    _LOCAL_CONFIG = os.path.join(os.path.dirname(sys.executable), "config.json")
else:
    _LOCAL_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def _config_path() -> str:
    """Always prefer Program Files config once it exists — checked every call."""
    return _INSTALL_CONFIG if os.path.exists(_INSTALL_CONFIG) else _LOCAL_CONFIG


def _load_config():
    with open(_config_path(), "r") as f:
        return json.load(f)


def _save_config(config):
    with open(_config_path(), "w") as f:
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
        if "USB" in disk.InterfaceType:
            drives.append(disk)
    return drives


def get_usb_drive_path() -> str | None:
    """
    Return the root path of the first connected USB drive (e.g. 'E:\\').
    Returns None if no USB drive is found.
    """
    try:
        c = wmi.WMI()
        for disk in c.Win32_DiskDrive():
            if "USB" not in disk.InterfaceType:
                continue
            for partition in disk.associators("Win32_DiskDriveToDiskPartition"):
                for logical in partition.associators("Win32_LogicalDiskToPartition"):
                    return logical.DeviceID + "\\"   # e.g. "E:\\"
    except Exception:
        pass
    return None


def detect_focus_guard_usb():
    """
    Returns (device_id, is_new) if a valid USB is found.
    is_new=True means first time on this machine.
    Returns (None, False) if no USB found.
    """
    drives = get_connected_usb_drives()
    if not drives:
        return None, False

    config = _load_config()
    registered = config.get("registered_devices", [])

    # Use the first USB drive found
    device = drives[0]
    dev_id = _device_id(device)

    if dev_id not in registered:
        return dev_id, True  # new device
    return dev_id, False     # known device


def register_device(device_id):
    """Register a USB device as trusted."""
    config = _load_config()
    if device_id not in config["registered_devices"]:
        config["registered_devices"].append(device_id)
        _save_config(config)


def is_device_registered(device_id):
    config = _load_config()
    return device_id in config.get("registered_devices", [])
