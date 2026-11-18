# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for CV Studio (Windows, one-folder build: pyinstaller --noconfirm --clean "CV Studio.spec").
a = Analysis(
    ['run_app.py'],
    pathex=[],
    binaries=[],
    datas=[('cvstudio/assets', 'cvstudio/assets')],       # icon + bundled fonts + licences
    hiddenimports=["PySide6.QtPdf"],
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtQml',
              'PySide6.Qt3DCore', 'PySide6.QtMultimedia', 'PySide6.QtCharts', 'PySide6.QtDataVisualization'],
    noarchive=False, optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='CVStudio', debug=False, bootloader_ignore_signals=False,
          strip=False, upx=False, console=False, disable_windowed_traceback=False, icon='cvstudio/assets/cv-studio.ico')
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='CVStudio')
