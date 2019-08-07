# -*- mode: python -*-

import os

current_path = os.path.dirname(os.path.abspath(os.getcwd()))

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[        
        current_path,
    ],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='UniqueBibleApp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    runtime_tmpdir=None,
    console=False
)

info_plist = {
    'NSHighResolutionCapable': True,
    'LSEnvironment': {
        'LANG': 'de_DE.UTF-8',
        'LC_CTYPE': 'de_DE.UTF-8'
    },
    'NSRequiresAquaSystemAppearance': False
}

app = BUNDLE(
    exe,
    name='UniqueBibleApp.app',
    icon=None,
    bundle_identifier=None,
    info_plist=info_plist
)
