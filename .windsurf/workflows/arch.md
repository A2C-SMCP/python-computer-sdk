---
description: 开发架构说明
---

本SDK主要是实现 A2C-SMCP 协议。

A2C-SMCP协议主要有三部分：Agent-Server-Computer。三者通过Socket.IO协议实现实时通信。协议的概况在 @docs/index.md （因为文档较长，如无必要不要读取）

---

Computer主要负责MCP工具的生命周期维护，调度管理等工作。其代码封装在 @a2c_smcp/computer 之下

SMCP协议数据结构与事件的定义，主要集中在：

@a2c_smcp/smpc.py 之中。其定义方式主要使用 TypedDict进行定义。
@a2c_smcp/computer/mcp_clients/model.py 之中。其定义主要是对上者的Pydantic实现，因为在Python进程内，使用Pydantic会有更好的类型管理与数据结构校验的能力。

因此SMCP协议以 @a2c_smcp/smpc.py 为主，以 @a2c_smcp/computer/mcp_clients/model.py 为辅。如果协议有调整与修改，二者均需要进行修改。

如果事件发生变动，需要注意有以下位置需要同步这个变动：

1. Socket.IO注册的事件响应函数，按目前的其它响应函数命令规范，需要进行调整。
2. 测试文件中 Socket.IO 服务器的Mock。因为其名称在 trigger_event 中进行转义，也就是事件响应函数与事件名称有关系，需要同步修改。
3. （未来）A2C-SMCP 信令服务器相关响应函数与测试用例
4. （未来）A2C-SMCP Agent相关响应函数与测试用例

当前封装中 @a2c_smcp/computer/mcp_clients/base_client.py 是 MCP Client封装基类，这里面有个重点，因为我们使用了transitions库进行状态管理，因此外界不好代码补全，因此我添加了 @a2c_smcp/computer/mcp_clients/base_client.pyi 类型定义文件。如果是对这个基类有能力上的变动，需要记住 ** 同步修改 pyi 文件**

---

Server主要负责中央信令服务器，负责维护Computer/Agent元数据信息，信号传输转发消息，或者将收到的一些消息转换为Notification广播出去，不同的动作其处理方式不一，大概就这三种。其主要代码在：@a2c_smcp/server 目录下

1. 认证系统：创建了AuthenticationProvider抽象基类和DefaultAuthenticationProvider默认实现
2. 基础架构：实现了BaseNamespace抽象基类，提供通用连接管理和认证功能
3. SMCP Namespace：完整实现了SMCPNamespace，包含所有SMCP协议事件处理方法
4. 类型定义：创建了完整的类型系统，包括Session类型和工具函数
5. 工具函数：实现了房间管理相关的工具函数
6. 测试用例：创建了完整的测试用例，展示了使用方法
7. 文档：在docs/server.md中添加了详细的使用文档

文件结构：
a2c_smcp/server/auth.py - 认证系统
a2c_smcp/server/base.py - 基础Namespace
a2c_smcp/server/namespace.py - SMCP协议实现
a2c_smcp/server/types.py - 类型定义
a2c_smcp/server/utils.py - 工具函数
tests/unit_tests/server/ - 测试用例
docs/server.md - 使用文档

需要注意，关于 @a2c_smcp/server 的封装，我们提供了同步原语与异步原语两种模式，后续所有的业务需求改动与变动，均需要同步体现在同步与异步版本之中。

---

Agent模块主要也是一个Socket.IO Client的封装。与Server类似，也提供同步+异步两种模式的封装。同时因为当前项目Agent封装不是重点，因此与Server一样，仅预留需要提供的Agent能力接口即可，具体实现由使用方来进行实现。


# Agent 模块系统说明与总结

## 架构概览

- __认证体系__（[a2c_smcp/agent/auth.py](@a2c_smcp/agent/auth.py:0:0-0:0)）
  - [AgentAuthProvider](@a2c_smcp/agent/auth.py:16:0-64:12) 抽象基类：规范 [get_agent_id()](@a2c_smcp/agent/auth.py:22:4-31:12)、[get_connection_auth()](@a2c_smcp/agent/auth.py:33:4-42:12)、[get_connection_headers()](@a2c_smcp/agent/auth.py:44:4-53:12)、[get_agent_config()](@a2c_smcp/agent/auth.py:131:4-139:9)。
  - [DefaultAgentAuthProvider](@a2c_smcp/agent/auth.py:67:0-139:9)：支持 API Key、自定义头、可扩展 [auth](@a2c_smcp/agent/auth.py:33:4-42:12) 数据。

- __类型与回调协议__（[a2c_smcp/agent/types.py](@a2c_smcp/agent/types.py:0:0-0:0)）
  - 类型别名：`AgentID`、`ComputerID`、`RequestID`、[AgentConfig](@a2c_smcp/agent/types.py:24:0-30:45)、[ToolCallContext](@a2c_smcp/agent/types.py:33:0-41:51)。
  - 事件处理协议：
    - 同步：[AgentEventHandler](@a2c_smcp/agent/types.py:44:0-89:11) 包含 [on_computer_enter_office](@a2c_smcp/agent/types.py:50:4-58:11) / [leave_office](@a2c_smcp/agent/types.py:60:4-68:11) / [update_config](@a2c_smcp/agent/types.py:70:4-78:11) / [on_tools_received](@a2c_smcp/agent/types.py:119:4-124:11)。
    - 异步：[AsyncAgentEventHandler](@a2c_smcp/agent/types.py:92:0-124:11) 等价 async 形态。

- __基础抽象__（[a2c_smcp/agent/base.py](@a2c_smcp/agent/base.py:0:0-0:0)）
  - [BaseAgentClient](@a2c_smcp/agent/base.py:29:0-249:12)：统一封装
    - 事件合法性校验：禁止发送 `notify:*` 与 `agent:*`。
    - 请求构造：[create_tool_call_request()](@a2c_smcp/agent/base.py:83:4-105:9)、[create_get_tools_request()](@a2c_smcp/agent/base.py:107:4-123:9)。
    - 超时处理：返回 `CallToolResult(isError=True)`。
    - 通知处理骨架：进入/离开办公室、配置更新；工具列表响应分发 [process_tools_response()](@a2c_smcp/agent/base.py:220:4-239:65)。
  - 子类需实现 [emit()](@a2c_smcp/agent/sync_client.py:70:4-87:54)、[call()](@a2c_smcp/agent/client.py:90:4-110:66)、[register_event_handlers()](@a2c_smcp/agent/sync_client.py:209:4-216:102)。

- __同步客户端__（[a2c_smcp/agent/sync_client.py](@a2c_smcp/agent/sync_client.py:0:0-0:0)）
  - 类：[SMCPAgentClient(socketio.Client, BaseAgentClient)](@a2c_smcp/agent/sync_client.py:35:0-257:69)。
  - 核心方法：[connect_to_server()](@a2c_smcp/agent/sync_client.py:111:4-142:60)、[emit_tool_call()](@a2c_smcp/agent/client.py:148:4-182:13)、[get_tools_from_computer()](@a2c_smcp/agent/sync_client.py:180:4-207:17)。
  - 自动行为：收到 `ENTER_OFFICE_NOTIFICATION` / `UPDATE_CONFIG_NOTIFICATION` 时自动拉取工具并回调 [on_tools_received()](@a2c_smcp/agent/types.py:119:4-124:11)。
  - 线程安全：标注为“非线程安全”。

- __异步客户端__（[a2c_smcp/agent/client.py](@a2c_smcp/agent/client.py:0:0-0:0)）
  - 类：[AsyncSMCPAgentClient(socketio.AsyncClient, BaseAgentClient)](@a2c_smcp/agent/client.py:35:0-302:65)。
  - 同步版等价的 async 形态：包含 [connect_to_server()](@a2c_smcp/agent/sync_client.py:111:4-142:60)、[emit_tool_call()](@a2c_smcp/agent/client.py:148:4-182:13)、[get_tools_from_computer()](@a2c_smcp/agent/sync_client.py:180:4-207:17)。
  - 事件回调与工具分发均为 async 版本。

- __协议常量/数据结构__（来自 `a2c_smcp/smcp.py`）
  - `SMCP_NAMESPACE`、`TOOL_CALL_EVENT`、`CANCEL_TOOL_CALL_EVENT`、`GET_TOOLS_EVENT`。
  - 通知：`ENTER_OFFICE_NOTIFICATION`、`LEAVE_OFFICE_NOTIFICATION`、`UPDATE_CONFIG_NOTIFICATION`。
  - 请求/响应：`ToolCallReq`、`GetToolsReq`、`GetToolsRet`、`AgentCallData` 等。

## 关键流程

- __连接__：[connect_to_server(url, namespace=SMCP_NAMESPACE, ...)](@a2c_smcp/agent/sync_client.py:111:4-142:60)，自动注入 [auth](@a2c_smcp/agent/auth.py:33:4-42:12) 与 [headers](@a2c_smcp/agent/auth.py:44:4-53:12)。
- __通知处理__：
  - Enter Office → 校验 `office_id`/[computer](@a2c_smcp/agent/sync_client.py:180:4-207:17) → 调用事件处理器 → 自动拉取工具 → 分发给 [on_tools_received()](@a2c_smcp/agent/types.py:119:4-124:11)。
  - Update Config → 调用事件处理器 → 重新拉取工具 → 分发。
  - Leave Office → 调用事件处理器。
- __工具调用__：[emit_tool_call(computer, tool_name, params, timeout)](@a2c_smcp/agent/client.py:148:4-182:13) 同步/异步分别通过 [call()](@a2c_smcp/agent/client.py:90:4-110:66) 发起；超时发送取消事件并返回错误结果。

## 可扩展性与最佳实践

- __认证__：通过实现自定义 [AgentAuthProvider](@a2c_smcp/agent/auth.py:16:0-64:12) 对接不同鉴权策略（API Key、JWT、自定义 header/auth）。
- __事件处理__：注入 [AgentEventHandler](@a2c_smcp/agent/types.py:44:0-89:11) 或 [AsyncAgentEventHandler](@a2c_smcp/agent/types.py:92:0-124:11) 与业务集成。
- __命名空间__：默认 `SMCP_NAMESPACE`，可在 [connect_to_server()](@a2c_smcp/agent/sync_client.py:111:4-142:60) 时自定义以实现隔离（测试/多租户）。
- __一致性__：同步与异步两套实现的功能需要保持一致，调整协议时需同步更新。

## 注意事项

- 同步客户端非线程安全，避免多线程共享实例；异步客户端建议单事件循环内使用。
- 修改 `a2c_smcp/smcp.py` 的事件或结构时，需同步更新 Agent 端注册/类型引用与测试。
- 参考现有测试位置：`tests/unit_tests/agent/`（如需增强，请补充）。

## 关联文件与入口

- 类型与协议：[a2c_smcp/agent/types.py](@a2c_smcp/agent/types.py)
- 认证：[a2c_smcp/agent/auth.py](@/a2c_smcp/agent/auth.py)
- 抽象：[a2c_smcp/agent/base.py](@a2c_smcp/agent/base.py)
- 同步客户端：[a2c_smcp/agent/sync_client.py]@a2c_smcp/agent/sync_client.py)
- 异步客户端：[a2c_smcp/agent/client.py](@a2c_smcp/agent/client.py)
- 文档：`docs/agent.md`

---

如果变动涉及到 @smcp.py 中协议内容变更，需要注意将协议的变更同步更新到 @a2c_smcp/server @a2c_smcp/computer @a2c_smcp/agent 三个模块中去。