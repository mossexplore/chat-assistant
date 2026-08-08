from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SOURCE_ROOT))

from chat_message_agent.version import __version__  # noqa: E402


def version_tuple(version: str) -> tuple[int, int, int, int]:
    parts: list[int] = []
    for segment in version.split(".")[:4]:
        match = re.match(r"\d+", segment)
        parts.append(int(match.group()) if match else 0)
    parts.extend([0] * (4 - len(parts)))
    if any(part > 65535 for part in parts):
        raise ValueError("版本号的每个数字部分必须小于等于 65535")
    return parts[0], parts[1], parts[2], parts[3]


def render_version_info(version: str) -> str:
    numeric_version = version_tuple(version)
    executable_name = f"chat-message-agent-v{version}.exe"
    return f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={numeric_version},
    prodvers={numeric_version},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [
          StringStruct('CompanyName', 'mossexplore'),
          StringStruct('FileDescription', 'Windows Chat Message Query Agent'),
          StringStruct('FileVersion', '{version}'),
          StringStruct('InternalName', 'chat-message-agent'),
          StringStruct('OriginalFilename', '{executable_name}'),
          StringStruct('ProductName', 'Chat Message Agent'),
          StringStruct('ProductVersion', '{version}')
        ]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: generate_version_info.py OUTPUT_PATH", file=sys.stderr)
        return 2
    output_path = Path(sys.argv[1])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_version_info(__version__), encoding="utf-8")
    print(f"Generated Windows version metadata for {__version__}: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
