# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['src/pyama_qt/visualization/main.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=[
        'pyama_qt',
        'pyama_qt.visualization',
        'pyama_qt.visualization.main',
        'pyama_qt.visualization.ui',
        'pyama_qt.visualization.ui.main_window',
        'pyama_qt.visualization.ui.widgets',
        'pyama_qt.visualization.services',
        'pyama_qt.visualization.utils',
        'pyama_qt.core',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'numpy',
        'scipy',
        'scikit-image',
        'matplotlib',
        'pandas',
        'dask',
        'xarray',
        'nd2',
        'numba',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='pyama-viz',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Set to True for console application
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
