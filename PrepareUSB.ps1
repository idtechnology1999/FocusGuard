# PrepareUSB.ps1 - Copies Focus Guard files to the USB key and protects them.
# Run via PrepareUSB.bat (recommended) or right-click -> Run as Administrator.

$ErrorActionPreference = "Stop"
trap {
    Write-Host ""
    Write-Host "  ERROR: $_" -ForegroundColor Red
    Write-Host ""
    pause
    exit 1
}

# --------------------------------------------------------------------------
# 1. Locate USB drive
# --------------------------------------------------------------------------
# Pass 1: FAT32/exFAT removable drives (DriveType=2) - most common
$candidates = @(Get-WmiObject Win32_LogicalDisk | Where-Object { $_.DriveType -eq 2 })

# Pass 2: NTFS USB drives - they appear as DriveType=3 (fixed) in WMI.
# Detect them via Win32_DiskDrive InterfaceType=USB, then follow associations.
if ($candidates.Count -eq 0) {
    try {
        $usbPhysical = @(Get-WmiObject Win32_DiskDrive |
            Where-Object { ($_.InterfaceType -ne $null) -and ($_.InterfaceType -match 'USB') })
        foreach ($ud in $usbPhysical) {
            foreach ($part in @($ud.GetRelated('Win32_DiskPartition'))) {
                foreach ($ld in @($part.GetRelated('Win32_LogicalDisk'))) {
                    if ($ld -and $ld.DeviceID) { $candidates += $ld }
                }
            }
        }
    } catch {}
}

# Pass 3: still nothing - let the user type the drive letter
if ($candidates.Count -eq 0) {
    Write-Host ""
    Write-Host "  Could not auto-detect your USB drive." -ForegroundColor Yellow
    Write-Host "  Open File Explorer, note your USB drive letter, then type it below." -ForegroundColor Yellow
    $letter = (Read-Host "  Drive letter (e.g. E), or press Enter to exit").Trim().TrimEnd(':').ToUpper()
    if (-not $letter) { Write-Host "  Cancelled." -ForegroundColor Red; pause; exit 1 }
    $drive = $letter + ":"
    if (-not (Test-Path "$drive\")) {
        Write-Host "  Drive $drive not found." -ForegroundColor Red; pause; exit 1
    }
} elseif ($candidates.Count -gt 1) {
    Write-Host ""
    Write-Host "  Multiple drives found:" -ForegroundColor Yellow
    $candidates | ForEach-Object {
        $sz = if ($_.Size) { "($([math]::Round($_.Size/1GB,1)) GB)" } else { "" }
        Write-Host "    $($_.DeviceID)  $($_.VolumeName)  $sz"
    }
    $letter = (Read-Host "`n  Enter drive letter to use (e.g. E)").Trim().TrimEnd(':').ToUpper()
    $drive  = $letter + ":"
    if (-not (Test-Path "$drive\")) {
        Write-Host "  Drive $drive not found." -ForegroundColor Red; pause; exit 1
    }
} else {
    $drive = $candidates[0].DeviceID
}
if (-not (Test-Path "$drive\")) {
    Write-Host "  Drive $drive not found." -ForegroundColor Red; pause; exit 1
}

Write-Host ""
Write-Host "  Focus Guard USB Preparation" -ForegroundColor Cyan
Write-Host "  Target drive : $drive" -ForegroundColor Cyan
Write-Host ""

# --------------------------------------------------------------------------
# 2. Locate source files
# --------------------------------------------------------------------------
$here   = Split-Path -Parent $MyInvocation.MyCommand.Path
$exeSrc = Join-Path $here "dist\FocusGuard.exe"
$pkgDir = Join-Path $here "USB_Package"

if (-not (Test-Path $exeSrc)) {
    $exeSrc = Join-Path $pkgDir "FocusGuard.exe"
}
if (-not (Test-Path $exeSrc)) {
    Write-Host "  ERROR: FocusGuard.exe not found in dist\ or USB_Package\." -ForegroundColor Red
    pause; exit 1
}

# --------------------------------------------------------------------------
# 3. Unlock any existing protected files first (reset beats deny rules)
# --------------------------------------------------------------------------
$allFiles = @("FocusGuard.exe", "autorun.inf", "config.json", "USB_README.txt", "Launch Focus Guard.bat", "Setup.bat")
foreach ($f in $allFiles) {
    $dest = "$drive\$f"
    if (Test-Path $dest) {
        try { icacls $dest /reset /q 2>$null }          catch {}
        try { icacls $dest /grant "Everyone:(F)" /q 2>$null } catch {}
        try { attrib -R -S -H $dest }                   catch {}
    }
}
# Remove the old bat launcher - no longer needed
if (Test-Path "$drive\Launch Focus Guard.bat") {
    Remove-Item "$drive\Launch Focus Guard.bat" -Force -ErrorAction SilentlyContinue
}

# --------------------------------------------------------------------------
# 3b. Fingerprint this USB and write its ID into config.json
# This pre-registers the device so ONLY this USB can unlock the app.
# Any other flash drive (even one with FocusGuard.exe copied onto it) is rejected.
# --------------------------------------------------------------------------
Write-Host "  Registering USB device fingerprint..."
$deviceId = $null

# Primary: PNPDeviceID from Win32_DiskDrive (matches usb_auth.py _device_id logic)
try {
    $usbDisks = @(Get-WmiObject Win32_DiskDrive |
        Where-Object { ($_.InterfaceType -ne $null) -and ($_.InterfaceType -match 'USB') })
    foreach ($ud in $usbDisks) {
        foreach ($part in @($ud.GetRelated('Win32_DiskPartition'))) {
            foreach ($ld in @($part.GetRelated('Win32_LogicalDisk'))) {
                if ($ld.DeviceID -eq $drive -and $ud.PNPDeviceID) {
                    $sha256 = [System.Security.Cryptography.SHA256]::Create()
                    $bytes  = [System.Text.Encoding]::UTF8.GetBytes($ud.PNPDeviceID)
                    $deviceId = [System.BitConverter]::ToString($sha256.ComputeHash($bytes)).Replace("-","").ToLower()
                }
            }
        }
    }
} catch {}

# Fallback: volume serial number (matches usb_auth.py WMI-fallback logic)
if (-not $deviceId) {
    try {
        $logDisk = Get-WmiObject Win32_LogicalDisk | Where-Object {$_.DeviceID -eq $drive}
        if ($logDisk -and $logDisk.VolumeSerialNumber) {
            $vsnDec  = [uint32]::Parse($logDisk.VolumeSerialNumber, [System.Globalization.NumberStyles]::HexNumber)
            $sha256  = [System.Security.Cryptography.SHA256]::Create()
            $bytes   = [System.Text.Encoding]::UTF8.GetBytes("vsn:$vsnDec")
            $deviceId = [System.BitConverter]::ToString($sha256.ComputeHash($bytes)).Replace("-","").ToLower()
        }
    } catch {}
}

if ($deviceId) {
    $cfgSrc  = Join-Path $pkgDir "config.json"
    $cfgJson = Get-Content $cfgSrc -Raw | ConvertFrom-Json
    $cfgJson.registered_devices = @($deviceId)
    $cfgJson | ConvertTo-Json -Depth 10 | Out-File $cfgSrc -Encoding utf8 -NoNewline
    Write-Host "        Device ID registered: $($deviceId.Substring(0,16))..."
} else {
    Write-Host "        WARNING: could not fingerprint USB - registration skipped" -ForegroundColor Yellow
}
Write-Host ""

# --------------------------------------------------------------------------
# 4. Defender exclusion FIRST, then copy
# CRITICAL: exclusion must be added BEFORE copying FocusGuard.exe.
# Defender scans files as they are written to disk. If we copy first and
# add the exclusion afterwards, Defender may quarantine the EXE mid-copy.
# --------------------------------------------------------------------------
Write-Host "  [1/3] Adding Defender exclusions before copy..."
try {
    Add-MpPreference -ExclusionPath "$drive\" -ErrorAction SilentlyContinue
    Add-MpPreference -ExclusionProcess "FocusGuard.exe" -ErrorAction SilentlyContinue
    Write-Host "        Defender exclusion set for $drive\"
} catch {
    Write-Host "        (Defender exclusion skipped - may not be running)" -ForegroundColor Yellow
}

Write-Host "  Copying files..."
Copy-Item $exeSrc "$drive\FocusGuard.exe" -Force
Write-Host "        FocusGuard.exe  ->  $drive\"

foreach ($extra in @("autorun.inf", "config.json", "USB_README.txt", "Setup.bat")) {
    $src = Join-Path $pkgDir $extra
    if (Test-Path $src) {
        Copy-Item $src "$drive\$extra" -Force
        Write-Host "        $extra  ->  $drive\"
    }
}

# Copy onedir build folder (fast-launch installed version)
$installedSrc = Join-Path $pkgDir "FocusGuard_installed"
if (Test-Path $installedSrc) {
    $installedDst = "$drive\FocusGuard_installed"
    if (Test-Path $installedDst) { Remove-Item $installedDst -Recurse -Force }
    Copy-Item $installedSrc $installedDst -Recurse -Force
    Write-Host "        FocusGuard_installed/  ->  $drive\"
}

# Remove Zone Identifier (Mark of the Web) so the EXE runs without a block warning.
try { Unblock-File "$drive\FocusGuard.exe" -ErrorAction SilentlyContinue } catch {}
try { Unblock-File "$drive\Setup.bat"      -ErrorAction SilentlyContinue } catch {}
Write-Host ""

# --------------------------------------------------------------------------
# 5. Detect filesystem
# --------------------------------------------------------------------------
$fsType = (Get-WmiObject Win32_LogicalDisk | Where-Object {$_.DeviceID -eq $drive}).FileSystem
Write-Host "  [2/3] Filesystem: $fsType"

# --------------------------------------------------------------------------
# 6. Apply protection
# --------------------------------------------------------------------------
Write-Host "  [3/3] Applying protection..."

# FocusGuard.exe - VISIBLE (user can double-click) + delete-protected.
# Deny only D (Delete). Do NOT deny WA (Write Attributes) because
# Windows needs WA when launching an exe to update file timestamps.
$exeDest = "$drive\FocusGuard.exe"
icacls $exeDest /reset /q 2>$null
attrib +R $exeDest
if ($fsType -eq "NTFS") {
    icacls $exeDest /inheritance:d /q 2>$null
    icacls $exeDest /grant:r "BUILTIN\Administrators:F" /q 2>$null
    icacls $exeDest /grant:r "SYSTEM:F" /q 2>$null
    icacls $exeDest /grant:r "Everyone:(RX,WA)" /q 2>$null
    icacls $exeDest /deny  "Everyone:(D)" /q 2>$null
    Write-Host "        FocusGuard.exe  : visible, executable, delete-locked (NTFS)"
} else {
    Write-Host "        FocusGuard.exe  : visible, read-only"
}

# autorun.inf - VISIBLE (Windows needs to read it for AutoPlay)
$autorunDest = "$drive\autorun.inf"
if (Test-Path $autorunDest) {
    attrib +R $autorunDest
    Write-Host "        autorun.inf     : visible, read-only"
}

# Setup.bat - VISIBLE (first-time setup on any new machine)
$setupDest = "$drive\Setup.bat"
if (Test-Path $setupDest) {
    attrib +R $setupDest
    Write-Host "        Setup.bat       : visible, read-only"
}

# Support files - HIDDEN (user never needs to touch these)
foreach ($f in @("config.json", "USB_README.txt")) {
    $dest = "$drive\$f"
    if (-not (Test-Path $dest)) { continue }
    attrib +R +S +H $dest
    if ($fsType -eq "NTFS") {
        icacls $dest /inheritance:d /q 2>$null
        icacls $dest /grant:r "BUILTIN\Administrators:F" /q 2>$null
        icacls $dest /grant:r "SYSTEM:F" /q 2>$null
        icacls $dest /deny "Everyone:(D,W,WA,AD)" /q 2>$null
    }
    Write-Host "        $f  : hidden, protected"
}

Write-Host ""
if ($fsType -ne "NTFS") {
    Write-Host "  NOTE: $fsType only supports read-only protection." -ForegroundColor Yellow
    Write-Host "  For stronger delete-lock, reformat as NTFS then run again." -ForegroundColor Yellow
    Write-Host ""
}

Write-Host "  =============================================" -ForegroundColor Green
Write-Host "   USB key is ready." -ForegroundColor Green
Write-Host ""
Write-Host "   What the user sees on the USB:" -ForegroundColor White
Write-Host "     FocusGuard.exe   (main app - double-click to run)" -ForegroundColor White
Write-Host "     Setup.bat        (first-time setup on any new computer)" -ForegroundColor White
Write-Host "     autorun.inf      (AutoPlay, invisible on most machines)" -ForegroundColor White
Write-Host ""
Write-Host "   On a computer with Focus Guard already installed:" -ForegroundColor White
Write-Host "     Insert USB -> app opens automatically" -ForegroundColor White
Write-Host ""
Write-Host "   On a brand-new computer (first time only):" -ForegroundColor White
Write-Host "     1. Open USB drive in File Explorer" -ForegroundColor Cyan
Write-Host "     2. Double-click Setup.bat -> click Yes to UAC prompt" -ForegroundColor Cyan
Write-Host "     3. Focus Guard will launch and install automatically" -ForegroundColor Cyan
Write-Host "     After that, just insert USB -> app opens by itself" -ForegroundColor Cyan
Write-Host "  =============================================" -ForegroundColor Green
Write-Host ""
pause
