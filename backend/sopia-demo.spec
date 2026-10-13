# PyInstaller spec for the offline SOPIA demo.
#
# Build with:
#   cd backend
#   venv\Scripts\python.exe -m PyInstaller --noconfirm sopia-demo.spec
#
# Produces dist/sopia-api/ - a folder build rather than a single file, because a
# one-file executable would unpack ~150 MB to a temp directory on every launch,
# which is a poor experience for a demo that is started repeatedly.
#
# The frontend is deliberately NOT embedded: it ships alongside the executable so
# the UI can be updated without rebuilding the binary.

import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Uvicorn resolves its loop/protocol implementations dynamically, so static
# analysis misses them and the server fails at start-up without these.
hidden = [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    "sqlalchemy.dialects.sqlite",
    "sqlalchemy.sql.default_comparator",
    "app.main",
]
hidden += collect_submodules("app")

# pdfminer ships character maps that are read at runtime, not imported.
datas = collect_data_files("pdfminer")

# PostgreSQL is not part of the offline build: the demo runs on SQLite. Dropping
# the driver, the migration tool and test-only packages keeps the binary lean.
excludes = [
    "psycopg2",
    "alembic",
    "pytest",
    "httpx",
    "tkinter",
    "matplotlib",
    "IPython",
    "pandas",
    "scipy",
]

a = Analysis(
    ["serve.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="sopia-api",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="sopia-api",
)
