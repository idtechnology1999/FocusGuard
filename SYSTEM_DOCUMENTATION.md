# NACOMES FOCUS GUARD — SYSTEM DOCUMENTATION
### Final Year Project | The Polytechnic, Ibadan | Class of 2026
### Developed by NACOMES Final Year Students

---

## TABLE OF CONTENTS
1. [Project Overview](#1-project-overview)
2. [Technology Stack](#2-technology-stack)
3. [System Architecture](#3-system-architecture)
4. [File Structure](#4-file-structure)
5. [How It Works — Step by Step](#5-how-it-works--step-by-step)
6. [USB Authentication System](#6-usb-authentication-system)
7. [USB File Protection System](#7-usb-file-protection-system)
8. [Focus Session System](#8-focus-session-system)
9. [Website Blocking System](#9-website-blocking-system)
10. [GUI & Interface](#10-gui--interface)
11. [Building the EXE](#11-building-the-exe)
12. [Deploying to USB Flash Drive](#12-deploying-to-usb-flash-drive)
13. [Developer Reference](#13-developer-reference)
14. [Troubleshooting](#14-troubleshooting)

---

## 1. PROJECT OVERVIEW

**NACOMES Focus Guard** is a productivity enforcement system that uses a physical USB flash drive as both an installer and authentication key. Once a focus session is started, all selected websites are blocked at the operating-system level and cannot be unblocked by anyone — including the user — until the countdown timer reaches zero.

### Core Objectives
- Force genuine commitment to focus sessions using physical USB authentication
- Block distracting websites at the OS level (not just browser level)
- Persist sessions across system reboots — shutting down does not cancel a session
- Protect USB files from accidental or deliberate deletion
- Provide a modern, professional user interface

### Key Capabilities
- USB-based authentication — no password can substitute the physical key
- OS-level website blocking via Windows hosts file
- Wall-clock session timer — runs on real time, not CPU time
- Session survives reboots — auto-resumes on next login
- Watchdog task in Task Scheduler relaunches app if killed
- System tray integration with live session countdown
- USB drive write-protection via diskpart (permanent, even without app running)
- Programs & Features registration for clean uninstall
- Desktop shortcut and Start Menu entry created automatically

---

## 2. TECHNOLOGY STACK

| Component | Technology |
|-----------|-----------|
| Language | Python 3.14 |
| GUI Framework | PySide6 6.x (Qt6 for Python) |
| USB Detection | WMI (Windows Management Instrumentation) |
| Website Blocking | Windows Hosts File (`C:\Windows\System32\drivers\etc\hosts`) |
| USB Protection | diskpart `attributes volume set readonly` |
| File Locking | Windows API `CreateFileW` via ctypes |
| Session Persistence | JSON config file in Program Files |
| Startup on Boot | Windows Registry `HKCU\...\Run` |
| Watchdog | Windows Task Scheduler (every 5 minutes) |
| Packaging | PyInstaller (single-file EXE with splash screen) |
| Platform | Windows 10 / Windows 11 (64-bit) |

---

## 3. SYSTEM ARCHITECTURE

```
USB Flash Drive
├── FocusGuard.exe          ← Single-file installer + app
├── autorun.inf             ← Auto-launches when USB is inserted
├── config.json             ← Initial seed configuration
└── USB_README.txt          ← User instructions

After Installation (C:\Program Files\FocusGuard\)
├── FocusGuard.exe          ← Installed copy (always up to date)
├── config.json             ← Live config (registered devices, sessions, logs)
└── image\
    └── focus logo.png      ← App logo

Registry Entries
├── HKCU\...\Run\FocusGuard              ← Startup on login
├── HKCU\...\AutoplayHandlers\...        ← AutoPlay handler
└── HKLM\...\Uninstall\FocusGuard        ← Programs & Features entry

Task Scheduler
└── FocusGuardWatchdog                   ← Relaunches every 5 min if killed
```

---

## 4. FILE STRUCTURE

| File | Purpose |
|------|---------|
| `main.py` | Entry point — install flow, admin check, session resume |
| `gui.py` | All UI: lock screen, dashboard, session screen, tray, animations |
| `usb_auth.py` | USB detection and device registration via WMI |
| `usb_protect.py` | USB write-protection via diskpart + Windows file handles |
| `session.py` | Focus session logic, timer, persistence, startup registration |
| `blocker.py` | Hosts file manipulation to block/unblock websites |
| `installer.py` | Install, uninstall, repair, shortcuts, registry entries |
| `config.json` | App configuration (registered devices, active session, logs) |
| `FocusGuard.spec` | PyInstaller build specification |
| `requirements.txt` | Python package dependencies |

---

## 5. HOW IT WORKS — STEP BY STEP

### First Use (Running from USB)
1. User inserts USB → Windows AutoPlay launches `FocusGuard.exe`
2. App requests Administrator privileges (UAC prompt)
3. App checks if already installed → asks user to install
4. `install_to_computer()` copies EXE to `C:\Program Files\FocusGuard\`
5. Desktop shortcut, Start Menu entry, and Programs & Features entry are created
6. App opens — USB is detected as new → asks user to register
7. USB device fingerprint is saved to `config.json` in Program Files
8. USB drive is write-protected via diskpart (permanent, app-independent)
9. First-run Welcome/EULA screen is shown
10. App is now ready

### Subsequent Use (Running from Desktop Shortcut)
1. User opens Focus Guard from Desktop (no USB needed to open)
2. App shows lock screen: "Insert USB to Unlock"
3. User inserts USB → app detects registered device → unlocks to Dashboard
4. User selects website categories and duration → clicks Start Session
5. All selected websites are blocked in the hosts file
6. Session persists — user can remove USB
7. Timer counts down in real wall-clock time
8. On reboot: app auto-starts, resumes session, tray notification shown
9. When timer reaches zero: websites unblocked, session logged

---

## 6. USB AUTHENTICATION SYSTEM

**File:** `usb_auth.py`

The app uses WMI to detect USB drives via `Win32_DiskDrive`. A unique device fingerprint is generated from the drive's `DeviceID`, `Manufacturer`, and `Name` fields and hashed with SHA-256.

```python
def _device_id(device):
    raw = f"{device.DeviceID}-{device.Manufacturer}-{device.Name}"
    return hashlib.sha256(raw.encode()).hexdigest()
```

Registered device IDs are stored in `C:\Program Files\FocusGuard\config.json` under `registered_devices`. Both the USB process and the installed process always read from this single authoritative config file.

**States detected by `detect_focus_guard_usb()`:**
- `(None, False)` → No USB connected
- `(hash, True)` → USB connected but not registered (new)
- `(hash, False)` → USB connected and registered (authenticated)

---

## 7. USB FILE PROTECTION SYSTEM

**File:** `usb_protect.py`

Protection uses two independent layers:

### Layer 1 — diskpart Volume Read-Only (Permanent)
```
diskpart: select volume E → attributes volume set readonly
```
- Sets the entire USB volume to read-only at the OS level
- Works on **FAT32 and NTFS** — no formatting required
- **Persists without the app running** — permanent until removed
- Any attempt to delete, modify, or create files returns:
  *"The disk is write-protected. Remove the write-protection or use another disk."*

**To remove:** Open Focus Guard → click 🔐 button in header → enter developer key

### Layer 2 — Windows File Handle Lock (While App Running)
- Opens Windows handles on key USB files without `FILE_SHARE_DELETE`
- Prevents deletion even if volume protection is temporarily bypassed
- Automatically released when app closes

### Developer Protection Key
```
DELETE-FOCUSG
```
This key is known only to the developer. Users are never shown this key.
To unprotect: Focus Guard app → 🔐 button → enter `DELETE-FOCUSG`

---

## 8. FOCUS SESSION SYSTEM

**File:** `session.py`

Sessions use **wall-clock time**, not elapsed CPU time. This means:
- The session end time (`end_unix`) is stored as a Unix timestamp
- `remaining = end_unix - time.time()` — real time, not paused by shutdown
- Shutting down the computer does NOT pause the timer

### Session Persistence
Active sessions are saved to `config.json`:
```json
{
  "active_session": {
    "end_unix": 1748000000,
    "duration_secs": 1800,
    "sites": ["youtube.com", "facebook.com", ...]
  }
}
```

On the next login, Focus Guard auto-starts (via startup registry), reads `active_session`, and resumes if time remains. A tray notification informs the user.

### Watchdog
A Task Scheduler task (`FocusGuardWatchdog`) relaunches Focus Guard every 5 minutes if it is not running during an active session. This prevents users from killing the process to escape a session.

---

## 9. WEBSITE BLOCKING SYSTEM

**File:** `blocker.py`

Websites are blocked using two mechanisms simultaneously:

**1. Windows Hosts File**
```
C:\Windows\System32\drivers\etc\hosts
```
Each blocked domain is redirected to `127.0.0.1` (localhost):
```
127.0.0.1 youtube.com  # FocusGuard
127.0.0.1 www.youtube.com  # FocusGuard
```
Both the bare domain and `www.` variant are blocked. Entries are tagged with `# FocusGuard` so they can be precisely removed when the session ends.

**2. Windows Firewall Rules**
Outbound firewall rules are created via `netsh advfirewall` to block each site at the network level — providing a second layer of blocking even if the hosts file is cleared.

**Admin rights required** — both the hosts file and firewall require administrator access.

### Built-in Categories
| Category | Sites |
|----------|-------|
| Social Media | Facebook, Instagram, Twitter/X, TikTok, Snapchat, Reddit, LinkedIn... |
| Video & Entertainment | YouTube, Netflix, Twitch, Hulu, Disney+, Prime Video... |
| Gaming | Steam, Epic Games, Roblox, Miniclip... |
| News & Media | CNN, BBC, Fox News, Guardian, NYT... |
| Shopping | Amazon, eBay, AliExpress, Shein... |
| Music & Podcasts | Spotify, SoundCloud, Apple Music... |
| Messaging & Chat | WhatsApp Web, Telegram, Discord, Messenger, Slack... |
| Adult & NSFW | (restricted sites) |

Custom domains can also be added manually.

---

## 10. GUI & INTERFACE

**File:** `gui.py`

Built entirely with PySide6 (Qt6). The app has three main screens managed by a `QStackedWidget`:

### Screens
1. **Lock Screen** — animated glow effect, typewriter hint text, feature pills
2. **Dashboard** — category selection sidebar, duration picker, site preview, start button
3. **Session Screen** — arc timer canvas, countdown, lock banner, progress bar

### Animations
- Lock screen: pulsing glow rings around the logo
- Dashboard: breathing gradient on the Start button
- Session screen: amber border pulse on lock banner, status dot color oscillation

### System Tray
- Normal icon (blue shield) when no session
- Red padlock icon during active session
- Tooltip shows live remaining time
- Right-click menu: Show Window, Exit (Exit hidden during active session)
- Balloon notification on session resume after reboot

### Themes
- Dark mode (default) and Light mode
- Toggle with the ☀️/🌙 button in the header

---

## 11. BUILDING THE EXE

Requires PyInstaller and all dependencies from `requirements.txt`.

```bash
# Install dependencies
pip install -r requirements.txt

# Build using the spec file (recommended)
python -m PyInstaller FocusGuard.spec
```

The built EXE is placed at:
```
dist\FocusGuard.exe
```

The spec file (`FocusGuard.spec`) includes:
- Splash screen from `image/focus logo.png`
- App icon from `image/focus_logo.ico`
- Bundled assets: `image/` folder and `config.json`
- `--onefile` single-file build
- `--windowed` (no console window)

---

## 12. DEPLOYING TO USB FLASH DRIVE

After building, copy these 4 files to the **root** of the USB flash drive:

| File | Note |
|------|------|
| `dist\FocusGuard.exe` | The main application |
| `USB_Package\autorun.inf` | Auto-launch on USB insert |
| `USB_Package\config.json` | Initial seed configuration |
| `USB_Package\USB_README.txt` | User instructions |

**Important:** Files must be in the root of the drive, not inside a folder.

After first run and registration, the USB drive will be write-protected automatically. No files can be deleted without the developer key.

---

## 13. DEVELOPER REFERENCE

### Protection Key
```
DELETE-FOCUSG
```
Enter this in the Focus Guard app (🔐 button) to remove write-protection from the USB drive. Never share this with users.

### config.json Structure
```json
{
  "first_run": true,
  "registered_devices": ["sha256_hash_of_device_id"],
  "active_session": null,
  "session_log": [
    {
      "date": "2026-05-28",
      "start": "10:30:00",
      "duration_minutes": 45
    }
  ]
}
```

### Uninstall
Users can uninstall via Settings → Apps → Focus Guard → Uninstall.
Alternatively, run: `FocusGuard.exe --uninstall`

This removes:
- Program Files folder
- Desktop shortcut
- Start Menu entry
- Startup registry entry
- Task Scheduler watchdog
- Programs & Features entry
- AutoPlay handler

---

## 14. TROUBLESHOOTING

| Problem | Cause | Fix |
|---------|-------|-----|
| App says "Insert USB" even with USB in | Old install — registered devices in wrong config | Uninstall fully, delete `C:\Program Files\FocusGuard\`, reinstall from USB |
| Files on USB can still be deleted | Protection was applied with old build (bug) | Insert USB, open app, click 🔐 button, apply protection again |
| USB not auto-launching | AutoPlay disabled in Windows settings | Run FocusGuard.exe manually |
| Websites not blocking | Hosts file blocked by antivirus | Add Focus Guard to antivirus exclusions |
| App won't open without admin | UAC required for hosts file access | Right-click → Run as Administrator |
| Session didn't resume after reboot | Startup path pointed to USB (old bug) | Fixed in current build — always uses Program Files path |
| Can't unprotect USB | Wrong key entered | Key is `DELETE-FOCUSG` — enter exactly as shown |

---

*NACOMES Focus Guard — Productivity Enforcement System*
*The Polytechnic, Ibadan | Final Year Project 2026*
