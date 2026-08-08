from __future__ import annotations

import argparse
import sys

from chat_message_agent.app import build_application
from chat_message_agent.version import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Windows 聊天消息查询程序")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--port", type=int, default=8765, help="本机配置页面端口")
    parser.add_argument("--no-browser", action="store_true", help="启动时不自动打开浏览器")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not 1 <= args.port <= 65535:
        print("错误：端口必须在 1 到 65535 之间", file=sys.stderr)
        return 2
    try:
        application = build_application(port=args.port)
        application.run(open_browser=not args.no_browser)
    except Exception as exc:
        print(f"启动失败：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
