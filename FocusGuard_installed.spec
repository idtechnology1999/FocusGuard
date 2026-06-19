# -*- mode: python ; coding: utf-8 -*-
# Onedir build -- installed to Program Files for fast launch (no temp extraction).

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('image', 'image'), ('config.json', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'unittest', 'doctest', 'pydoc', 'difflib',
        'ftplib', 'imaplib', 'poplib', 'smtplib', 'telnetlib',
        'xmlrpc', 'antigravity', 'turtle', 'turtledemo',
        'PySide6.Qt3DAnimation', 'PySide6.Qt3DCore', 'PySide6.Qt3DExtras',
        'PySide6.Qt3DInput', 'PySide6.Qt3DLogic', 'PySide6.Qt3DRender',
        'PySide6.QtBluetooth', 'PySide6.QtCharts', 'PySide6.QtDataVisualization',
        'PySide6.QtDesigner', 'PySide6.QtHelp', 'PySide6.QtLocation',
        'PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets',
        'PySide6.QtNfc', 'PySide6.QtPdf', 'PySide6.QtPdfWidgets',
        'PySide6.QtPositioning', 'PySide6.QtPrintSupport',
        'PySide6.QtQuick', 'PySide6.QtQuick3D', 'PySide6.QtQuickWidgets',
        'PySide6.QtRemoteObjects', 'PySide6.QtScxml', 'PySide6.QtSensors',
        'PySide6.QtSerialBus', 'PySide6.QtSerialPort', 'PySide6.QtSql',
        'PySide6.QtStateMachine', 'PySide6.QtTest', 'PySide6.QtTextToSpeech',
        'PySide6.QtUiTools', 'PySide6.QtWebChannel', 'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineQuick', 'PySide6.QtWebEngineWidgets',
        'PySide6.QtWebSockets', 'PySide6.QtXml',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
splash = Splash(
    'image/logo.png',
    binaries=a.binaries,
    datas=a.datas,
    text_pos=None,
    text_size=12,
    minify_script=True,
    always_on_top=True,
)

exe = EXE(
    pyz,
    a.scripts,
    [],
    splash,
    [],
    name='FocusGuard',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['image\\focus_logo.ico'],
    uac_admin=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    splash.binaries,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='FocusGuard_installed',
)
