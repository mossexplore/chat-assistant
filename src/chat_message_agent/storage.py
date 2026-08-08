from __future__ import annotations

import json
import os
import tempfile
from contextlib import suppress
from pathlib import Path
from typing import Any

from .errors import PersistenceError


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    """Write JSON through a sibling temporary file and atomically replace the target."""
    temp_name: str | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    except OSError as exc:
        if temp_name:
            with suppress(OSError):
                Path(temp_name).unlink(missing_ok=True)
        raise PersistenceError(f"无法写入 {path}: {exc}") from exc
