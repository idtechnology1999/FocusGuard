# 🛡️ Focus Guard USB Setup

## 📦 What's on this USB?

This USB contains the Focus Guard application - a productivity tool that blocks distracting websites during focus sessions.

## 🚀 First Time Setup

1. **Insert this USB** into your computer
2. **Double-click `FocusGuard.exe`** (or run from autorun prompt)
3. Click **"Yes"** when Windows asks for Administrator permission
4. Click **"Yes"** when asked "Do you want to install?"
5. The app will be installed to `C:\Program Files\FocusGuard\`
6. A desktop shortcut will be created

## 🔑 How It Works

### Starting a Focus Session
1. Insert your USB key
2. Open Focus Guard (from desktop shortcut or Start menu)
3. Select your focus duration (15-90 minutes)
4. Click "▶ Start Session"
5. **You can now remove the USB** - the session will continue

### During a Session
- Distracting websites are blocked at the system level
- Timer counts down in the app window
- Removing USB does NOT stop the session
- Session continues until timer reaches 00:00

### Starting Another Session
- **USB must be re-inserted** to start a new session
- This prevents you from starting unlimited sessions
- Physical key = physical commitment to focus

## 🖥️ Using on Multiple Computers

This same USB works on multiple computers:

1. Insert USB into Computer A → Install → Register USB
2. Insert USB into Computer B → Install → Register USB
3. Now you can use the same USB on both computers

Each computer remembers your USB and allows you to start sessions when it's inserted.

## ⚠️ Important Notes

- **Keep this USB safe** - it's your authentication key
- **Admin rights required** - needed to block websites at system level
- **Windows only** - currently supports Windows 10/11
- **One USB per user** - each person should have their own USB key

## 🛠️ Troubleshooting

### "USB Key Required" message
- Make sure USB is fully inserted
- Try a different USB port
- Check Device Manager to verify USB is detected

### Websites not blocking
- Ensure you ran as Administrator
- Check Windows Firewall is enabled
- Verify hosts file at `C:\Windows\System32\drivers\etc\hosts`

### Can't install
- Right-click `FocusGuard.exe` → "Run as Administrator"
- Disable antivirus temporarily during installation
- Check you have write permissions to Program Files

## 📞 Support

For issues or questions, check the documentation in the installation folder:
`C:\Program Files\FocusGuard\SYSTEM_DOCUMENTATION.md`

---

**Focus Guard v2.0** - Hardware-Authenticated Productivity Enforcement System
