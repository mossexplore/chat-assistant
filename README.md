# Windows 聊天消息查询程序

这是一个仅监听本机回环地址的 Flask 程序，用于配置聊天 CLI，并按群组独立游标周期性增量查询消息。V1 的消息处理器是 No-Op 扩展点，不会调用知识库、自动回复或转发消息。

## 环境与运行

- Windows 10/11 64 位
- Python 3.11 或兼容版本
- 已安装、登录并可正常使用目标聊天 CLI

开发运行：

```bat
python -m pip install -r requirements-dev.txt
set PYTHONPATH=src
python -m chat_message_agent
```

服务默认监听 `http://127.0.0.1:8765/` 并自动打开浏览器。可用 `--no-browser` 禁止自动打开，或用 `--port 8766` 指定其他本机端口。`python -m chat_message_agent --version` 只打印版本，不启动服务。

首次启动会在当前工作目录（EXE 模式为 EXE 所在目录）创建：

- `config.json`：用户配置；
- `runtime_state.json`：各群组消息游标；
- `logs/app.log`：轮转日志，单文件 10 MB、保留 5 份。

请把免安装程序放在普通用户可写目录，不要放入受保护的 `Program Files`。配置损坏时程序保留原文件、用默认配置启动，并在页面显示错误；游标只在整页消息成功处理后推进。

## 查询语义

目标群组没有游标时，程序按“首次查询条数”查询最近消息并建立游标。此后每次 CLI 调用固定携带 `--message-id <cursor> --query-direction 1`，对可能重复返回的游标消息去重，并在满页时继续分页。真实 CLI 的首次查询参数语义仍需按设计说明书的“待联调确认项”在目标环境验证。

## 测试与静态检查

```bat
python -m pytest -q
python -m ruff check .
```

测试使用模拟执行器，不依赖真实聊天软件。

## Windows 打包

在 Windows 命令提示符执行：

```bat
package.bat
dist\chat-message-agent.exe --version
```

脚本安装受控范围内的构建依赖、读取唯一版本来源、清理本项目构建产物并使用 PyInstaller one-file console 模式生成 `dist\chat-message-agent.exe`。配置、运行状态和日志不会打入 EXE。

## 常见问题

- **找不到聊天 CLI**：在页面填写 PATH 中的可执行文件名，或填写带 `.exe` 的完整绝对路径。
- **群组 ID 无效**：启用定时查询时必须填写纯数字群组 ID；它始终按字符串保存，不会损失精度。
- **端口占用**：退出占用 8765 的程序，或通过 `--port` 更换端口。
- **无法保存**：移动到用户可写目录，并查看 `logs/app.log` 中的具体错误。
- **查询失败**：旧游标会保留，下个周期自动重试；日志包含群组 ID、错误类别和有限长度摘要。
