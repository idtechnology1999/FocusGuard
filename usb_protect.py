"""
USB file protection module.

Protection strategy: diskpart 'attributes volume set readonly'
  - Locks the ENTIRE USB drive at the OS level
  - Works on FAT32 AND NTFS — no conversion needed
  - Survives reboots — permanent without the app running
  - Any delete/write attempt in Explorer returns
    "The disk is write-protected. Remove the write-protection..."
  - Only removed by entering the master key in Focus Guard

Master key (developer only): DELETE-FOCUSG
"""

import os
import tempfile
import subprocess
import ctypes

_MASTER_KEY = "DELETE-FOCUSG"


# ── Diskpart helper ────────────────────────────────────────────────────────────

def _run_diskpart(commands: list) -> bool:
    """Write a diskpart script to a temp file and execute it."""
    script = "\n".join(commands) + "\nexit\n"
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(suffix=".txt")
        os.write(fd, script.encode("ascii"))
        os.close(fd)
        r = subprocess.run(
            ["diskpart", "/s", tmp],
            capture_output=True, timeout=60
        )
        return r.returncode == 0
    except Exception:
        return False
    finally:
        if tmp:
            try:
                os.unlink(tmp)
            except Exception:
                pass


def _drive_letter(usb_path: str) -> str:
    """Extract bare drive letter from a path — e.g. 'E:\\' → 'E'."""
    return os.path.splitdrive(usb_path)[0].rstrip(":\\").strip()


# ── Protection state ───────────────────────────────────────────────────────────

def is_protected(usb_path: str) -> bool:
    """
    Return True if the USB volume is write-protected.
    Tests by attempting to create and delete a tiny temp file.
    """
    test = os.path.join(usb_path, f"._fg_wtest_{os.getpid()}")
    try:
        with open(test, "w") as f:
            f.write("x")
        os.remove(test)
        return False   # write succeeded → not protected
    except Exception:
        return True    # write failed → protected


# ── Apply protection ───────────────────────────────────────────────────────────

def protect(usb_path: str) -> None:
    """
    Set the USB volume to read-only using diskpart.
    After this, no file can be deleted, modified, or created on the drive
    — even when Focus Guard is not running, even on FAT32.
    """
    letter = _drive_letter(usb_path)
    _run_diskpart([
        f"select volume {letter}",
        "attributes volume set readonly",
    ])


# ── Remove protection ──────────────────────────────────────────────────────────

def verify_and_unprotect(usb_path: str, entered_key: str) -> bool:
    """
    Verify the master key and, if correct, remove write-protection.
    Returns True on success, False if the key is wrong.
    """
    def _norm(k):
        return k.upper().replace("-", "").replace(" ", "")

    if _norm(entered_key) != _norm(_MASTER_KEY):
        return False

    letter = _drive_letter(usb_path)
    return _run_diskpart([
        f"select volume {letter}",
        "attributes volume clear readonly",
    ])


# ── File-handle lock (bonus Layer 2 — extra protection while app is running) ──

def lock_usb_files(usb_path: str) -> list:
    """
    Open file handles on critical USB files (no FILE_SHARE_DELETE).
    Adds an extra layer while Focus Guard is running.
    The main protection is the diskpart write-lock — this is supplementary.
    """
    GENERIC_READ      = 0x80000000
    FILE_SHARE_RW     = 0x00000003   # Read+Write allowed, Delete blocked
    OPEN_EXISTING     = 3
    FILE_ATTR_NORMAL  = 0x80

    CreateFileW = ctypes.windll.kernel32.CreateFileW
    CreateFileW.restype  = ctypes.c_void_p
    CreateFileW.argtypes = [
        ctypes.c_wchar_p, ctypes.c_ulong, ctypes.c_ulong,
        ctypes.c_void_p,  ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p,
    ]
    INVALID = ctypes.c_void_p(-1).value

    handles = []
    for name in ["FocusGuard.exe", "autorun.inf", "config.json", "USB_README.txt"]:
        fp = os.path.join(usb_path, name)
        if not os.path.exists(fp):
            continue
        try:
            h = CreateFileW(fp, GENERIC_READ, FILE_SHARE_RW,
                            None, OPEN_EXISTING, FILE_ATTR_NORMAL, None)
            if h is not None and h != INVALID:
                handles.append(h)
        except Exception:
            pass
    return handles


def unlock_usb_files(handles: list):
    """Release all handles returned by lock_usb_files()."""
    CloseHandle = ctypes.windll.kernel32.CloseHandle
    CloseHandle.argtypes = [ctypes.c_void_p]
    for h in handles:
        try:
            CloseHandle(h)
        except Exception:
            pass
    handles.clear()


# ── Filesystem info ────────────────────────────────────────────────────────────

def is_ntfs(path: str) -> bool:
    try:
        drive = os.path.splitdrive(path)[0] + "\\"
        fs_name = ctypes.create_unicode_buffer(32)
        ctypes.windll.kernel32.GetVolumeInformationW(
            drive, None, 0, None, None, None, fs_name, 32)
        return fs_name.value.upper() == "NTFS"
    except Exception:
        return False


def convert_to_ntfs(usb_path: str) -> bool:
    try:
        drive = os.path.splitdrive(usb_path)[0]
        r = subprocess.run(
            ["convert", drive, "/FS:NTFS", "/NoSecurity"],
            capture_output=True, timeout=120)
        return r.returncode == 0
    except Exception:
        return False
