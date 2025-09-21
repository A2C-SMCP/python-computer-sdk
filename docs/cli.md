# A2C Computer CLI 使用指南

本指南介绍如何使用 A2C Computer CLI 进行计算机端的运行、配置管理、工具查询与 Socket.IO 连接。

- 技术栈：`typer + rich + prompt_toolkit`
- 交互原则：
  - 计算机的配置管理、启停管理与状态查询通过 CLI 暴露。
  - 工具的实际调用与控制通过 Socket.IO 通道由远端 Agent 驱动。
  - 对配置中出现的动态变量如 `${input:<id>}`，CLI 会在渲染阶段按需解析（需要你先提供对应的 inputs 定义）。

## 安装与启动

- 安装（示例）
```bash
pip install -e .
```

- 启动 CLI
```bash
python -m a2c_smcp_cc.cli.main run
# 或（如果配置了 console_scripts）
a2c-computer run
```

- 常用参数
```bash
# 自动连接 MCP Server（在添加配置时立即尝试启动）和自动重连
python -m a2c_smcp_cc.cli.main run --auto-connect true --auto-reconnect true
```

启动后将进入交互模式（prompt: `a2c>`），输入 `help` 查看可用命令。

## 交互命令总览

- status
  - 查看当前 MCP 管理器中各服务器的状态。
- tools
  - 列出当前可用工具（来源于所有已激活的 MCP Server）。
- mcp
  - 打印当前内存中的 MCP 配置（含 `servers` 与 `inputs` 概览）。
- server add <json|@file>
  - 动态添加或更新某个 MCP Server 的配置。支持直接输入 JSON 字符串或 `@path/to.json` 从文件加载。
  - 配置会按需渲染 `${input:<id>}` 占位符，并通过强校验确认结构有效。
- server rm <name>
  - 移除指定名称的 MCP Server 配置，如果该服务已启动会一并停止。
- start <name>|all
  - 启动单个或全部（未禁用）MCP Server 客户端。
- stop <name>|all
  - 停止单个或全部 MCP Server 客户端。
- inputs load @file
  - 从文件加载 inputs 定义（用于占位符的按需解析）。文件必须是包含 inputs 列表的 JSON。
- socket connect <url>
  - 连接到信令服务器（Socket.IO）。
- socket join <office_id> <computer_name>
  - 加入一个 office（房间）。成功后会接收与该 office 相关的事件。
- socket leave
  - 离开当前 office。
- notify update
  - 在已连接并加入 office 的前提下，向服务器发送 `server:update_mcp_config` 事件，通知远端刷新配置。
- render <json|@file>
  - 测试渲染任意 JSON 结构，内部按需解析其中的 `${input:<id>}` 占位符并打印结果。
- quit | exit
  - 退出 CLI。

## 配置与 Inputs 格式

CLI 使用的是 SMCP 协议同构结构（与 `a2c_smcp_cc/socketio/smcp.py` 中的类型一致）。

- Server 配置（示例，stdio 类型）：
```json
{
  "name": "my-stdio-server",
  "type": "stdio",
  "disabled": false,
  "forbidden_tools": [],
  "tool_meta": {
    "echo": {"auto_apply": true}
  },
  "server_parameters": {
    "command": "my_mcp_server",
    "args": ["--flag"],
    "env": {"MY_ENV": "${input:MY_ENV_VALUE}"},
    "cwd": null,
    "encoding": "utf-8",
    "encoding_error_handler": "strict"
  }
}
```

- Inputs 定义（示例）：
```json
[
  {
    "id": "MY_ENV_VALUE",
    "type": "promptString",
    "description": "Environment variable for the server",
    "default": "hello",
    "password": false
  },
  {
    "id": "REGION",
    "type": "pickString",
    "description": "Select a region",
    "options": ["us-east-1", "eu-west-1"],
    "default": "us-east-1"
  }
]
```

当 Server 配置中出现 `${input:MY_ENV_VALUE}` 这样的占位符时，会在「渲染」阶段按需解析，解析逻辑来自你通过 `inputs load` 提供的 inputs 定义。

## 常见操作示例

1) 加载 inputs 定义
```bash
# 假设 inputs.json 含上面示例
inputs load @./inputs.json
```

2) 添加/更新一个 Server 配置
```bash
# 从文件加载（推荐）
server add @./server_stdio.json

# 或直接输入 JSON 字符串
server add {"name":"my-stdio-server","type":"stdio","disabled":false,"forbidden_tools":[],"tool_meta":{},"server_parameters":{"command":"my_mcp_server","args":[],"env":null,"cwd":null,"encoding":"utf-8","encoding_error_handler":"strict"}}
```

3) 启动所有服务，查看状态与工具
```bash
start all
status
tools
```

4) 连接信令服务器并加入 office
```bash
socket connect http://localhost:7000
socket join office-123 "My Computer"
```

5) 通知远端刷新配置
```bash
notify update
```

6) 测试渲染任意 JSON
```bash
render {"env":"${input:MY_ENV_VALUE}","regions":"${input:REGION}"}
# 或ender @./any.json
```

7) 停止与移除
```bash
stop all
server rm my-stdio-server
```

## 注意事项与最佳实践

- Server 名称唯一性
  - 当多个服务器存在相同工具名时，系统会抛出冲突警告。建议使用 `tool_meta.alias` 为工具添加别名避免冲突。
- 禁用工具
  - 可通过 `forbidden_tools` 禁用特定工具；禁用后该工具无法被调用。
- auto_apply
  - 当 `tool_meta.<tool>.auto_apply = true` 时，将跳过调用前的用户二次确认（若你的应用侧设置了确认策略）。
- 渲染与报错
  - 若引用了未定义的 `${input:<id>}`，渲染时会记录警告并尽量保留原值继续；建议确保 inputs 定义完整。
- Socket.IO 会话
  - `notify update` 需要已 `socket connect` 并成功 `socket join` 后才能正确通知；否则会提示未连接。
- 参数大小与复杂 JSON
  - 在 `server add` 与 `render` 中直接粘贴长 JSON 可能不便，建议使用 `@file.json` 方式。

## 故障排查

- 看不到任何工具
  - 确认已 `start all` 或 `start <name>`，并检查对应进程是否正常启动。
- 工具名冲突报错
  - 为冲突的工具配置 `tool_meta.alias`，保证在全局唯一。
- 输入占位符没有被替换
  - 确认已通过 `inputs load @file` 提供 inputs 定义，或检查 id 是否拼写正确。
- 无法通知远端刷新
  - 确认已 `socket connect <url>` 且 `socket join <office_id> <computer_name>` 成功，再执行 `notify update`。

## 参考

- 代码位置
  - CLI 主入口：`a2c_smcp_cc/cli/main.py`
  - 计算机核心：`a2c_smcp_cc/computer.py`
  - Socket.IO SMCP 类型：`a2c_smcp_cc/socketio/smcp.py`
  - Socket.IO 客户端：`a2c_smcp_cc/socketio/client.py`
  - 输入渲染：`a2c_smcp_cc/inputs/render.py`
  - CLI I/O 工具：`a2c_smcp_cc/inputs/cli_io.py`
