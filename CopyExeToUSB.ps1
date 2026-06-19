# CopyExeToUSB.ps1
# Copies only FocusGuard.exe (single file) + support files to the USB.
# Use after rebuilding the EXE to update the USB quickly.

$here   = Split-Path -Parent $MyInvocation.MyCommand.Path
$pkgDir = Join-Path $here "USB_Package"

# Find USB drive
$drive = $null
$candidates = @(Get-WmiObject Win32_LogicalDisk | Where-Object { $_.DriveType -eq 2 })
if ($candidates.Count -eq 0) {
    try {
        $usbPhysical = @(Get-WmiObject Win32_DiskDrive | Where-Object { ($_.InterfaceType -ne $null) -and ($_.InterfaceType -match 'USB') })
        foreach ($ud in $usbPhysical) {
            foreach ($part in @($ud.GetRelated('Win32_DiskPartition'))) {
                foreach ($ld in @($part.GetRelated('Win32_LogicalDisk'))) {
                    if ($ld -and $ld.DeviceID) { $candidates += $ld }
                }
            }
        }
    } catch {}
}
if ($candidates.Count -eq 0) {
    $letter = (Read-Host "No USB detected. Enter drive letter (e.g. E)").Trim().TrimEnd(':').ToUpper()
    $drive = $letter + ":"
} else {
    $drive = $candidates[0].DeviceID
}

if (-not (Test-Path "$drive\")) { Write-Host "Drive $drive not found." -ForegroundColor Red; pause; exit 1 }

# Find EXE source
$exeSrc = Join-Path $pkgDir "FocusGuard.exe"
if (-not (Test-Path $exeSrc)) { $exeSrc = Join-Path $here "dist\FocusGuard.exe" }
if (-not (Test-Path $exeSrc)) { Write-Host "FocusGuard.exe not found in USB_Package\ or dist\." -ForegroundColor Red; pause; exit 1 }

Write-Host ""
Write-Host "  Copying FocusGuard.exe to $drive ..." -ForegroundColor Cyan

# Unlock existing file if protected
try { attrib -R "$drive\FocusGuard.exe" 2>$null } catch {}
try { icacls "$drive\FocusGuard.exe" /grant "Everyone:F" /q 2>$null } catch {}
try { icacls "$drive\FocusGuard.exe" /remove:d "Everyone" /q 2>$null } catch {}

Add-MpPreference -ExclusionPath "$drive\" -ErrorAction SilentlyContinue
Add-MpPreference -ExclusionProcess "FocusGuard.exe" -ErrorAction SilentlyContinue

Copy-Item $exeSrc "$drive\FocusGuard.exe" -Force
try { Unblock-File "$drive\FocusGuard.exe" -ErrorAction SilentlyContinue } catch {}

# Also copy support files
foreach ($f in @("autorun.inf", "config.json", "Setup.bat")) {
    $src = Join-Path $pkgDir $f
    if (Test-Path $src) {
        try { attrib -R "$drive\$f" 2>$null } catch {}
        Copy-Item $src "$drive\$f" -Force
        Write-Host "  Copied $f" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "  Done. Single-file EXE updated on $drive" -ForegroundColor Green
Write-Host ""
pause
