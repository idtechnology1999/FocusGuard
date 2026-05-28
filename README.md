# NACOMES Focus Guard

**USB-Authenticated Productivity Enforcement System**
Final Year Project — The Polytechnic, Ibadan | NACOMES | Class of 2026

---

## What It Does

Focus Guard blocks distracting websites at the OS level during a timed focus session.
Once started, **no one can stop the session** — not even the person who started it — until the countdown reaches zero.

A physical **USB flash drive** acts as the authentication key.

---

## Key Features

- USB-based authentication — no password can substitute the physical key
- Blocks websites at OS level (hosts file + Windows Firewall)
- Session persists across reboots — shutting down does not cancel it
- Watchdog process relaunches app if killed during session
- USB drive write-protection (diskpart) — files cannot be deleted without developer key
- Modern PySide6 GUI with animations and system tray integration
- Programs & Features registration for clean uninstall

---

## Tech Stack

| | |
|--|--|
| Language | Python 3.14 |
| GUI | PySide6 (Qt6) |
| USB Detection | WMI |
| Packaging | PyInstaller (single-file EXE) |
| Platform | Windows 10 / 11 |

---

## Project Structure

```
├── main.py           # Entry point
├── gui.py            # All UI screens and animations
├── usb_auth.py       # USB detection and registration
├── usb_protect.py    # USB write-protection (diskpart)
├── session.py        # Focus session logic and persistence
├── blocker.py        # Hosts file + firewall website blocking
├── installer.py      # Install, uninstall, shortcuts, registry
├── config.json       # Seed configuration
├── FocusGuard.spec   # PyInstaller build spec
├── requirements.txt  # Python dependencies
├── USB_Package/      # Files to copy to USB flash drive
└── SYSTEM_DOCUMENTATION.md  # Full technical documentation
```

---

## Building

```bash
pip install -r requirements.txt
python -m PyInstaller FocusGuard.spec
```

Output: `dist/FocusGuard.exe`

## Deploying to USB

Copy these files to the root of a USB flash drive:
- `dist/FocusGuard.exe`
- `USB_Package/autorun.inf`
- `USB_Package/config.json`
- `USB_Package/USB_README.txt`

---

## Full Documentation

See [SYSTEM_DOCUMENTATION.md](SYSTEM_DOCUMENTATION.md) for complete technical details.

---

*Developed by NACOMES Final Year Students — The Polytechnic, Ibadan, 2026*
