from __future__ import annotations

import locale
import logging
import subprocess
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from .cli_parser import parse_history_result, parse_send_result
from .errors import CliError, CliNotFoundError, CliProcessError, CliTimeoutError, ValidationError
from .models import HistoryQueryResult, SendResult

LOGGER = logging.getLogger("cliclient")


class CommandRunner(Protocol):
    def run(self, args: Sequence[str], timeout: float) -> str: ...


class SubprocessRunner:
    def run(self, args: Sequence[str], timeout: float) -> str:
        try:
            completed = subprocess.run(  # noqa: S603 - executable is intentional user config
                list(args),
                capture_output=True,
                timeout=timeout,
                check=False,
                shell=False,
            )
        except FileNotFoundError as exc:
            raise CliNotFoundError(f"找不到聊天 CLI：{args[0]}，请检查命令前缀或绝对路径") from exc
        except subprocess.TimeoutExpired as exc:
            raise CliTimeoutError(f"聊天 CLI 执行超过 {timeout:g} 秒") from exc
        except OSError as exc:
            raise CliProcessError(f"无法启动聊天 CLI：{exc}") from exc

        stdout = _decode(completed.stdout)
        stderr = _decode(completed.stderr)
        if completed.returncode != 0:
            summary = (stderr or stdout).strip().replace("\n", " ")[:500]
            raise CliProcessError(
                f"聊天 CLI 退出码为 {completed.returncode}: {summary}",
                exit_code=completed.returncode,
            )
        return stdout


def _operation_name(args: Sequence[str]) -> str:
    if len(args) >= 3 and args[1] == "im":
        return args[2]
    return "unknown"


def _decode(value: bytes) -> str:
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError:
        encoding = locale.getpreferredencoding(False) or "utf-8"
        LOGGER.warning("event=cli_encoding_fallback encoding=%s", encoding)
        return value.decode(encoding, errors="replace")


class ChatCliClient:
    def __init__(
        self,
        cli_prefix: str,
        *,
        runner: CommandRunner | None = None,
        timeout: float = 30,
    ) -> None:
        if not cli_prefix.strip():
            raise ValidationError("CLI 前缀不能为空")
        self.cli_prefix = cli_prefix
        self.runner = runner or SubprocessRunner()
        self.timeout = timeout

    def send_to_user(
        self,
        receiver: str,
        text: str | None = None,
        image: Path | None = None,
        file: Path | None = None,
    ) -> SendResult:
        if not receiver:
            raise ValidationError("receiver 不能为空")
        args = [self.cli_prefix, "im", "send-to-user", "--receiver", receiver]
        return self._send(args, text=text, image=image, file=file)

    def send_to_group(
        self,
        group_id: str,
        text: str | None = None,
        image: Path | None = None,
        file: Path | None = None,
    ) -> SendResult:
        if not group_id:
            raise ValidationError("group_id 不能为空")
        args = [self.cli_prefix, "im", "send-to-group", "--group-id", str(group_id)]
        return self._send(args, text=text, image=image, file=file)

    def _send(
        self,
        args: list[str],
        *,
        text: str | None,
        image: Path | None,
        file: Path | None,
    ) -> SendResult:
        if text is None and image is None and file is None:
            raise ValidationError("text、image、file 至少提供一项")
        if text is not None:
            args.extend(("--text", text))
        for flag, path in (("--image", image), ("--file", file)):
            if path is not None:
                normalized = path.expanduser().resolve()
                if not normalized.is_file():
                    raise ValidationError(f"文件不存在：{normalized}")
                args.extend((flag, str(normalized)))
        started_at = time.perf_counter()
        try:
            result = parse_send_result(self.runner.run(args, self.timeout))
        except Exception as exc:
            _log_cli_failure(_operation_name(args), started_at, exc)
            raise
        LOGGER.info(
            "operation=%s elapsed_seconds=%.3f",
            _operation_name(args),
            time.perf_counter() - started_at,
        )
        return result

    def query_history_messages(
        self,
        *,
        group_id: str | None = None,
        user_account: str | None = None,
        query_count: int = 20,
        message_id: str | None = None,
        query_direction: int | None = None,
    ) -> HistoryQueryResult:
        if bool(group_id) == bool(user_account):
            raise ValidationError("group_id 与 user_account 必须且只能提供一个")
        if type(query_count) is not int or not 1 <= query_count <= 100:
            raise ValidationError("query_count 必须是 1 到 100 之间的整数")
        if (message_id is None) != (query_direction is None):
            raise ValidationError("message_id 与 query_direction 必须同时提供")
        if query_direction not in (None, 0, 1):
            raise ValidationError("query_direction 只允许 0 或 1")

        args = [self.cli_prefix, "im", "query-history-message"]
        if group_id:
            args.extend(("--group-id", group_id))
        else:
            args.extend(("--user-account", str(user_account)))
        args.extend(("--query-count", str(query_count)))
        if message_id is not None:
            args.extend(("--message-id", message_id, "--query-direction", str(query_direction)))
        started_at = time.perf_counter()
        try:
            result = parse_history_result(self.runner.run(args, self.timeout))
        except Exception as exc:
            _log_cli_failure(_operation_name(args), started_at, exc, group_id or user_account)
            raise
        LOGGER.info(
            "[%s] count=%s elapsed_seconds=%.3f",
            group_id or user_account,
            result.total_count,
            time.perf_counter() - started_at,
        )
        return result


def _log_cli_failure(
    operation: str,
    started_at: float,
    exc: Exception,
    target: str | None = None,
) -> None:
    category = exc.category if isinstance(exc, CliError) else type(exc).__name__
    exit_code = exc.exit_code if isinstance(exc, CliError) else None
    prefix = f"[{target}] " if target else ""
    LOGGER.error(
        "%soperation=%s failed elapsed_seconds=%.3f error_category=%s exit_code=%s",
        prefix,
        operation,
        time.perf_counter() - started_at,
        category,
        exit_code,
    )
