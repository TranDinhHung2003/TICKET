# PyInstaller spec — bản bảo vệ (AES payload + bootstrap)
# Build:
#   python protect/build_protected.py
#   pyinstaller fb_poster_secure.spec --clean --noconfirm

from pathlib import Path

block_cipher = None
ROOT = Path(".").resolve()
PROT = ROOT / "build_protected"

a = Analysis(
    [str(PROT / "run_protected.py")],
    pathex=[str(ROOT), str(PROT)],
    binaries=[],
    datas=[
        (str(PROT / "payloads"), "payloads"),
    ],
    hiddenimports=[
        "requests",
        "tenacity",
        "tkinter",
        "tkinter.ttk",
        "tkinter.scrolledtext",
        "tkinter.filedialog",
        "tkinter.messagebox",
        "Cryptodome",
        "Cryptodome.Cipher",
        "Cryptodome.Cipher.AES",
        "json",
        "threading",
        "re",
        "uuid",
        "pathlib",
        "marshal",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["matplotlib", "numpy", "pandas", "scipy"],
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
    name="FacebookGroupPoster",
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
