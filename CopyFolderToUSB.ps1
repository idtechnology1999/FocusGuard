# CopyFolderToUSB.ps1
# Copies FocusGuard_installed/ folder + support files to the USB.
# This is what gets installed to Program Files on a student computer.
# Use after rebuilding the onedir version.

$here   = Split-Path -Parent $MyInvocation.MyCommand.Path
$pkgDir = Join-Path $here "USB_Package"
$folderSrc = Join-Path $pkgDir "FocusGuard_installed"

if (-not (Test-Path $folderSrc)) {
    $folderSrc = Join-Path $here "dist\FocusGuard_installed"
}
if (-not (Test-Path $folderSrc)) {
    Write-Host "FocusGuard_installed folder not found. Build it first." -ForegroundColor Red
    pause; exit 1
}

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

$folderDst = "$drive\FocusGuard_installed"
$sizeMB = [math]::Round((Get-ChildItem $folderSrc -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1MB, 0)

Write-Host ""
Write-Host "  Copying FocusGuard_installed/ to $drive  ($sizeMB MB) ..." -ForegroundColor Cyan
Write-Host "  This may take a minute..."

# Remove old version if present
if (Test-Path $folderDst) { Remove-Item $folderDst -Recurse -Force }
Copy-Item $folderSrc $folderDst -Recurse -Force
Write-Host "  FocusGuard_installed/ copied." -ForegroundColor Green

# Also copy support files needed on USB root
Write-Host ""
Write-Host "  Copying support files..." -ForegroundColor Cyan
foreach ($f in @("config.json", "Setup.bat", "autorun.inf", "USB_README.txt")) {
    $src = Join-Path $pkgDir $f
    if (Test-Path $src) {
        try { attrib -R "$drive\$f" 2>$null } catch {}
        Copy-Item $src "$drive\$f" -Force
        Write-Host "  Copied $f" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "  Done. USB is ready with folder build on $drive" -ForegroundColor Green
Write-Host ""
pause
