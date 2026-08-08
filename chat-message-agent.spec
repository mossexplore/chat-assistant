# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

project_root = Path(SPECPATH)
source_root = project_root / "src"
web_root = source_root / "chat_message_agent" / "web"
sys.path.insert(0, str(source_root))

from chat_message_agent.version import __version__ as app_version

version_file = project_root / "build" / "version_info.txt"

a = Analysis(
    [str(source_root / "chat_message_agent" / "__main__.py")],
    pathex=[str(source_root)],
    binaries=[],
    datas=[
        (str(web_root / "templates"), "chat_message_agent/web/templates"),
        (str(web_root / "static"), "chat_message_agent/web/static"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=f"chat-message-agent-v{app_version}",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    version=str(version_file) if version_file.is_file() else None,
)
