# PyInstaller spec: freezes the Nitro Forge engine + sidecar API into one
# windowless exe the Tauri shell spawns in production.
#
# Build:  pyinstaller sidecar.spec
# Output: dist/nitro-forge-sidecar.exe
#
# NOTE: sidecar/server.py calls multiprocessing.freeze_support() first thing
# under __main__. That line is what prevents py-cpuinfo's child processes
# from re-running the whole app ("opens hundreds of times" bug). Keep it.

a = Analysis(
    ['sidecar\\server.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('core\\data\\game_catalog.json', 'core\\data'),
    ],
    hiddenimports=[
        'wmi', 'cpuinfo', 'GPUtil', 'pynvml', 'screeninfo',
        'win32com', 'win32com.client', 'pythoncom', 'pywintypes',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'PIL', 'numpy.f2py'],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='nitro-forge-sidecar',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,               # UPX triggers AV false-positives on system tools
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
