# Windows 聊天消息查询程序需求设计说明书（完整备份）

## 1. 文档信息

| 项目 | 内容 |
| --- | --- |
| 文档用途 | 汇总项目全部历史需求、最终决策和当前实现，作为独立备份基线 |
| 备份日期 | 2026-08-16 |
| 基线版本 | `0.5.0` |
| 基线提交 | `7c654a8 Refresh latest messages on startup (#7)` |
| 代码仓库 | `https://github.com/mossexplore/chat-assistant.git` |
| 目标平台 | Windows 10/11 64 位 |
| 开发语言 | Python 3.11 及以上兼容版本 |
| Web 框架 | Flask |
| 打包工具 | PyInstaller |
| 最终交付物 | 源代码、测试、设计说明、`package.bat` 和带版本号的 Windows EXE |

本文档以当前最终需求为准。历史对话中被后续要求替代的内容不再作为有效需求，尤其是“程序重启后从旧游标继续追赶历史消息”的旧行为已经废止。

## 2. 项目背景

用户的 Windows 电脑已安装并登录聊天软件，同时具备可用的聊天 CLI。项目需要封装该 CLI，并提供一个本机 Web 配置页面，按配置周期依次查询多个群组的消息。

程序当前只负责查询、解析、记录消息和维护游标。消息处理接口已预留，但默认实现为 No-Op，不调用知识库，不自动回复，也不转发消息。

## 3. 项目目标

- 安全封装发送私聊、发送群聊和查询历史消息的 CLI 能力。
- 支持配置多个群组 ID，每行一个，并由单一后台线程依次查询。
- 每次程序启动后优先获取各群组最新指定条数的消息，忽略重启期间积压的过期历史消息。
- 同一次运行中使用消息 ID 游标执行增量查询和分页。
- 提供仅本机可访问的配置管理页面，保存后实时生效。
- 分离程序日志、完整消息日志和操作日志。
- 支持引用回复消息正文解析。
- 生成文件名和 Windows 文件属性均带版本号的单文件 EXE。
- 保持模块可测试、可扩展，为后续知识库处理预留接口。

## 4. 范围

### 4.1 本期范围

- Windows EXE 主程序和命令行入口。
- CLI 参数构造、进程执行、超时控制、编码处理和响应解析。
- 私聊、群聊发送接口。
- 私聊、群聊历史消息查询接口。
- 多群组串行调度。
- 启动初始化查询、运行期增量查询和分页。
- 配置及游标持久化。
- 本机 Flask 配置页面及 JSON API。
- 配置实时生效。
- 三类日志文件和日志轮转。
- 普通消息及引用回复消息的日志正文处理。
- 自动化测试、静态检查及 PyInstaller 打包。

### 4.2 非目标

- 不调用知识库 API。
- 不实现自动回复、消息转发或内容判断业务。
- 不并发查询多个群组。
- 不在页面中展示历史消息或提供手工发送功能。
- 不提供远程访问、账号体系或权限管理。
- 不提供 Windows 服务、系统托盘、安装包、开机启动或自动升级。
- 不负责安装、登录或升级聊天软件及聊天 CLI。

## 5. 最终产品决策

| 决策项 | 最终结论 |
| --- | --- |
| Web 页面 | Flask + 原生 HTML/CSS/JavaScript，资源全部本地打包 |
| 监听地址 | 仅 `127.0.0.1` |
| 默认端口 | `8765`，支持 `--port` 修改 |
| 浏览器 | 启动后默认自动打开；支持 `--no-browser` |
| 数据目录 | EXE 模式为 EXE 所在目录；源码模式为当前工作目录 |
| 多群组 | 最多 100 个数字字符串群组 ID，串行查询 |
| 默认周期 | 60 秒 |
| 默认首次条数 | 2 条 |
| 启动后首次查询 | 每个群组均忽略旧游标，不传 `--message-id`，直接查询最新 N 条 |
| 运行期后续查询 | 使用当前运行中保存的游标和 `--query-direction 1` |
| 消息日志开关 | 默认关闭，保存后实时生效 |
| 当前版本 | `0.5.0` |
| 发布分支策略 | 直接在本地 `main` 提交并推送远端 `main`，不创建分支或 PR |

## 6. 配置设计

配置文件为 EXE 所在目录的 `config.json`，UTF-8 编码，使用缩进 JSON。

| 配置键 | 页面名称 | 类型 | 默认值 | 校验规则 |
| --- | --- | --- | --- | --- |
| `schema_version` | 不展示 | 整数 | `2` | 大于等于 1 |
| `cli_prefix` | 消息命令前缀 | 字符串 | `chat-cli` | 非空，只能是一个可执行文件名或绝对路径，不能含命令操作符 |
| `scheduled_query_enabled` | 定时查询指定群组开关 | 布尔值 | `false` | 仅允许布尔值 |
| `target_group_ids` | 指定群组 ID | 字符串数组 | `[]` | 每项为数字字符串、去空格、去重、最多 100 项；启用查询时至少一项 |
| `log_group_message_content` | 打印群组消息日志 | 布尔值 | `false` | 仅允许布尔值，保存后实时生效 |
| `query_interval_seconds` | 定时执行周期（秒） | 整数 | `60` | 5～86400 |
| `initial_query_count` | 首次查询条数 | 整数 | `2` | 1～100 |

配置示例：

```json
{
  "schema_version": 2,
  "cli_prefix": "chat-cli",
  "scheduled_query_enabled": true,
  "target_group_ids": [
    "987432812330259203",
    "987432812330259204"
  ],
  "log_group_message_content": false,
  "query_interval_seconds": 60,
  "initial_query_count": 2
}
```

配置持久化要求：

1. 文件不存在时创建默认配置。
2. 文件损坏时保留原文件，程序使用安全默认值启动，并在页面显示加载错误。
3. 保存前完整校验；校验失败不得覆盖有效配置。
4. 使用同目录临时文件、刷新磁盘并原子替换目标文件。
5. 保留未知扩展字段，兼容未来版本。
6. 旧版单群组字段 `target_group_id` 自动迁移为 `target_group_ids`。
7. EXE 应放在普通用户可写目录，不应放入受保护的 `Program Files`。

## 7. CLI 能力设计

### 7.1 安全执行规则

- CLI 前缀只表示可执行文件名或绝对路径。
- 所有命令使用参数数组执行。
- `shell=False`，禁止管道、重定向和拼接 shell 命令。
- 默认超时为 30 秒。
- 标准输出优先按 UTF-8 解码；失败时回退系统编码并记录告警。
- 非零退出码、程序不存在、超时、进程启动失败、输出解析失败和业务失败必须映射为明确错误类型。

### 7.2 发送私聊

内部接口：

```python
send_to_user(
    receiver: str,
    text: str | None = None,
    image: Path | None = None,
    file: Path | None = None,
) -> SendResult
```

命令结构：

```text
<cli-prefix> im send-to-user --receiver <receiver> [--text ...] [--image ...] [--file ...]
```

`receiver` 必填；文本、图片和文件至少提供一项。本地文件必须在启动 CLI 前确认存在。

### 7.3 发送群聊

内部接口：

```python
send_to_group(
    group_id: str,
    text: str | None = None,
    image: Path | None = None,
    file: Path | None = None,
) -> SendResult
```

命令使用 `im send-to-group --group-id <group_id>`，其余规则与私聊发送一致。群组 ID 始终使用字符串，避免 JavaScript 大整数精度丢失。

### 7.4 查询历史消息

内部接口：

```python
query_history_messages(
    *,
    group_id: str | None = None,
    user_account: str | None = None,
    query_count: int = 20,
    message_id: str | None = None,
    query_direction: int | None = None,
) -> HistoryQueryResult
```

规则：

- `group_id` 和 `user_account` 必须且只能提供一个。
- `query_count` 为 1～100 的整数。
- `message_id` 与 `query_direction` 必须成对出现。
- `query_direction` 只允许 `0` 或 `1`。
- 响应支持纯 JSON，以及带 `status_code:`、`resp_body:` 前缀的输出。
- 使用 `resultCode == "0"` 判断 CLI 业务是否成功。
- 使用 `msgTotalCount` 判断是否存在消息，不再通过 `chatInfo` 是否存在判断命令成功。
- `msgTotalCount == 0` 时，允许省略 `chatInfo`，解析为正常空结果。
- `msgTotalCount > 0` 且没有有效消息时，视为响应错误。

统一消息模型至少包含：

- `msg_id`
- `group_type`
- `content_type`
- `server_send_time`
- `group_id`
- `sender`
- `receiver`
- `content`
- `at`
- `at_account_list`
- 原始消息对象

## 8. 调度和游标设计

### 8.1 多群组调度

- 使用一个后台调度线程。
- 多个群组按配置顺序串行查询，不并发执行。
- 程序启动且开关已开启时立即执行第一轮。
- 一轮包括所有当前有效群组。
- 一轮全部完成后，再等待 `query_interval_seconds` 秒开始下一轮。
- 因此同一群组两次完成日志的实际间隔约为：配置周期 + 本轮所有群组 CLI 耗时 + 消息处理及日志耗时。
- 例如三个群组合计耗时 25 秒、周期为 60 秒时，同一群组两次完成时间通常约间隔 85 秒，而不是严格 60 秒。
- 若一轮执行超过一个周期，不补跑错过的周期，也不创建并行任务。

### 8.2 每次进程启动后的首次查询

这是当前最终需求，优先级高于旧版“重启后从持久化游标继续”的行为。

对每个群组，本次进程中的第一次查询必须：

1. 忽略 `runtime_state.json` 中保存的旧游标。
2. CLI 命令只携带 `--group-id` 和 `--query-count`。
3. 不携带 `--message-id` 和 `--query-direction`。
4. 获取最新 `initial_query_count` 条消息。
5. 去重并按 `serverSendTime`、`msgId` 升序处理。
6. 全部处理成功后，用响应 `maxMsgId` 或消息集合最大 `msgId` 覆盖群组游标。
7. 重启前未查询到、且不在最新 N 条范围内的旧消息直接忽略，不追赶历史积压。

影响说明：每次重启后最新 N 条消息可能再次被处理或记录一次，这是用“允许少量重复”换取“立即定位最新消息”的明确产品选择。

如果初始化查询为空，且 `maxMsgId` 为 `0` 或缺失：

- 清除该群组旧持久化游标。
- 下一轮仍执行不带 `--message-id` 的最新消息查询。
- 直到获得有效消息 ID 后，才进入运行期增量模式。

如果初始化查询、解析、消息处理或日志写入失败：

- 不把该群组标记为初始化成功。
- 不推进游标。
- 下一周期继续执行无 `--message-id` 的最新消息查询。

### 8.3 同一次运行中的增量查询

群组初始化成功且具有有效游标后，后续查询命令为：

```text
<cli-prefix> im query-history-message \
  --group-id <group-id> \
  --query-count <count> \
  --message-id <cursor> \
  --query-direction 1
```

处理规则：

1. 过滤 `msgId <= cursor` 的消息，防止 CLI 重复返回游标消息。
2. 按服务端时间和消息 ID 从旧到新处理。
3. 返回满页时继续分页，下一页从本页成功保存的新游标开始。
4. 单轮最多 100 页，防止异常 CLI 导致无限循环。
5. 每页所有消息成功处理后，才原子保存本页最大消息 ID。
6. 空结果保留当前有效游标。
7. CLI、处理器或完整消息日志写入失败时不推进当前页游标。

### 8.4 游标文件

游标保存在 `runtime_state.json`：

```json
{
  "schema_version": 1,
  "group_cursors": {
    "987432812330259203": {
      "message_id": "89308574058460924",
      "updated_at": "2026-08-15T12:00:00Z"
    }
  }
}
```

游标按群组独立存储，并使用字符串避免精度损失。文件通过临时文件和原子替换写入。

持久化游标的主要用途是同一次运行中的增量查询状态、故障恢复诊断和状态可见性；新进程启动后的首次 CLI 查询不会使用旧游标。

## 9. 配置实时生效

- Web 保存配置成功后，配置管理器立即通知调度器。
- 开关由关闭变为开启时，立即开始一轮查询。
- 开关由开启变为关闭时，不再启动新查询；已经进入 CLI 的调用允许结束。
- 周期修改后，从保存成功时刻按新周期重新等待。
- CLI 前缀修改后，下一次 CLI 调用使用新值。
- 群组列表修改后，移除的群组不再查询；本进程中首次出现的新群组执行无游标初始化查询。
- 消息日志开关从下一条待处理消息开始读取最新值，无需重启。
- 快速连续保存不得产生多个调度线程或并行查询。

## 10. 消息处理与引用消息解析

消息处理扩展点：

```python
class MessageProcessor(Protocol):
    def process(self, message: ChatMessage) -> None: ...
```

当前默认实现为 `NoOpMessageProcessor`，不进行外部调用。

对于普通消息，日志正文直接使用 `content`。

对于 `contentType == "CARD_MSG"` 的引用回复，解析：

- 当前回复：`cardContext.replyMsg.content`
- 被引用内容：`cardContext.preMsg.content`

日志正文格式：

```text
回复内容↩被引用内容
```

示例：

```text
好的↩我知道了，这个就是那样的
```

若只有回复正文，则只记录回复正文；JSON 无效或结构不匹配时安全回退原始 `content`。

## 11. 日志设计

统一格式：

```text
时间 - 级别 - logger名称 - 正文
```

示例：

```text
2026-08-08 15:07:32,122 - INFO - scheduler - [987432812330259203] a123456 ➔ 哈哈
```

### 11.1 `logs/app.log`

- 程序运行、调度器和 CLI 查询日志。
- 单文件 10 MB，保留 5 个历史文件。
- 查询成功时，群组 ID、CLI 返回数量和耗时必须在同一行：

  ```text
  2026-08-08 15:07:32,121 - INFO - cliclient - [987432812330259203] count=2 elapsed_seconds=8.092
  ```

- `elapsed_seconds` 单位为秒，保留三位小数。
- 不再额外输出重复的查询完成日志。
- 查询失败记录群组 ID、操作、耗时、错误类别和可用的退出码。
- 开启消息内容日志时，每条消息格式为：

  ```text
  [group_id] sender ➔ content
  ```

- `app.log` 中的正文最多 4096 个字符，超出后追加省略号。
- 回车和换行转义，保证每条记录只占一行。

### 11.2 `logs/messages.log`

仅当 `log_group_message_content` 开启时写入。每条完整消息一行，字段顺序固定为：

```text
日志记录时间|msgId|groupType|contentType|serverSendTime|groupId|sender|receiver|content
```

要求：

- `content` 不截断。
- 反斜杠、竖线、回车、换行分别进行反斜杠转义。
- `serverSendTime` 从 Unix 时间戳转换为 UTC ISO 8601 标准时间，保留毫秒并使用 `Z` 后缀。
- 示例时间：`2026-08-08T06:44:41.169Z`。
- 无法识别的服务端时间保留原值，避免数据丢失。
- 引用回复使用 `回复内容↩被引用内容`。
- 写入失败视为本条消息处理失败，不推进当前页游标，后续可重试。

### 11.3 `logs/operations.log`

- 记录程序启动、关闭以及 Web 页面配置修改操作。
- 单文件 10 MB，保留 5 个历史文件。
- 启动记录包含版本号和本地 Web 地址。
- 配置保存成功记录发生变化的配置项名称。
- 配置请求被拒绝时记录原因和错误字段名称。
- 持久化失败或未知异常记录错误类别。
- 不记录配置值、完整请求体、CLI 路径或群组 ID。
- 操作日志不重复写入 `app.log`。

## 12. Web 页面与 API

Web 服务仅绑定 `127.0.0.1`，默认端口 `8765`，Flask debug 模式关闭。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/` | 配置页面 |
| `GET` | `/api/health` | 健康状态、版本和调度状态 |
| `GET` | `/api/config` | 当前配置、版本、调度状态和加载错误 |
| `PUT` | `/api/config` | 校验、原子保存并发布新配置 |

页面要求：

- 中文标签和错误提示。
- 群组 ID 文本框每行一个 ID。
- 显示程序版本和运行状态。
- 保存期间防止重复提交。
- 保存成功后明确提示，失败时显示字段级错误。
- 刷新页面后从已落盘配置重新加载。
- 不使用公网 CDN。
- 支持键盘操作和常见桌面浏览器宽度。
- 响应包含内容类型、防嵌入、Referrer、CSP 和禁止缓存等安全头。

## 13. 数据目录与生成文件

源码模式默认使用当前工作目录；打包模式使用 `sys.executable` 所在目录，而不是 PyInstaller 临时解压目录。

运行后可能生成：

```text
config.json
runtime_state.json
logs/
├── app.log
├── messages.log
└── operations.log
```

这些用户数据不得打入 EXE。

## 14. 版本和 Windows 打包

### 14.1 版本管理

- 唯一版本来源：`src/chat_message_agent/version.py` 中的 `__version__`。
- 当前版本：`0.5.0`。
- Web 页面、健康 API、`--version`、EXE 文件名和 Windows 文件属性必须一致。
- 每次对外打包都应更新版本号。

### 14.2 打包命令

在 Windows 命令提示符运行：

```bat
package.bat
```

输出文件：

```text
dist\chat-message-agent-v<版本号>.exe
```

打包脚本执行：

1. 切换到 `package.bat` 所在目录。
2. 检查 Python。
3. 从唯一版本源读取并打印版本。
4. 安装或校验 `requirements-dev.txt`。
5. 删除 `build` 目录。
6. 删除 `dist` 中旧的 `chat-message-agent.exe` 和版本化同名 EXE。
7. 生成 Windows `FileVersion`、`ProductVersion` 元数据。
8. 使用 spec 文件执行 PyInstaller one-file console 打包。
9. 检查目标 EXE 是否存在。
10. 执行新 EXE 的 `--version`，确认内置版本与文件名一致。

### 14.3 `build` 和 `dist` 清理结论

- 正常使用当前 `package.bat` 时，无需用户手工清理 `build` 和 `dist`。
- 脚本会清理整个 `build`，并删除 `dist` 中本项目旧 EXE。
- `dist` 中其他无关文件不会被全部删除。
- 若打包后仍表现为旧版本，应首先确认运行的是当前目录新生成的带版本号 EXE，而不是其他目录、快捷方式或仍在运行的旧进程。
- 同时检查 `src/chat_message_agent/version.py`、构建日志版本和 EXE 的 `--version` 输出是否一致。

## 15. 错误模型与可靠性

错误至少区分：

- 配置或参数校验失败。
- CLI 不存在。
- CLI 超时。
- CLI 进程启动或退出失败。
- CLI 输出解析失败。
- 聊天服务业务失败。
- 配置、游标或消息日志持久化失败。

可靠性原则：

- 单次 CLI 失败不能使 Web 服务退出。
- 调度线程具有顶层异常保护。
- 配置和游标使用锁及原子写入。
- 页内处理失败时不推进游标。
- 崩溃最多造成当前页或重启后最新 N 条重复处理，不应因提前推进游标造成运行期消息永久漏记。
- 启动时主动忽略最新 N 条之外的历史积压，这是明确需求，不视为漏消息缺陷。
- 退出时停止新任务，并最多等待当前调度线程 35 秒。

## 16. 架构与代码结构

```text
Application / Bootstrap
├── ConfigManager
│   ├── config.json
│   ├── validation / migration
│   └── change notification
├── StateStore
│   └── runtime_state.json
├── ChatCliClient
│   ├── SubprocessRunner
│   ├── CLI output parser
│   ├── send_to_user
│   ├── send_to_group
│   └── query_history_messages
├── QueryScheduler
│   ├── per-process group initialization
│   ├── incremental pagination
│   └── MessageProcessor
├── Flask Web
│   ├── templates / static assets
│   └── JSON API
└── Logging
    ├── app.log
    ├── messages.log
    └── operations.log
```

关键源文件：

| 文件 | 职责 |
| --- | --- |
| `app.py` | 应用组装、Web 服务、浏览器和生命周期 |
| `config.py` | 配置模型、迁移、校验、持久化和通知 |
| `state.py` | 群组游标读取、保存和清除 |
| `cli_client.py` | CLI 参数构造、进程执行、耗时日志和错误映射 |
| `cli_parser.py` | CLI JSON、业务码、消息和数量解析 |
| `scheduler.py` | 多群组调度、首次查询、增量和分页 |
| `message_content.py` | 普通及引用回复正文提取 |
| `message_log.py` | 完整消息日志、字段转义和时间转换 |
| `logging_setup.py` | 日志格式、轮转和文件隔离 |
| `web/routes.py` | 页面、配置 API、健康 API 和操作审计 |
| `version.py` | 唯一版本来源 |

## 17. 测试和质量门禁

代码提交前至少执行：

```bat
python -m pytest -q
python -m ruff check .
```

当前 `0.5.0` 基线共有 59 个自动化测试，覆盖：

- CLI 参数和错误映射。
- `resultCode` 与 `msgTotalCount` 解析。
- 配置默认值、迁移、校验和原子写入。
- 多群组独立游标。
- 每次进程启动后忽略持久化游标。
- 初始化空结果和 `maxMsgId=0` 时清除旧游标。
- 同进程增量查询、分页、去重和最大页数。
- 处理器或完整消息日志失败时不推进游标。
- 配置热更新和日志开关实时生效。
- 引用回复内容解析。
- 三类日志格式及文件隔离。
- Web API、安全响应头和应用生命周期。
- 版本资源和版本化 EXE 文件名。

发布前还需执行：

```bat
package.bat
dist\chat-message-agent-v0.5.0.exe --version
```

Windows 冒烟测试应确认：

- 无 Python 的干净 Windows 10/11 机器可以启动 EXE。
- 页面自动打开，或可通过日志中的本地地址访问。
- 配置保存并实时生效。
- 三类日志按规则生成。
- 多群组首次和增量查询符合 CLI 实际行为。
- EXE 文件名、`--version` 和 Windows 文件属性一致。

## 18. 验收标准

- [x] CLI 调用不使用 shell，路径含空格时可安全执行。
- [x] 支持发送私聊、发送群聊和历史查询原子接口。
- [x] 使用 `resultCode` 判断业务成功，使用 `msgTotalCount` 判断消息数量。
- [x] 支持多个群组 ID，每行一个，串行查询。
- [x] 默认周期为 60 秒，默认首次查询为 2 条。
- [x] 每次进程启动后，各群组第一次查询不传 `--message-id`。
- [x] 初始化成功后覆盖保存最新消息 ID。
- [x] 同一次运行中使用游标增量查询和分页。
- [x] 配置页面仅监听本机并可实时更新调度。
- [x] 消息内容日志开关实时生效。
- [x] `app.log` 使用简洁消息和 CLI 汇总格式。
- [x] `messages.log` 保存完整字段、标准时间和引用回复正文。
- [x] `operations.log` 独立记录启动和 Web 配置操作。
- [x] EXE 文件名及文件属性包含统一版本号。
- [x] `package.bat` 清理本项目旧构建并验证新 EXE 版本。
- [x] 自动化测试和静态检查通过。

## 19. 已知行为、限制和风险

| 项目 | 最终说明 |
| --- | --- |
| 调度间隔 | 周期从整轮结束后开始等待，因此实际同群组间隔包含所有群组查询耗时 |
| 重启重复 | 重启后最新 N 条可能重复处理，属于最终需求允许的行为 |
| 重启历史 | 最新 N 条之前的积压消息主动忽略，属于最终需求，不是缺陷 |
| 消息至少一次 | 同一次运行中，页处理完成前崩溃可能导致本页重试 |
| 群组并发 | 当前串行执行，群组越多、CLI 越慢，实际间隔越长 |
| 本地目录权限 | EXE 目录不可写会影响配置、游标和日志，应使用普通用户可写目录 |
| CLI 协议变化 | 输出字段或分页语义变化可能导致解析失败，需要根据真实 CLI 更新测试 |
| 日志敏感性 | 开启消息内容日志后会记录正文，日志文件应限制访问并妥善保管 |

## 20. 发布与 Git 工作流约定

后续用户明确要求采用以下流程：

1. 不在推送前检测、获取或合并远端改动。
2. 不创建功能分支。
3. 不创建 Pull Request。
4. 直接在本地 `main` 提交指定范围的改动。
5. 直接执行：

   ```text
   git push origin main
   ```

6. 禁止强制推送。
7. 如果远端 `main` 已领先导致普通推送被拒绝，立即停止并报告；不得自动拉取、变基、合并或覆盖远端。
8. 提交前仍需检查本地改动范围并完成适当测试，避免把无关文件纳入提交。

此工作流是项目所有者的明确操作要求，优先于此前使用功能分支和 PR 合入 `main` 的历史流程。

## 21. 版本演进摘要

| 版本/阶段 | 主要变化 |
| --- | --- |
| 初始实现 | CLI 封装、本机 Web 配置、单群组定时查询、游标和打包基础 |
| 多群组增强 | 群组 ID 支持多行配置、日志开关实时生效、CLI 结果判断修正 |
| 版本化打包 | EXE 文件名、`--version` 和 Windows 文件属性统一版本 |
| 完整消息日志 | 新增 `messages.log` 和完整字段记录 |
| 引用回复 | `CARD_MSG` 解析为 `回复↩引用` |
| 日志简化 | `app.log` 使用简洁消息格式，CLI 数量和耗时合并为一行 |
| 操作日志 | 新增独立 `operations.log` |
| `0.5.0` | 每次进程启动后忽略旧游标，直接获取各群组最新指定条数消息 |

## 22. 备份说明

本文件为截至 2026-08-16 的完整需求和设计基线备份。后续需求发生变化时，应：

1. 更新正式说明书或新增下一份带日期的备份。
2. 明确标注被替代的旧行为。
3. 同步更新 README、测试和版本号。
4. 确保代码行为、文档、日志示例和打包版本保持一致。
